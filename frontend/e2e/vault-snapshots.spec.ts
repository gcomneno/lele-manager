import { test, expect, type APIRequestContext } from '@playwright/test'
import { mkdir, readFile, rm, rmdir, writeFile } from 'node:fs/promises'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'

const repositoryRoot = fileURLToPath(new URL('../..', import.meta.url))
const fixtureRoot = join(repositoryRoot, '.e2e-fixture')

function lesson(id: string, title: string, body: string): string {
  return ['---', `id: ${id}`, 'topic: snapshots', 'source: e2e', 'importance: 3', 'tags: [snapshot]', "date: '2026-08-11'", `title: ${title}`, '---', body, ''].join('\n')
}

async function cleanupRegisteredVault(
  request: APIRequestContext,
  originalVaultId: string,
  registeredVaultId: string | undefined,
  vaultDir: string,
): Promise<void> {
  try {
    if (registeredVaultId) {
      expect((await request.post(`/vaults/${originalVaultId}/activate`)).ok()).toBeTruthy()
    }
  } finally {
    try {
      if (registeredVaultId) {
        expect((await request.delete(`/vaults/${registeredVaultId}`)).status()).toBe(204)
      }
    } finally {
      await rm(vaultDir, { recursive: true, force: true })
    }
  }
}

test('snapshots an explicit Vault and restores it into another Vault only after preview and confirmation', async ({ page, request }) => {
  const active = await (await request.get('/vault/status')).json() as { vault_id: string, vault_dir: string, display_name: string }
  const targetName = `Snapshot target B ${test.info().retry}`
  const vaultB = join(fixtureRoot, `vault-snapshot-b-${test.info().retry}`)
  const sourceDirectory = join(active.vault_dir, 'snapshots')
  const sourcePath = join(active.vault_dir, 'snapshots', 'source.md')
  const targetPath = join(vaultB, 'snapshots', 'target.md')
  const sourceBefore = await readFile(sourcePath).catch(() => null)
  const sourceDirectoryCreated = (await mkdir(sourceDirectory, { recursive: true })) !== undefined
  let vaultBId: string | undefined

  try {
    await writeFile(sourcePath, lesson('snapshots/source', 'Source snapshot', 'A stays untouched.'))
    await mkdir(join(vaultB, 'snapshots'), { recursive: true })
    await writeFile(targetPath, lesson('snapshots/target', 'Target before restore', 'B is replaced.'))
    expect((await request.post('/vault/import')).ok()).toBeTruthy()
    const registered = await request.post('/vaults/register', { data: { name: targetName, path: vaultB } })
    expect(registered.status()).toBe(201)
    vaultBId = (await registered.json()).id as string

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

  } finally {
    try {
      await cleanupRegisteredVault(request, active.vault_id, vaultBId, vaultB)
    } finally {
      if (sourceBefore === null) await rm(sourcePath, { force: true })
      else await writeFile(sourcePath, sourceBefore)
      if (sourceDirectoryCreated) await rmdir(sourceDirectory)
    }
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

test('discards a stale restore preview when its target changes', async ({ page, request }) => {
  const active = await (await request.get('/vault/status')).json() as { vault_id: string, vault_dir: string, display_name: string }
  const vaultB = join(fixtureRoot, `vault-snapshot-race-b-${test.info().retry}`)
  const targetName = `Snapshot race B ${test.info().retry}`
  let vaultBId: string | undefined
  let releaseA: (() => void) | undefined
  const aDelayed = new Promise<void>((resolve) => { releaseA = resolve })
  const previewFor = (id: string, name: string) => ({
    plan_digest: 'a'.repeat(64), target_vault_id: id, target_name: name, target_path: `/vaults/${id}`,
    source_vault_id: active.vault_id, source_vault_name: active.display_name, canonical_file_count: 1,
    additions: [], replacements: [], removals: [], unchanged: ['snapshots/source.md'],
    editorial_state: ['candidate staging'], derived_effects: ['projection rebuilt'],
  })
  try {
    await mkdir(vaultB, { recursive: true })
    const registered = await request.post('/vaults/register', { data: { name: targetName, path: vaultB } })
    expect(registered.status()).toBe(201)
    vaultBId = (await registered.json()).id as string
    await page.route('**/restore/preview', async (route) => {
      const id = route.request().url().split('/vaults/')[1].split('/')[0]
      if (id === active.vault_id) await aDelayed
      await route.fulfill({ contentType: 'application/json', body: JSON.stringify(previewFor(id, id === vaultBId ? targetName : active.display_name)) })
    })
    await page.goto('/app/#/vault')
    await page.getByLabel('Snapshot file').setInputFiles({ name: 'snapshot.zip', mimeType: 'application/zip', buffer: Buffer.from('PK') })
    await page.getByRole('button', { name: 'Validate and preview restore' }).click()
    await page.getByLabel('Restore target Vault').selectOption(vaultBId)
    releaseA?.()
    await expect(page.getByRole('heading', { name: 'Restore preview' })).toHaveCount(0)
    await expect(page.getByRole('button', { name: 'Restore exact managed state' })).toHaveCount(0)
    await page.getByRole('button', { name: 'Validate and preview restore' }).click()
    await expect(page.getByRole('heading', { name: 'Restore preview' })).toBeVisible()
    await expect(page.getByText(`Target: ${targetName} (${vaultBId}) at /vaults/${vaultBId}`)).toBeVisible()
  } finally {
    releaseA?.()
    await page.unroute('**/restore/preview')
    await cleanupRegisteredVault(request, active.vault_id, vaultBId, vaultB)
  }
})
