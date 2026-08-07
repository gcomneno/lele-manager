import { test, expect, type APIRequestContext, type Page } from '@playwright/test'

const API = '/api/v1/tritalele'

function ingestionRegion(page: Page) {
  return page.getByRole('region', {
    name: 'Collect new LeLe',
    exact: true,
  })
}

async function countVaultFiles(page: Page): Promise<number> {
  const response = await page.request.get('/vault/tree')
  expect(response.ok()).toBeTruthy()
  const body = (await response.json()) as {
    tree: { type: 'dir' | 'file'; children?: unknown[] }
  }
  const count = (node: unknown): number => {
    if (typeof node !== 'object' || node === null) return 0
    const item = node as { type?: string; children?: unknown[] }
    if (item.type === 'file') return 1
    return (item.children ?? []).reduce<number>((total, child) => total + count(child), 0)
  }
  return count(body.tree)
}

async function stageAccepted(
  request: APIRequestContext,
  logicalName: string,
): Promise<{ candidateId: string; revision: number; lessonId: string; path: string }> {
  const staged = await request.post(`${API}/ingestion/stage`, {
    data: {
      content: `Candidate for controlled partial refresh: ${logicalName}`,
      source_kind: 'plain_text',
      logical_name: logicalName,
      max_characters: 2000,
    },
  })
  expect(staged.ok()).toBeTruthy()
  const candidateId = (await staged.json()).candidate_ids[0] as string
  const revised = await request.patch(`${API}/candidates/${encodeURIComponent(candidateId)}`, {
    data: {
      expected_revision: 0,
      proposed_metadata: {
        topic: 'e2e',
        source: 'playwright',
        importance: 4,
        tags: ['e2e', 'partial'],
        date: '2026-07-22',
        title: 'Controlled partial refresh',
      },
    },
  })
  expect(revised.ok()).toBeTruthy()
  const revisedBody = await revised.json()
  const accepted = await request.post(
    `${API}/candidates/${encodeURIComponent(candidateId)}/accept`,
    { data: { expected_revision: revisedBody.revision, reason: 'ready for controlled E2E' } },
  )
  expect(accepted.ok()).toBeTruthy()
  const acceptedBody = await accepted.json()
  return {
    candidateId,
    revision: acceptedBody.revision,
    lessonId: acceptedBody.approval_destination.lesson_id,
    path: acceptedBody.approval_destination.relative_vault_path,
  }
}

