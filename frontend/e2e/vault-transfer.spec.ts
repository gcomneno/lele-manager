import { test as base, expect, type Page, type Request } from '@playwright/test'
import { mkdir, mkdtemp, readFile, realpath, rm, writeFile } from 'node:fs/promises'
import { randomUUID } from 'node:crypto'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'

const repositoryRoot = fileURLToPath(new URL('../..', import.meta.url))
const fixtureRoot = join(repositoryRoot, '.e2e-fixture')

type TestVault = { id: string, name: string, path: string }

function deferred() {
  let resolve!: () => void
  const promise = new Promise<void>((done) => { resolve = done })
  return { promise, resolve }
}

async function settleApplication(page: Page) {
  // Let fetch continuations and Svelte's DOM update run after requestfinished.
  await page.evaluate(() => new Promise<void>((resolve) => {
    requestAnimationFrame(() => requestAnimationFrame(() => resolve()))
  }))
}

const test = base.extend<{
  transferFixture: {
    activeId: string
    source: TestVault
    destination: TestVault
    other: TestVault
    delayResponse: (url: string, status?: number) => Promise<{
      intercepted: Promise<void>
      assertHeld: () => void
      releaseAndSettle: () => Promise<void>
    }>
  }
}>({
  transferFixture: async ({ page, playwright, baseURL }, use) => {
    // Independent request authority survives test timeout and page teardown.
    const cleanup = await playwright.request.newContext({ baseURL })
    const releases: Array<() => void> = []
    const registered: TestVault[] = []
    const handlers: Array<() => Promise<void>> = []
    const removeRequestListeners: Array<() => void> = []
    let attemptRoot = ''
    let activeId = ''
    let beforeIds: string[] | undefined
    const fixtureErrors: unknown[] = []
    try {
      const status = await cleanup.get('/vault/status')
      expect(status.ok()).toBeTruthy()
      const active = await status.json() as { vault_id: string, vault_dir: string }
      expect(await realpath(active.vault_dir)).toBe(join(await realpath(fixtureRoot), 'vault'))
      activeId = active.vault_id
      const before = await (await cleanup.get('/vaults')).json() as TestVault[]
      beforeIds = before.map((vault) => vault.id).sort()
      attemptRoot = await mkdtemp(join(fixtureRoot, 'vault-transfer-'))
      const token = randomUUID()
      for (const role of ['source', 'destination', 'other']) {
        const path = join(attemptRoot, role)
        const name = `Transfer ${role} ${token}`
        await mkdir(path)
        const response = await cleanup.post('/vaults/register', { data: { name, path } })
        expect(response.status()).toBe(201)
        registered.push({ id: (await response.json()).id, name, path })
      }
      const [source, destination, other] = registered
      const delayResponse = async (url: string, status?: number) => {
        const gate = deferred()
        const intercepted = deferred()
        const requestCompleted = deferred()
        const label = `Delayed response ${releases.length + 1}: ${url} (${status ?? 'upstream success'})`
        releases.push(gate.resolve)
        let heldRequest: Request | undefined
        let phase = 'waiting for request'
        let failure: Error | undefined
        let released = false
        let settlementStarted = false
        let requestFinished = false
        let drainOwner: (() => Promise<void>) | undefined
        await page.route(url, async (route) => {
          const completed = deferred()
          let handlerError: Error | undefined
          const drain = async () => {
            await completed.promise
            if (handlerError) throw handlerError
          }
          handlers.push(drain)
          try {
            // Keep the route registered until teardown. `times: 1` removes it
            // before this callback finishes; completion of another expired
            // handler can then remove the server interceptor and auto-continue
            // requests still held here. Claim once, and delegate later matches.
            if (heldRequest) {
              await route.fallback()
              return
            }
            heldRequest = route.request()
            drainOwner = drain
            const onFinished = (request: Request) => {
              if (request !== heldRequest) return
              requestFinished = true
              if (!settlementStarted) {
                failure = new Error(`${label}: request finished before its owner fulfilled it (${phase})`)
                gate.resolve()
              }
              requestCompleted.resolve()
            }
            const onFailed = (request: Request) => {
              if (request !== heldRequest) return
              failure = new Error(`${label}: request failed (${phase}): ${request.failure()?.errorText}`)
              requestCompleted.resolve()
              gate.resolve()
            }
            const onClosed = () => {
              if (requestFinished) return
              failure = new Error(`${label}: page closed before request completion (${phase})`)
              requestCompleted.resolve()
              gate.resolve()
            }
            page.on('requestfinished', onFinished)
            page.on('requestfailed', onFailed)
            page.on('close', onClosed)
            removeRequestListeners.push(() => {
              page.off('requestfinished', onFinished)
              page.off('requestfailed', onFailed)
              page.off('close', onClosed)
            })
            phase = 'fetching upstream response'
            // fetch obtains bytes without settling the browser's routed request.
            const response = await route.fetch()
            try {
              expect(response.ok(), `${label}: upstream status ${response.status()}`).toBeTruthy()
              phase = 'held'
              intercepted.resolve()
              await gate.promise
              if (failure) throw failure
              phase = 'fulfilling'
              settlementStarted = true
              if (status) await route.fulfill({ status, json: { detail: 'Delayed obsolete failure' } })
              else await route.fulfill({ response })
              phase = 'fulfilled'
            } finally {
              await response.dispose()
            }
          } catch (error) {
            const detail = error instanceof Error ? error.message : String(error)
            handlerError = new Error(`${label}: handler failed (${phase}): ${detail}`, { cause: error })
            failure = handlerError
            phase = 'failed'
            intercepted.resolve()
            throw handlerError
          } finally {
            completed.resolve()
          }
        })
        return {
          get intercepted() {
            return intercepted.promise.then(() => { if (failure) throw failure })
          },
          assertHeld: () => {
            if (failure) throw failure
            expect(phase, `${label}: response must remain owned and gated`).toBe('held')
            expect(requestFinished, `${label}: browser request must remain pending`).toBe(false)
          },
          releaseAndSettle: async () => {
            expect(heldRequest, `${label}: release requires an intercepted request`).toBeDefined()
            expect(released, `${label}: response must be released only once`).toBe(false)
            released = true
            gate.resolve()
            // Drain the owner first: a fulfill/fetch failure must surface before
            // waiting for a requestfinished event that can never arrive.
            await drainOwner!()
            if (failure) throw failure
            await requestCompleted.promise
            if (failure) throw failure
            await settleApplication(page)
          },
        }
      }
      await use({ activeId, source, destination, other, delayResponse })
    } catch (error) {
      // Preserve setup/use errors if cleanup also fails. Test-body failures
      // are retained separately by Playwright when fixture teardown fails.
      fixtureErrors.push(error)
      throw error
    } finally {
      const cleanupErrors: Error[] = []
      const attempt = async (label: string, operation: () => Promise<unknown> | void) => {
        try {
          await operation()
        } catch (error) {
          cleanupErrors.push(new Error(label, { cause: error }))
        }
      }
      try {
        // Release and drain owners before removing interception. Removing routes
        // first can auto-continue requests whose owners still intend to fulfill.
        for (const [index, release] of releases.entries()) {
          await attempt(`Release interception gate ${index + 1}`, release)
        }
        await Promise.all(handlers.map((handler, index) =>
          attempt(`Drain interception handler ${index + 1}`, handler)))
        await attempt('Remove page routes', () => page.unrouteAll({ behavior: 'wait' }))
        for (const [index, removeListeners] of removeRequestListeners.entries()) {
          await attempt(`Remove request listeners ${index + 1}`, removeListeners)
        }
        for (const vault of [...registered].reverse()) {
          await attempt(`Unregister synthetic Vault ${vault.name} (${vault.id})`, async () => {
            expect((await cleanup.delete(`/vaults/${vault.id}`)).status()).toBe(204)
          })
          for (const area of ['data', 'cache']) {
            await attempt(`Remove ${area} for synthetic Vault ${vault.name} (${vault.id})`, () =>
              rm(join(fixtureRoot, area, 'vaults', vault.id), { recursive: true, force: true }))
          }
        }
        if (beforeIds) {
          await attempt('Verify original Vault registry', async () => {
            const after = await (await cleanup.get('/vaults')).json() as TestVault[]
            expect(after.map((vault) => vault.id).sort()).toEqual(beforeIds)
          })
          await attempt('Verify original active Vault', async () => {
            expect((await (await cleanup.get('/vault/status')).json()).vault_id).toBe(activeId)
          })
        }
        if (attemptRoot) {
          await attempt('Remove owned synthetic attempt directory', () =>
            rm(attemptRoot, { recursive: true, force: true }))
        }
      } finally {
        await attempt('Dispose independent API request context', () => cleanup.dispose())
      }
      if (cleanupErrors.length) {
        throw new AggregateError([...fixtureErrors, ...cleanupErrors],
          `Vault transfer cleanup failed:\n${cleanupErrors.map((error) => error.message).join('\n')}`)
      }
    }
  },
})

