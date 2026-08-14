import { test, expect } from '@playwright/test'
import { mkdir, readFile, rm, writeFile } from 'node:fs/promises'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'

const repositoryRoot = fileURLToPath(new URL('../..', import.meta.url))
const fixtureRoot = join(repositoryRoot, '.e2e-fixture')

function lesson(id: string, title: string, body: string): string {
  return ['---', `id: ${id}`, 'topic: transfer', 'source: e2e', 'importance: 3', 'tags: [transfer]', "date: '2026-08-12'", `title: ${title}`, '---', body, ''].join('\n')
}

test('previews and merges an explicit A -> B selection without switching the active Vault', async ({ page, request }) => {
  const active = await (await request.get('/vault/status')).json() as { vault_id: string, vault_dir: string, display_name: string }
  const vaultA = active.vault_dir
  const vaultB = join(fixtureRoot, 'issue-193-vault-b')
  const vaultC = join(fixtureRoot, 'issue-193-vault-c')
  const sourcePath = join(vaultA, 'issue-193', 'clean.md')
  const sourceBytes = Buffer.from(lesson('issue-193/clean', 'Issue 193 clean', 'Clean merge body.'))
  await mkdir(join(vaultA, 'issue-193'), { recursive: true })
  await writeFile(sourcePath, sourceBytes)
  await mkdir(vaultB, { recursive: true })
  await mkdir(vaultC, { recursive: true })
  let vaultBId = ''
  let vaultCId = ''

  try {
    const registeredB = await request.post('/vaults/register', { data: { name: 'Issue 193 Destination', path: vaultB } })
    expect(registeredB.status()).toBe(201)
    vaultBId = (await registeredB.json()).id as string
    const registeredC = await request.post('/vaults/register', { data: { name: 'Issue 193 Other', path: vaultC } })
    expect(registeredC.status()).toBe(201)
    vaultCId = (await registeredC.json()).id as string

    await page.goto('/app/#/vault')
    const transfer = page.locator('section.vault-management').filter({ has: page.getByRole('heading', { name: 'Vault-to-Vault transfer' }) })
    await expect(transfer).toBeVisible()
    await expect(transfer.getByLabel('Source Vault')).toHaveValue(active.vault_id)
    await transfer.getByLabel('Destination Vault').selectOption(vaultBId)
    await expect(transfer.getByLabel('Vault transfer direction')).toContainText(`${active.display_name} → Issue 193 Destination`)
    const checkbox = transfer.getByRole('checkbox', { name: /issue-193\/clean/ })
    await checkbox.check()
    await expect(transfer.getByRole('button', { name: 'Execute transfer' })).toHaveCount(0)
    await transfer.getByRole('button', { name: 'Validate and preview transfer' }).click()
    await expect(transfer.getByRole('heading', { name: 'Transfer preview' })).toBeVisible()
    await expect(transfer).toContainText('New')

    await transfer.getByLabel('Destination Vault').selectOption(vaultCId)
    await expect(transfer.getByRole('heading', { name: 'Transfer preview' })).toHaveCount(0)
    await transfer.getByLabel('Destination Vault').selectOption(vaultBId)
    await transfer.getByRole('button', { name: 'Validate and preview transfer' }).click()
    await transfer.getByRole('button', { name: 'Execute transfer' }).click()
    await expect(transfer.getByText('Transfer completed.', { exact: true })).toBeVisible()

    expect(await readFile(sourcePath)).toEqual(sourceBytes)
    expect(await readFile(join(vaultB, 'issue-193', 'clean.md'))).toEqual(sourceBytes)
    expect((await (await request.get('/vault/status')).json()).vault_id).toBe(active.vault_id)

    await transfer.getByLabel('Operation').selectOption('move')
    await expect(transfer.getByText('Move deletes each source lesson only after its destination canonical success.')).toBeVisible()
  } finally {
    if (vaultCId) expect((await request.delete(`/vaults/${vaultCId}`)).status()).toBe(204)
    if (vaultBId) expect((await request.delete(`/vaults/${vaultBId}`)).status()).toBe(204)
    await rm(join(vaultA, 'issue-193'), { recursive: true, force: true })
    await rm(vaultB, { recursive: true, force: true })
    await rm(vaultC, { recursive: true, force: true })
    if (vaultBId) {
      await rm(join(fixtureRoot, 'data', 'vaults', vaultBId), { recursive: true, force: true })
      await rm(join(fixtureRoot, 'cache', 'vaults', vaultBId), { recursive: true, force: true })
    }
    if (vaultCId) {
      await rm(join(fixtureRoot, 'data', 'vaults', vaultCId), { recursive: true, force: true })
      await rm(join(fixtureRoot, 'cache', 'vaults', vaultCId), { recursive: true, force: true })
    }
  }
})