test.describe.serial('TritaLeLe GUI', () => {
  test('plain text: preview, stage, revise, accept and one explicit approval', async ({ page }) => {
    await page.goto('/app/#/tritalele')
    await expect(page.getByRole('heading', { name: 'Collect new LeLe' })).toBeVisible()
    await expect(page.getByText('No selection.')).toBeVisible()

    const initialVaultFiles = await countVaultFiles(page)

    await ingestionRegion(page).getByLabel('Source name').fill('pasted-happy-path.txt')
    const source = ingestionRegion(page).getByLabel('Source text')
    await source.fill('Plain text incollato per il workflow TritaLeLe deterministico.')
    await page.getByRole('button', { name: 'Create preview' }).click()
    await expect(page.getByTestId('ingestion-preview')).toBeVisible()
    await expect(page.getByRole('button', { name: 'Add to collection' })).toBeEnabled()

    await source.fill('Plain text incollato modificato: la preview precedente non è più valida.')
    await expect(page.getByTestId('ingestion-preview')).toHaveCount(0)
    await expect(page.getByRole('button', { name: 'Add to collection' })).toBeDisabled()

    await page.getByRole('button', { name: 'Create preview' }).click()
    await page.getByRole('button', { name: 'Add to collection' }).click()
    await expect(page.getByText(/Staging completed/)).toBeVisible()
    expect(await countVaultFiles(page)).toBe(initialVaultFiles)

    await page.locator('.candidate-card').filter({ hasText: 'pasted-happy-path.txt' }).click()
    await expect(page.getByRole('heading', { name: 'LeLe details' })).toBeVisible()
    await page.getByLabel('Proposed text').fill(
      'Testo rivisto in Markdown con **contenuto canonico** e provenienza intatta.',
    )
    await page.getByLabel('Topic', { exact: true }).fill('e2e')
    await page.getByLabel('Source', { exact: true }).fill('playwright')
    await page.getByLabel('Importance', { exact: true }).fill('4')
    await page.getByLabel('Date', { exact: true }).fill('2026-07-22')
    await page.getByLabel('Tags', { exact: true }).fill('e2e, tritalele')
    await page.getByLabel('Title', { exact: true }).fill('TritaLeLe approval')
    await page.getByLabel('Revision reason (optional)').fill('editorial pass')
    await page.getByRole('button', { name: 'Save revision' }).click()
    await expect(page.getByText(/Revision 1 saved/)).toBeVisible()
    await expect(page.getByTestId('approval-destination')).toContainText('e2e/')
    expect(await countVaultFiles(page)).toBe(initialVaultFiles)

    await page.getByLabel(/Transition reason/).fill('ready')
    await page.getByRole('button', { name: 'Accept for review' }).click()
    await expect(page.getByText(/is not published yet/)).toBeVisible()
    expect(await countVaultFiles(page)).toBe(initialVaultFiles)

    let approvalRequests = 0
    page.on('request', (request) => {
      if (request.method() === 'POST' && request.url().endsWith('/approve')) {
        approvalRequests += 1
      }
    })
    await page.getByRole('button', { name: 'Approve to vault' }).click()
    const dialog = page.getByRole('dialog', { name: 'Confirm canonical approval' })
    await expect(dialog).toContainText('Candidate')
    await expect(dialog).toContainText('Revision')
    await expect(dialog).toContainText('Lesson ID')
    await expect(dialog).toContainText('Canonical path')
    await dialog.getByRole('button', { name: 'Cancel' }).click()
    await expect(dialog).toHaveCount(0)
    expect(approvalRequests).toBe(0)

    await page.getByRole('button', { name: 'Approve to vault' }).click()
    await page.getByRole('button', { name: 'Confirm approval' }).click()
    await expect(page.getByTestId('approval-result')).toContainText('created')
    await expect(page.getByText(/Lesson read back:/)).toBeVisible()
    await expect(page.getByText(/Vault file read back:/)).toBeVisible()
    expect(approvalRequests).toBe(1)
    expect(await countVaultFiles(page)).toBe(initialVaultFiles + 1)

    const lessons = await page.request.get('/lessons?limit=50')
    expect(lessons.ok()).toBeTruthy()
    expect(((await lessons.json()) as unknown[]).length).toBe(initialVaultFiles + 1)
  })

  test('Markdown file can be staged and a rejected candidate remains visible', async ({ page }) => {
    await page.goto('/app/#/tritalele')
    const initialVaultFiles = await countVaultFiles(page)

    await ingestionRegion(page).getByLabel('Markdown or text file').setInputFiles({
      name: 'file-input.md',
      mimeType: 'text/markdown',
      buffer: Buffer.from('# File input\n\nCandidate rejected but retained.'),
    })
    await expect(ingestionRegion(page).getByLabel('Content format')).toHaveValue('markdown')
    await expect(ingestionRegion(page).getByLabel('Source name')).toHaveValue('file-input.md')
    await page.getByRole('button', { name: 'Create preview' }).click()
    await expect(page.getByTestId('ingestion-preview')).toBeVisible()
    await page.getByRole('button', { name: 'Add to collection' }).click()
    await expect(page.getByText(/Staging completed/)).toBeVisible()

    await page.locator('.candidate-card').filter({ hasText: 'file-input.md' }).click()
    await page.getByLabel(/Transition reason/).fill('not useful for the vault')
    await page.getByRole('button', { name: 'Reject candidate' }).click()
    await expect(page.getByText(/remains in staging/)).toBeVisible()
    await expect(page.locator('.candidate-card').filter({ hasText: 'file-input.md' })).toBeVisible()
    await expect(page.getByText('Rejected → Rejected')).toHaveCount(0)
    await expect(page.getByText('Staged → Rejected')).toBeVisible()
    await expect(page.getByText('not useful for the vault')).toBeVisible()
    expect(await countVaultFiles(page)).toBe(initialVaultFiles)
  })

  test('409, 422, 503 and obsolete preview responses are controlled', async ({ page }) => {
    await page.goto('/app/#/tritalele')
    await ingestionRegion(page).getByLabel('Source name').fill('controlled-errors.txt')
    await ingestionRegion(page).getByLabel('Source text').fill('Valid input used to exercise controlled HTTP errors.')

    const previewUrl = '**/api/v1/tritalele/ingestion/preview'
    await page.route(previewUrl, (route) =>
      route.fulfill({
        status: 409,
        contentType: 'application/json',
        body: JSON.stringify({ detail: { code: 'ingestion_conflict', message: 'Conflict.' } }),
      }),
    )
    await page.getByRole('button', { name: 'Create preview' }).click()
    await expect(page.getByText(/Conflict \(409 · ingestion_conflict\)/)).toBeVisible()
    await page.unroute(previewUrl)

    await page.route(previewUrl, (route) =>
      route.fulfill({
        status: 422,
        contentType: 'application/json',
        body: JSON.stringify({ detail: [{ loc: ['body'], msg: 'invalid', type: 'value_error' }] }),
      }),
    )
    await page.getByRole('button', { name: 'Create preview' }).click()
    await expect(page.getByText(/Invalid data \(422\)/)).toBeVisible()
    await page.unroute(previewUrl)

    await page.route(previewUrl, (route) =>
      route.fulfill({
        status: 503,
        contentType: 'application/json',
        body: JSON.stringify({
          detail: { code: 'candidate_storage_unavailable', message: 'Unavailable.' },
        }),
      }),
    )
    await page.getByRole('button', { name: 'Create preview' }).click()
    await expect(page.getByText(/Operational error \(503 · candidate_storage_unavailable\)/)).toBeVisible()
    await page.unroute(previewUrl)

    await page.route(previewUrl, async (route) => {
      await new Promise((resolve) => setTimeout(resolve, 300))
      await route.continue()
    })
    await page.getByRole('button', { name: 'Create preview' }).click()
    await ingestionRegion(page).getByLabel('Source text').fill('Changed while the preview request is still running.')
    await page.waitForTimeout(500)
    await expect(page.getByTestId('ingestion-preview')).toHaveCount(0)
    await expect(page.getByRole('button', { name: 'Add to collection' })).toBeDisabled()
    await page.unroute(previewUrl)
  })

  test('partial_refresh is reported as persisted with separate read-backs', async ({ page }) => {
    const staged = await stageAccepted(page.request, 'partial-refresh.txt')
    await page.route(`**/candidates/${encodeURIComponent(staged.candidateId)}/approve`, (route) =>
      route.fulfill({
        status: 503,
        contentType: 'application/json',
        body: JSON.stringify({
          detail: {
            code: 'partial_refresh',
            message: 'Projection refresh failed.',
            recovery: {
              partial_approval_result: {
                candidate_id: staged.candidateId,
                candidate_revision: staged.revision + 1,
                lesson_id: staged.lessonId,
                relative_vault_path: staged.path,
                vault_write_outcome: 'created',
                candidate_state_changed: true,
                refresh_outcome: { refreshed: false },
              },
              canonical_lesson_persisted: true,
              candidate_approval_persisted: true,
              projection_refreshed: false,
            },
          },
        }),
      }),
    )

    await page.goto('/app/#/tritalele')
    await page.locator('.candidate-card').filter({ hasText: 'partial-refresh.txt' }).click()
    await page.getByRole('button', { name: 'Approve to vault' }).click()
    await page.getByRole('button', { name: 'Confirm approval' }).click()
    await expect(page.getByText(/partial_refresh/).first()).toBeVisible()
    await expect(page.getByText('Recovery details')).toBeVisible()
    await expect(page.getByLabel('Approval read-back')).toBeVisible()
  })
})