function lesson(id: string, title: string, body: string): string {
  return ['---', `id: ${id}`, 'topic: transfer', 'source: e2e', 'importance: 3', 'tags: [transfer]', "date: '2026-08-12'", `title: ${title}`, '---', body, ''].join('\n')
}

async function writeLesson(vault: TestVault, id: string, title: string, body: string) {
  await mkdir(join(vault.path, 'transfer'), { recursive: true })
  const path = join(vault.path, `${id}.md`)
  const bytes = Buffer.from(lesson(id, title, body))
  await writeFile(path, bytes)
  return { path, bytes }
}

async function openTransfer(page: Page, source: TestVault, destination: TestVault, activeId: string) {
  await page.goto('/app/#/vault')
  const transfer = page.locator('section.vault-management').filter({ has: page.getByRole('heading', { name: 'Vault-to-Vault transfer' }) })
  await expect(transfer.getByLabel('Source Vault')).toHaveValue(activeId)
  await transfer.getByLabel('Source Vault').selectOption(source.id)
  await transfer.getByLabel('Destination Vault').selectOption(destination.id)
  return transfer
}

test('previews and merges an explicit A -> B selection without switching the active Vault', async ({ page, request, transferFixture }) => {
  const { source, destination, other, activeId } = transferFixture
  const original = await writeLesson(source, 'transfer/clean', 'Clean transfer', 'Clean merge body.')
  const transfer = await openTransfer(page, source, destination, activeId)
  await expect(transfer.getByLabel('Vault transfer direction')).toContainText(`${source.name} → ${destination.name}`)
  await transfer.getByRole('checkbox', { name: /transfer\/clean/ }).check()
  await expect(transfer.getByRole('button', { name: 'Execute transfer' })).toHaveCount(0)
  await transfer.getByRole('button', { name: 'Validate and preview transfer' }).click()
  await expect(transfer.getByRole('heading', { name: 'Transfer preview' })).toBeVisible()
  await expect(transfer).toContainText('New')

  await transfer.getByLabel('Destination Vault').selectOption(other.id)
  await expect(transfer.getByRole('heading', { name: 'Transfer preview' })).toHaveCount(0)
  await transfer.getByLabel('Destination Vault').selectOption(destination.id)
  await transfer.getByRole('button', { name: 'Validate and preview transfer' }).click()
  const executed = page.waitForResponse('**/vault-transfers/execute')
  await transfer.getByRole('button', { name: 'Execute transfer' }).click()
  expect((await executed).ok()).toBeTruthy()
  await expect(transfer.getByText('Transfer completed.', { exact: true })).toBeVisible()
  expect(await readFile(original.path)).toEqual(original.bytes)
  expect(await readFile(join(destination.path, 'transfer', 'clean.md'))).toEqual(original.bytes)
  expect((await (await request.get('/vault/status')).json()).vault_id).toBe(activeId)

  await transfer.getByLabel('Operation').selectOption('move')
  await expect(transfer.getByText('Move deletes each source lesson only after its destination canonical success.')).toBeVisible()
})

