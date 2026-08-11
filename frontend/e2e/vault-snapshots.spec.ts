import { test, expect } from '@playwright/test'
import { mkdir, readFile, rm, writeFile } from 'node:fs/promises'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'

const repositoryRoot = fileURLToPath(new URL('../..', import.meta.url))
const fixtureRoot = join(repositoryRoot, '.e2e-fixture')

function lesson(id: string, title: string, body: string): string {
  return ['---', `id: ${id}`, 'topic: snapshots', 'source: e2e', 'importance: 3', 'tags: [snapshot]', "date: '2026-08-11'", `title: ${title}`, '---', body, ''].join('\n')
}

test('snapshots an explicit Vault and restores it into another Vault only after preview and confirmation', async ({ page, request }) => {
  const active = await (await request.get('/vault/status')).json() as { vault_id: string, vault_dir: string, display_name: string }
  const targetName = `Snapshot target B ${test.info().retry}`
  const vaultB = join(fixtureRoot, `vault-snapshot-b-${test.info().retry}`)
  await mkdir(join(active.vault_dir, 'snapshots'), { recursive: true })
  const sourcePath = join(active.vault_dir, 'snapshots', 'source.md')
  await writeFile(sourcePath, lesson('snapshots/source', 'Source snapshot', 'A stays untouched.'))
  await mkdir(join(vaultB, 'snapshots'), { recursive: true })
  const targetPath = join(vaultB, 'snapshots', 'target.md')
  await writeFile(targetPath, lesson('snapshots/target', 'Target before restore', 'B is replaced.'))

  try {
    expect((await request.post('/vault/import')).ok()).toBeTruthy()
    const registered = await request.post('/vaults/register', { data: { name: targetName, path: vaultB } })
    expect(registered.status()).toBe(201)
    const vaultBId = (await registered.json()).id as string

    await page.goto('/app/#/vault')
    await expect(page.getByRole('region', { name: 'Vault', exact: true })).toBeVisible()
    const activeRow = page.locator('.vault-row').filter({ has: page.getByText(active.display_name, { exact: true }) })
    const downloadPromise = page.waitForEvent('download')
    await activeRow.getByRole('button', { name: 'Create snapshot' }).click()
    const download = await downloadPromise
    expect(download.suggestedFilename()).toBe(`lele-vault-${active.vault_id}.snapshot.zip`)
    const downloadedPath = await download.path()
    expect(downloadedPath).not.toBeNull()
    const artifact = await readFile(downloadedPath!)
    expect(artifact.subarray(0, 2).toString()).toBe('PK')
    await expect(page.getByText('Snapshot downloaded for')).toBeVisible()
    await expect(page.getByTestId('shell-workspace')).toHaveText(active.display_name)

    await page.getByLabel('Snapshot file').setInputFiles({ name: download.suggestedFilename(), mimeType: 'application/zip', buffer: artifact })
    await page.getByLabel('Restore target Vault').selectOption(vaultBId)
    const restoreButton = page.getByRole('button', { name: 'Restore exact managed state' })
    await expect(restoreButton).toHaveCount(0)
    await page.getByRole('button', { name: 'Validate and preview restore' }).click()
    await expect(page.getByRole('heading', { name: 'Restore preview' })).toBeVisible()
    await expect(page.getByText(`Target: ${targetName} (${vaultBId}) at ${vaultB}`)).toBeVisible()
    await expect(page.getByText('snapshots/target.md')).toBeVisible()
    await page.getByLabel('Type the target Vault name to confirm').fill('wrong target')
    await expect(restoreButton).toBeDisabled()
    expect((await readFile(targetPath)).toString()).toContain('B is replaced.')
    await page.getByLabel('Type the target Vault name to confirm').fill(targetName)
    await expect(restoreButton).toBeEnabled()
    await restoreButton.click()
    await expect(page.getByText('Canonical Vault state was restored and derived data was reconciled.')).toBeVisible()
    expect((await readFile(join(vaultB, 'snapshots', 'source.md'))).toString()).toContain('A stays untouched.')
    await expect(page.getByTestId('shell-workspace')).toHaveText(active.display_name)
    expect((await readFile(sourcePath)).toString()).toContain('A stays untouched.')

    await page.getByLabel('Snapshot file').setInputFiles({ name: 'malformed.zip', mimeType: 'application/zip', buffer: Buffer.from('not a zip') })
    await page.getByRole('button', { name: 'Validate and preview restore' }).click()
    await expect(page.getByText('snapshot artifact is not a valid ZIP archive')).toBeVisible()
    expect((await readFile(join(vaultB, 'snapshots', 'source.md'))).toString()).toContain('A stays untouched.')

    expect((await request.post(`/vaults/${active.vault_id}/activate`)).ok()).toBeTruthy()
    expect((await request.delete(`/vaults/${vaultBId}`)).status()).toBe(204)
  } finally {
    await rm(join(active.vault_dir, 'snapshots'), { recursive: true, force: true })
    await rm(vaultB, { recursive: true, force: true })
  }
})

test('localizes snapshot and restore controls in Italian', async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem('lele-manager.locale', 'it'))
  await page.goto('/app/#/vault')
  await expect(page.getByRole('region', { name: 'Vault', exact: true })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Snapshot e ripristino' })).toBeVisible()
  await expect(page.getByLabel('File snapshot')).toBeVisible()
  await expect(page.getByRole('button', { name: 'Valida e mostra anteprima del ripristino' })).toBeVisible()
})
