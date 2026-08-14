import { test, expect } from '@playwright/test'
import { mkdir, readFile, rm, writeFile } from 'node:fs/promises'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'

const repositoryRoot = fileURLToPath(new URL('../..', import.meta.url))
const fixtureRoot = join(repositoryRoot, '.e2e-fixture')

function lesson(id: string, body: string): string {
  return ['---', `id: ${id}`, 'topic: danger', 'source: e2e', 'importance: 3', 'tags: [danger]', "date: '2026-08-14'", `title: ${id}`, '---', body, ''].join('\n')
}

test('System Danger zone previews and empties an explicit Vault without changing active Vault', async ({ page, request }) => {
  const active = await (await request.get('/vault/status')).json() as { vault_id: string }
  const vaultB = join(fixtureRoot, 'issue-194-empty-b')
  const lessonPath = join(vaultB, 'danger', 'one.md')
  await mkdir(join(vaultB, 'danger'), { recursive: true })
  await writeFile(lessonPath, lesson('danger/one', 'Empty me.'))
  let vaultBId = ''

  try {
    const registered = await request.post('/vaults/register', { data: { name: 'Issue 194 Empty', path: vaultB } })
    expect(registered.status()).toBe(201)
    vaultBId = (await registered.json()).id as string

    await page.goto('/app/#/ops')
    const danger = page.locator('section.danger-zone')
    await expect(danger.getByRole('heading', { name: 'Danger zone' })).toBeVisible()
    await danger.getByLabel('Target Vault').selectOption(vaultBId)
    await danger.getByLabel('Destructive operation').selectOption('empty')
    await danger.getByRole('button', { name: 'Validate and preview' }).click()

    await expect(danger.getByRole('heading', { name: 'Destructive preview' })).toBeVisible()
    await expect(danger).toContainText('Issue 194 Empty')
    await expect(danger).toContainText('1 approved lessons')
    const execute = danger.getByRole('button', { name: 'Execute destructive operation' })
    await expect(execute).toBeDisabled()

    await danger.getByLabel(/Type exactly/).fill('EMPTY Issue 194 Empty')
    await expect(execute).toBeEnabled()
    await execute.click()
    await expect(danger.getByText(/Destructive operation completed\./)).toBeVisible()

    await expect.poll(async () => (await readFile(lessonPath).catch(() => null))).toBeNull()
    expect((await (await request.get('/vault/status')).json()).vault_id).toBe(active.vault_id)
    const vaults = await (await request.get('/vaults')).json() as Array<{ id: string }>
    expect(vaults.some((vault) => vault.id === vaultBId)).toBe(true)
  } finally {
    if (vaultBId) {
      const vaults = await (await request.get('/vaults')).json().catch(() => []) as Array<{ id: string }>
      if (vaults.some((vault) => vault.id === vaultBId)) await request.delete(`/vaults/${vaultBId}`)
    }
    await rm(vaultB, { recursive: true, force: true })
  }
})

test('merge-and-delete source requires exact destination proof and removes only the inactive source', async ({ page, request }) => {
  const active = await (await request.get('/vault/status')).json() as { vault_id: string, vault_dir: string }
  const sourceVault = join(fixtureRoot, 'issue-194-merge-source')
  const sourcePath = join(sourceVault, 'danger', 'shared.md')
  const destinationPath = join(active.vault_dir, 'danger', 'issue-194-shared.md')
  const bytes = Buffer.from(lesson('danger/issue-194-shared', 'Already merged exactly.'))
  await mkdir(join(sourceVault, 'danger'), { recursive: true })
  await mkdir(join(active.vault_dir, 'danger'), { recursive: true })
  await writeFile(sourcePath, bytes)
  await writeFile(destinationPath, bytes)
  let sourceId = ''

  try {
    const registered = await request.post('/vaults/register', { data: { name: 'Issue 194 Source', path: sourceVault } })
    expect(registered.status()).toBe(201)
    sourceId = (await registered.json()).id as string

    await page.goto('/app/#/ops')
    const danger = page.locator('section.danger-zone')
    await danger.getByLabel('Target Vault').selectOption(sourceId)
    await danger.getByLabel('Destructive operation').selectOption('merge_delete_source')
    await danger.getByLabel('Verified destination Vault').selectOption(active.vault_id)
    await danger.getByRole('button', { name: 'Validate and preview' }).click()

    await expect(danger.getByText(/Every source lesson is already present/)).toBeVisible()
    await danger.getByLabel(/Type exactly/).fill('DELETE Issue 194 Source')
    await danger.getByRole('button', { name: 'Execute destructive operation' }).click()
    await expect(danger.getByText(/Destructive operation completed\./)).toBeVisible()

    await expect.poll(async () => (await readFile(sourcePath).catch(() => null))).toBeNull()
    await expect.poll(async () => (await request.get('/vaults')).json()).not.toContainEqual(expect.objectContaining({ id: sourceId }))
    expect(await readFile(destinationPath)).toEqual(bytes)
    expect((await (await request.get('/vault/status')).json()).vault_id).toBe(active.vault_id)
  } finally {
    if (sourceId) {
      const vaults = await (await request.get('/vaults')).json().catch(() => []) as Array<{ id: string }>
      if (vaults.some((vault) => vault.id === sourceId)) await request.delete(`/vaults/${sourceId}`)
    }
    await rm(sourceVault, { recursive: true, force: true })
    await rm(destinationPath, { force: true })
    await rm(join(active.vault_dir, 'danger'), { recursive: false, force: true }).catch(() => undefined)
  }
})
