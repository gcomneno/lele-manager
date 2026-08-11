import { test, expect } from '@playwright/test'
import { mkdir, readFile, rm, writeFile } from 'node:fs/promises'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'

const repositoryRoot = fileURLToPath(new URL('../..', import.meta.url))
const fixtureRoot = join(repositoryRoot, '.e2e-fixture')

function lesson(id: string, title: string, body: string): string {
  return ['---', `id: ${id}`, 'topic: shared', 'source: e2e', 'importance: 3', 'tags: [shared]', "date: '2026-08-11'", `title: ${title}`, '---', body, ''].join('\n')
}

test('keeps registry-backed Vault runtime state isolated across a switch', async ({ page, request }) => {
  const activeA = await (await request.get('/vault/status')).json() as { vault_id: string, vault_dir: string }
  const vaultA = activeA.vault_dir
  const vaultB = join(fixtureRoot, 'vault-b')
  const projectionA = join(fixtureRoot, 'data', 'vaults', activeA.vault_id, 'lessons.jsonl')
  const candidatesA = join(fixtureRoot, 'data', 'vaults', activeA.vault_id, 'candidates.json')
  const projectionBefore = await readFile(projectionA)
  const candidatesBefore = await readFile(candidatesA).catch(() => null)
  const aShared = lesson('shared/id', 'Shared from A', 'A-only shared lesson.')
  const bShared = lesson('shared/id', 'Shared from B', 'B-only shared lesson.')

  await mkdir(join(vaultA, 'shared'), { recursive: true })
  await writeFile(join(vaultA, 'shared', 'shared.md'), aShared)
  await writeFile(join(vaultA, 'shared', 'duplicate-a.md'), lesson('duplicate/a', 'Duplicate', 'Same duplicate text.'))
  await writeFile(join(vaultA, 'shared', 'duplicate-b.md'), lesson('duplicate/b', 'Duplicate', 'Same duplicate text.'))
  await mkdir(join(vaultB, 'shared'), { recursive: true })
  await writeFile(join(vaultB, 'shared', 'shared.md'), bShared)
  await writeFile(join(vaultB, 'shared', 'duplicate-c.md'), lesson('duplicate/c', 'Duplicate', 'Same duplicate text.'))
  await writeFile(join(vaultB, 'shared', 'duplicate-d.md'), lesson('duplicate/d', 'Duplicate', 'Same duplicate text.'))
  const bBytes = await readFile(join(vaultB, 'shared', 'shared.md'))

  try {
    expect((await request.post('/vault/import')).ok()).toBeTruthy()
    expect((await request.post('/api/v1/tritalele/ingestion/stage', { data: { content: 'Candidate belongs to A.', source_kind: 'plain_text', logical_name: 'a.txt', max_characters: 200 } })).ok()).toBeTruthy()
    const aPair = (await (await request.get('/duplicates?exact_only=true&limit=100')).json()).pairs.find((pair: { left_id: string }) => pair.left_id === 'duplicate/a')
    expect(aPair).toBeTruthy()
    expect((await request.post('/duplicates/not-duplicates', { data: aPair })).ok()).toBeTruthy()
    expect((await (await request.get('/duplicates?exact_only=true&limit=100')).json()).pairs).not.toContainEqual(aPair)

    const registered = await request.post('/vaults/register', { data: { name: 'Vault B Display', path: vaultB } })
    expect(registered.status()).toBe(201)
    const vaultBId = (await registered.json()).id as string
    expect(vaultBId).not.toBe(activeA.vault_id)
    await page.goto('/app/#/vault')
    const bRow = page.locator('.vault-row').filter({ hasText: 'Vault B Display' })
    await expect(bRow).toBeVisible()
    await bRow.getByRole('button', { name: 'Switch to Vault' }).click()
    await expect(page.getByTestId('shell-workspace')).toHaveText('Vault B Display')
    await expect(page.getByRole('region', { name: 'Vault', exact: true }).getByText('Vault B Display')).toBeVisible()
    await page.goto('/app/#/lesson/shared%2Fid')
    await expect(page.getByText('B-only shared lesson.')).toBeVisible()
    await expect(page.getByText('A-only shared lesson.')).toHaveCount(0)
    expect((await (await request.get('/api/v1/tritalele/candidates')).json()).count).toBe(0)
    expect((await (await request.get('/duplicates?exact_only=true&limit=100')).json()).total_pairs).toBeGreaterThan(0)
    expect(await readFile(join(vaultB, 'shared', 'shared.md'))).toEqual(bBytes)
    expect((await request.post(`/vaults/${activeA.vault_id}/activate`)).ok()).toBeTruthy()
    expect((await request.delete(`/vaults/${vaultBId}`)).status()).toBe(204)
    expect(await readFile(join(vaultB, 'shared', 'shared.md'))).toEqual(bBytes)
  } finally {
    await rm(join(vaultA, 'shared'), { recursive: true, force: true })
    await rm(vaultB, { recursive: true, force: true })
    await writeFile(projectionA, projectionBefore)
    if (candidatesBefore === null) await rm(candidatesA, { force: true })
    else await writeFile(candidatesA, candidatesBefore)
  }
})
