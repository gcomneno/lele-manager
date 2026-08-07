import { test, expect } from '@playwright/test'
import { mkdir, rm, symlink, writeFile } from 'node:fs/promises'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'

const repositoryRoot = fileURLToPath(new URL('../..', import.meta.url))
const fixtureRoot = join(repositoryRoot, '.e2e-fixture')
const vaultDir = join(fixtureRoot, 'vault')
const externalMarkdown = join(fixtureRoot, 'outside-vault.md')

const healthyLesson = `---
id: python/2025-01-01.e2e
topic: python
source: note
importance: 3
tags:
  - python
date: '2025-01-01'
title: E2E fixture
---
Healthy E2E vault lesson.
`

async function resetVaultFixture() {
  await rm(vaultDir, { recursive: true, force: true })
  await mkdir(join(vaultDir, 'python'), { recursive: true })
  await writeFile(join(vaultDir, 'python', '2025-01-01.e2e.md'), healthyLesson)
  await rm(externalMarkdown, { force: true })
}

async function openDoctor(page: import('@playwright/test').Page) {
  await page.goto('/app/#/ops')
  await expect(page.getByRole('heading', { name: 'Vault doctor' })).toBeVisible()
  await page.getByRole('button', { name: 'Run check' }).click()
}

test.describe('ops: vault doctor', () => {
  test.afterEach(async () => {
    await resetVaultFixture()
  })

  test('shows a healthy isolated vault report', async ({ page }) => {
    await resetVaultFixture()

    await openDoctor(page)

    await expect(page.getByText('Vault healthy')).toBeVisible()
    await expect(page.locator('.doctor .error')).toHaveCount(0)
    await expect(page.locator('.doctor').getByText('1 file checked')).toBeVisible()
  })

  test('groups malformed-frontmatter findings by diagnostic code', async ({ page }) => {
    await resetVaultFixture()
    await writeFile(join(vaultDir, 'python', 'a-malformed.md'), 'No frontmatter\n')
    await writeFile(join(vaultDir, 'python', 'b-malformed.md'), 'No frontmatter\n')

    await openDoctor(page)

    await expect(page.getByText('Vault not healthy')).toBeVisible()
    await expect(
      page.getByRole('heading', { name: 'missing_frontmatter (2 findings)' }),
    ).toBeVisible()
    await expect(page.getByText('python/a-malformed.md')).toBeVisible()
    await expect(page.getByText('python/b-malformed.md')).toBeVisible()
    await expect(page.getByText('frontmatter YAML assente')).toHaveCount(2)
    await expect(page.getByText('error', { exact: true })).toHaveCount(2)
  })

  test('surfaces an external symlink as an operational API error', async ({ page }) => {
    await resetVaultFixture()
    await writeFile(externalMarkdown, 'outside the vault\n')
    try {
      await symlink(externalMarkdown, join(vaultDir, 'python', 'escaping.md'))
    } catch (error) {
      if (
        typeof error === 'object' &&
        error !== null &&
        'code' in error &&
        (error.code === 'EPERM' || error.code === 'EACCES' || error.code === 'ENOSYS')
      ) {
        test.skip(true, 'The platform cannot create symlinks')
        return
      }
      throw error
    }

    await openDoctor(page)

    await expect(
      page.locator('.doctor').getByText('file Markdown fuori dalla radice del vault'),
    ).toBeVisible()
    await expect(page.getByText('Vault healthy')).toHaveCount(0)
    await expect(page.getByText('Vault not healthy')).toHaveCount(0)
  })

  test('clears a successful report before a later operational error', async ({ page }) => {
    await resetVaultFixture()

    await openDoctor(page)
    await expect(page.getByText('Vault healthy')).toBeVisible()

    await page.route('**/vault/doctor', async (route) => {
      await route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'vault inspection failed for E2E' }),
      })
    })
    await page.getByRole('button', { name: 'Run check' }).click()

    await expect(page.locator('.doctor').getByText('vault inspection failed for E2E')).toBeVisible()
    await expect(page.getByText('Vault healthy')).toHaveCount(0)
    await expect(page.getByText('Vault not healthy')).toHaveCount(0)
    await expect(page.locator('.doctor').getByText('1 file checked')).toHaveCount(0)
  })
})