test('conflicts cannot overwrite, resolution requires a new preview, stale async preview is discarded, and IT terminology is complete', async ({ page, transferFixture }) => {
  const { source, destination, other, activeId, delayResponse } = transferFixture
  await writeLesson(source, 'transfer/conflict', 'Source conflict', 'Source conflict body.')
  const original = await writeLesson(destination, 'transfer/conflict', 'Destination conflict', 'Destination must remain.')
  const transfer = await openTransfer(page, source, destination, activeId)
  const preview = transfer.getByRole('button', { name: 'Validate and preview transfer' })
  await transfer.getByRole('checkbox', { name: /transfer\/conflict/ }).check()
  await preview.click()
  await expect(transfer).toContainText('Same ID')
  await expect(transfer.getByRole('button', { name: 'Execute transfer' })).toBeDisabled()
  await transfer.getByLabel('Resolution').selectOption('keep_destination')
  await expect(transfer.getByRole('heading', { name: 'Transfer preview' })).toHaveCount(0)
  await expect(transfer.getByText('Resolution changed. Validate and preview again before executing.')).toBeVisible()
  await preview.click()
  const executed = page.waitForResponse('**/vault-transfers/execute')
  await transfer.getByRole('button', { name: 'Execute transfer' }).click()
  const result = await executed
  expect(result.ok()).toBeTruthy()
  expect((await result.json()).items[0].outcome).toBe('skipped_by_resolution')
  await expect(transfer.getByText('Transfer completed.', { exact: true })).toBeVisible()
  expect(await readFile(original.path)).toEqual(original.bytes)

  await transfer.getByRole('checkbox', { name: /transfer\/conflict/ }).check()
  const delayed = await delayResponse('**/vault-transfers/preview')
  await preview.click()
  await delayed.intercepted
  await transfer.getByLabel('Destination Vault').selectOption(other.id)
  await delayed.releaseAndSettle()
  await expect(transfer.getByRole('heading', { name: 'Transfer preview' })).toHaveCount(0)
  await expect(transfer.getByRole('button', { name: 'Execute transfer' })).toHaveCount(0)
  await expect(preview).toBeEnabled()
  expect(await readFile(original.path)).toEqual(original.bytes)
  await preview.click()
  await expect(transfer.getByRole('heading', { name: 'Transfer preview' })).toBeVisible()
  await expect(transfer).toContainText(`Destination: ${other.name}`)

  await page.addInitScript(() => localStorage.setItem('lele-manager.locale', 'it'))
  await page.reload()
  const italian = page.locator('section.vault-management').filter({ has: page.getByRole('heading', { name: 'Trasferimento Vault-a-Vault' }) })
  await expect(italian.getByLabel('Vault sorgente')).toBeVisible()
  await expect(italian.getByLabel('Vault destinazione')).toBeVisible()
  await expect(italian.getByLabel('Operazione')).toContainText('Accorpa')
  await expect(italian.getByLabel('Operazione')).toContainText('Copia')
  await expect(italian.getByLabel('Operazione')).toContainText('Sposta')
})

