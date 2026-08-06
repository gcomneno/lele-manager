import { test, expect, type APIRequestContext, type Page } from '@playwright/test'

const API = '/api/v1/tritalele'

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
    await expect(page.getByRole('heading', { name: 'Raccogli nuove LeLe' })).toBeVisible()
    await expect(page.getByText('Nessuna selezione.')).toBeVisible()

    const initialVaultFiles = await countVaultFiles(page)

    await page.getByLabel('Nome della fonte').fill('pasted-happy-path.txt')
    const source = page.getByLabel('Testo sorgente')
    await source.fill('Plain text incollato per il workflow TritaLeLe deterministico.')
    await page.getByRole('button', { name: 'Crea anteprima' }).click()
    await expect(page.getByTestId('ingestion-preview')).toBeVisible()
    await expect(page.getByRole('button', { name: 'Aggiungi alla raccolta' })).toBeEnabled()

    await source.fill('Plain text incollato modificato: la preview precedente non è più valida.')
    await expect(page.getByTestId('ingestion-preview')).toHaveCount(0)
    await expect(page.getByRole('button', { name: 'Aggiungi alla raccolta' })).toBeDisabled()

    await page.getByRole('button', { name: 'Crea anteprima' }).click()
    await page.getByRole('button', { name: 'Aggiungi alla raccolta' }).click()
    await expect(page.getByText(/Staging completato: 1 created/)).toBeVisible()
    expect(await countVaultFiles(page)).toBe(initialVaultFiles)

    await page.locator('.candidate-card').filter({ hasText: 'pasted-happy-path.txt' }).click()
    await expect(page.getByRole('heading', { name: 'Dettaglio della LeLe' })).toBeVisible()
    await page.getByLabel('Testo proposto').fill(
      'Testo rivisto in Markdown con **contenuto canonico** e provenienza intatta.',
    )
    await page.getByLabel('Topic', { exact: true }).fill('e2e')
    await page.getByLabel('Source', { exact: true }).fill('playwright')
    await page.getByLabel('Importance', { exact: true }).fill('4')
    await page.getByLabel('Date', { exact: true }).fill('2026-07-22')
    await page.getByLabel('Tags', { exact: true }).fill('e2e, tritalele')
    await page.getByLabel('Title', { exact: true }).fill('TritaLeLe approval')
    await page.getByLabel('Motivo revisione (opzionale)').fill('editorial pass')
    await page.getByRole('button', { name: 'Salva revisione' }).click()
    await expect(page.getByText(/Revisione 1 salvata/)).toBeVisible()
    await expect(page.getByTestId('approval-destination')).toContainText('e2e/')
    expect(await countVaultFiles(page)).toBe(initialVaultFiles)

    await page.getByLabel(/Motivo transizione/).fill('ready')
    await page.getByRole('button', { name: 'Accetta per revisione' }).click()
    await expect(page.getByText(/non è ancora pubblicato/)).toBeVisible()
    expect(await countVaultFiles(page)).toBe(initialVaultFiles)

    let approvalRequests = 0
    page.on('request', (request) => {
      if (request.method() === 'POST' && request.url().endsWith('/approve')) {
        approvalRequests += 1
      }
    })
    await page.getByRole('button', { name: 'Approva nel vault' }).click()
    const dialog = page.getByRole('dialog', { name: 'Conferma approvazione canonica' })
    await expect(dialog).toContainText('Candidato')
    await expect(dialog).toContainText('Revisione')
    await expect(dialog).toContainText('Lesson ID')
    await expect(dialog).toContainText('Path canonico')
    await dialog.getByRole('button', { name: 'Annulla' }).click()
    await expect(dialog).toHaveCount(0)
    expect(approvalRequests).toBe(0)

    await page.getByRole('button', { name: 'Approva nel vault' }).click()
    await page.getByRole('button', { name: 'Conferma approvazione' }).click()
    await expect(page.getByTestId('approval-result')).toContainText('created')
    await expect(page.getByText(/Lesson riletta:/)).toBeVisible()
    await expect(page.getByText(/File vault riletto:/)).toBeVisible()
    expect(approvalRequests).toBe(1)
    expect(await countVaultFiles(page)).toBe(initialVaultFiles + 1)

    const lessons = await page.request.get('/lessons?limit=50')
    expect(lessons.ok()).toBeTruthy()
    expect(((await lessons.json()) as unknown[]).length).toBe(initialVaultFiles + 1)
  })

  test('Markdown file can be staged and a rejected candidate remains visible', async ({ page }) => {
    await page.goto('/app/#/tritalele')
    const initialVaultFiles = await countVaultFiles(page)

    await page.getByLabel('File Markdown o testo').setInputFiles({
      name: 'file-input.md',
      mimeType: 'text/markdown',
      buffer: Buffer.from('# File input\n\nCandidate rejected but retained.'),
    })
    await expect(page.getByLabel('Formato del contenuto')).toHaveValue('markdown')
    await expect(page.getByLabel('Nome della fonte')).toHaveValue('file-input.md')
    await page.getByRole('button', { name: 'Crea anteprima' }).click()
    await expect(page.getByTestId('ingestion-preview')).toBeVisible()
    await page.getByRole('button', { name: 'Aggiungi alla raccolta' }).click()
    await expect(page.getByText(/Staging completato: 1 created/)).toBeVisible()

    await page.locator('.candidate-card').filter({ hasText: 'file-input.md' }).click()
    await page.getByLabel(/Motivo transizione/).fill('not useful for the vault')
    await page.getByRole('button', { name: 'Rifiuta candidato' }).click()
    await expect(page.getByText(/resta nello staging/)).toBeVisible()
    await expect(page.locator('.candidate-card').filter({ hasText: 'file-input.md' })).toBeVisible()
    await expect(page.getByText('rejected → rejected')).toHaveCount(0)
    await expect(page.getByText('staged → rejected')).toBeVisible()
    await expect(page.getByText('not useful for the vault')).toBeVisible()
    expect(await countVaultFiles(page)).toBe(initialVaultFiles)
  })

  test('409, 422, 503 and obsolete preview responses are controlled', async ({ page }) => {
    await page.goto('/app/#/tritalele')
    await page.getByLabel('Nome della fonte').fill('controlled-errors.txt')
    await page.getByLabel('Testo sorgente').fill('Valid input used to exercise controlled HTTP errors.')

    const previewUrl = '**/api/v1/tritalele/ingestion/preview'
    await page.route(previewUrl, (route) =>
      route.fulfill({
        status: 409,
        contentType: 'application/json',
        body: JSON.stringify({ detail: { code: 'ingestion_conflict', message: 'Conflict.' } }),
      }),
    )
    await page.getByRole('button', { name: 'Crea anteprima' }).click()
    await expect(page.getByText(/Conflitto \(409 · ingestion_conflict\)/)).toBeVisible()
    await page.unroute(previewUrl)

    await page.route(previewUrl, (route) =>
      route.fulfill({
        status: 422,
        contentType: 'application/json',
        body: JSON.stringify({ detail: [{ loc: ['body'], msg: 'invalid', type: 'value_error' }] }),
      }),
    )
    await page.getByRole('button', { name: 'Crea anteprima' }).click()
    await expect(page.getByText(/Dati non validi \(422\)/)).toBeVisible()
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
    await page.getByRole('button', { name: 'Crea anteprima' }).click()
    await expect(page.getByText(/Errore operativo \(503 · candidate_storage_unavailable\)/)).toBeVisible()
    await page.unroute(previewUrl)

    await page.route(previewUrl, async (route) => {
      await new Promise((resolve) => setTimeout(resolve, 300))
      await route.continue()
    })
    await page.getByRole('button', { name: 'Crea anteprima' }).click()
    await page.getByLabel('Testo sorgente').fill('Changed while the preview request is still running.')
    await page.waitForTimeout(500)
    await expect(page.getByTestId('ingestion-preview')).toHaveCount(0)
    await expect(page.getByRole('button', { name: 'Aggiungi alla raccolta' })).toBeDisabled()
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
    await page.getByRole('button', { name: 'Approva nel vault' }).click()
    await page.getByRole('button', { name: 'Conferma approvazione' }).click()
    await expect(page.getByText(/partial_refresh/).first()).toBeVisible()
    await expect(page.getByText('Dettagli di recupero')).toBeVisible()
    await expect(page.getByLabel('Read-back approvazione')).toBeVisible()
  })
})