test('conflicts cannot overwrite, resolution requires a new preview, stale async preview is discarded, and IT terminology is complete', async ({ page, request }) => {
  const active = await (await request.get('/vault/status')).json() as { vault_id: string, vault_dir: string }
  const vaultA = active.vault_dir
  const vaultB = join(fixtureRoot, 'issue-193-conflict-b')
  const vaultC = join(fixtureRoot, 'issue-193-conflict-c')
  const sourcePath = join(vaultA, 'issue-193-conflict', 'same-id.md')
  const sourceBytes = Buffer.from(lesson('issue-193/conflict', 'Source conflict', 'Source conflict body.'))
  const destinationBytes = Buffer.from(lesson('issue-193/conflict', 'Destination conflict', 'Destination must remain.'))
  await mkdir(join(vaultA, 'issue-193-conflict'), { recursive: true })
  await writeFile(sourcePath, sourceBytes)
  await mkdir(join(vaultB, 'elsewhere'), { recursive: true })
  await writeFile(join(vaultB, 'elsewhere', 'same-id.md'), destinationBytes)
  await mkdir(vaultC, { recursive: true })
  let vaultBId = ''
  let vaultCId = ''

  try {
    const registeredB = await request.post('/vaults/register', { data: { name: 'Conflict Destination', path: vaultB } })
    expect(registeredB.status()).toBe(201)
    vaultBId = (await registeredB.json()).id as string
    const registeredC = await request.post('/vaults/register', { data: { name: 'Async Destination', path: vaultC } })
    expect(registeredC.status()).toBe(201)
    vaultCId = (await registeredC.json()).id as string

    await page.goto('/app/#/vault')
    const transfer = page.locator('section.vault-management').filter({ has: page.getByRole('heading', { name: 'Vault-to-Vault transfer' }) })
    await transfer.getByLabel('Destination Vault').selectOption(vaultBId)
    await transfer.getByRole('checkbox', { name: /issue-193\/conflict/ }).check()
    await transfer.getByRole('button', { name: 'Validate and preview transfer' }).click()
    await expect(transfer).toContainText('Same ID')
    await transfer.getByLabel('Resolution').selectOption('keep_destination')
    await expect(transfer.getByRole('heading', { name: 'Transfer preview' })).toHaveCount(0)
    await expect(transfer.getByText('Resolution changed. Validate and preview again before executing.')).toBeVisible()
    await transfer.getByRole('button', { name: 'Validate and preview transfer' }).click()
    await transfer.getByRole('button', { name: 'Execute transfer' }).click()
    expect(await readFile(join(vaultB, 'elsewhere', 'same-id.md'))).toEqual(destinationBytes)

    await transfer.getByLabel('Destination Vault').selectOption(vaultBId)
    await transfer.getByRole('checkbox', { name: /issue-193\/conflict/ }).check()

    let releasePreview: (() => void) | undefined
    let previewInterceptedResolve: (() => void) | undefined
    const previewIntercepted = new Promise<void>((resolve) => { previewInterceptedResolve = resolve })
    const release = new Promise<void>((resolve) => { releasePreview = resolve })
    await page.route('**/vault-transfers/preview', async (route) => {
      previewInterceptedResolve?.()
      await release
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          plan_digest: 'a'.repeat(64), operation: 'merge', source_vault_id: active.vault_id,
          source_name: 'stale source', source_path: vaultA, destination_vault_id: vaultBId,
          destination_name: 'stale destination', destination_path: vaultB,
          items: [{ lesson_id: 'issue-193/conflict', source_path: 'issue-193-conflict/same-id.md', source_sha256: 'a'.repeat(64), destination_path: 'elsewhere/same-id.md', destination_sha256: 'b'.repeat(64), classification: 'same_id', resolution: 'keep_destination', duplicate_lesson_ids: [] }],
        }),
      })
    })
    await transfer.getByRole('button', { name: 'Validate and preview transfer' }).click()
    await previewIntercepted
    await transfer.getByLabel('Destination Vault').selectOption(vaultCId)
    releasePreview?.()
    await expect(transfer.getByRole('heading', { name: 'Transfer preview' })).toHaveCount(0)
    await page.unroute('**/vault-transfers/preview')

    await page.addInitScript(() => localStorage.setItem('lele-manager.locale', 'it'))
    await page.reload()
    const italian = page.locator('section.vault-management').filter({ has: page.getByRole('heading', { name: 'Trasferimento Vault-a-Vault' }) })
    await expect(italian.getByLabel('Vault sorgente')).toBeVisible()
    await expect(italian.getByLabel('Vault destinazione')).toBeVisible()
    await expect(italian.getByLabel('Operazione')).toContainText('Accorpa')
    await expect(italian.getByLabel('Operazione')).toContainText('Copia')
    await expect(italian.getByLabel('Operazione')).toContainText('Sposta')
  } finally {
    await page.unroute('**/vault-transfers/preview').catch(() => undefined)
    if (vaultCId) expect((await request.delete(`/vaults/${vaultCId}`)).status()).toBe(204)
    if (vaultBId) expect((await request.delete(`/vaults/${vaultBId}`)).status()).toBe(204)
    await rm(join(vaultA, 'issue-193-conflict'), { recursive: true, force: true })
    await rm(vaultB, { recursive: true, force: true })
    await rm(vaultC, { recursive: true, force: true })
    if (vaultBId) {
      await rm(join(fixtureRoot, 'data', 'vaults', vaultBId), { recursive: true, force: true })
      await rm(join(fixtureRoot, 'cache', 'vaults', vaultBId), { recursive: true, force: true })
    }
    if (vaultCId) {
      await rm(join(fixtureRoot, 'data', 'vaults', vaultCId), { recursive: true, force: true })
      await rm(join(fixtureRoot, 'cache', 'vaults', vaultCId), { recursive: true, force: true })
    }
  }
})