test('destination and operation changes preserve an in-flight source load', async ({ page, transferFixture }) => {
  const { source, destination, other, activeId, delayResponse } = transferFixture
  await writeLesson(source, 'transfer/delayed-source', 'Delayed source', 'Source lessons survive destination edits.')
  const delayed = await delayResponse(`**/vault-transfers/sources/${source.id}/lessons`)
  const transfer = await openTransfer(page, source, destination, activeId)
  await delayed.intercepted
  await transfer.getByLabel('Destination Vault').selectOption(other.id)
  await transfer.getByLabel('Operation').selectOption('copy')
  await delayed.releaseAndSettle()
  await transfer.getByRole('checkbox', { name: /transfer\/delayed-source/ }).check()
  await transfer.getByRole('button', { name: 'Validate and preview transfer' }).click()
  await expect(transfer.getByRole('heading', { name: 'Transfer preview' })).toBeVisible()
  await expect(transfer).toContainText(`Destination: ${other.name}`)
})

for (const obsoleteStatus of [undefined, 500]) {
  test(`obsolete source ${obsoleteStatus ?? 'success'} cannot clear a newer source load`, async ({ page, transferFixture }) => {
    const { source, destination, other, activeId, delayResponse } = transferFixture
    await writeLesson(source, 'transfer/old-source', 'Old source', 'Old source response.')
    await writeLesson(other, 'transfer/new-source', 'New source', 'Current source response.')
    const old = await delayResponse(`**/vault-transfers/sources/${source.id}/lessons`, obsoleteStatus)
    const transfer = await openTransfer(page, source, destination, activeId)
    await old.intercepted
    const current = await delayResponse(`**/vault-transfers/sources/${other.id}/lessons`)
    await transfer.getByLabel('Source Vault').selectOption(other.id)
    await current.intercepted
    current.assertHeld()
    await old.releaseAndSettle()
    current.assertHeld()
    await expect(transfer.getByRole('checkbox', { name: /transfer\/old-source/ })).toHaveCount(0)
    await expect(transfer.getByText('Delayed obsolete failure', { exact: true })).toHaveCount(0)
    await current.releaseAndSettle()
    await transfer.getByRole('checkbox', { name: /transfer\/new-source/ }).check()
    await transfer.getByRole('button', { name: 'Validate and preview transfer' }).click()
    await expect(transfer.getByRole('heading', { name: 'Transfer preview' })).toBeVisible()
    await expect(transfer).toContainText(`Source: ${other.name}`)
  })

  test(`obsolete preview ${obsoleteStatus ?? 'success'} cannot clear a newer preview`, async ({ page, transferFixture }) => {
    const { source, destination, other, activeId, delayResponse } = transferFixture
    await writeLesson(source, 'transfer/delayed-preview', 'Delayed preview', 'Preview ownership follows the current destination.')
    const transfer = await openTransfer(page, source, destination, activeId)
    await transfer.getByRole('checkbox', { name: /transfer\/delayed-preview/ }).check()
    const preview = transfer.getByRole('button', { name: 'Validate and preview transfer' })
    const old = await delayResponse('**/vault-transfers/preview', obsoleteStatus)
    await preview.click()
    await old.intercepted
    await transfer.getByLabel('Destination Vault').selectOption(other.id)
    await expect(preview).toBeEnabled()
    const current = await delayResponse('**/vault-transfers/preview')
    await preview.click()
    await current.intercepted
    current.assertHeld()
    await expect(preview).toBeDisabled()
    await old.releaseAndSettle()
    current.assertHeld()
    await expect(preview).toBeDisabled()
    await expect(transfer.getByRole('heading', { name: 'Transfer preview' })).toHaveCount(0)
    await expect(transfer.getByText('Delayed obsolete failure', { exact: true })).toHaveCount(0)
    await current.releaseAndSettle()
    await expect(preview).toBeEnabled()
    await expect(transfer.getByRole('heading', { name: 'Transfer preview' })).toBeVisible()
    await expect(transfer).toContainText(`Destination: ${other.name}`)
  })
}
