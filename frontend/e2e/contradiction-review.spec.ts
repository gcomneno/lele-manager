import { expect, test, type Page } from '@playwright/test'

const revisionA = `sha256:${'a'.repeat(64)}`
const revisionB = `sha256:${'b'.repeat(64)}`

function candidateReport() {
  return {
    vault_id: 'vault-test',
    lessons_analyzed: 2,
    analysis_bound: 10000,
    returned_candidates: 1,
    suppressed_candidates: 0,
    candidates: [
      {
        left_id: 'alpha/new',
        right_id: 'alpha/old',
        reasons: ['same-topic', 'opposing-modal-cue'],
        same_subject_reasons: ['same-topic'],
        tension_reasons: ['opposing-modal-cue'],
        similarity_score: 0.91,
        left_fingerprint: 'left-fingerprint',
        right_fingerprint: 'right-fingerprint',
        left_canonical_revision: revisionA,
        right_canonical_revision: revisionB,
        resolution_available: true,
        resolution_problem: null,
        left_lesson: {
          id: 'alpha/new',
          text: 'The cache must not be enabled.',
          title: 'New guidance',
          topic: 'alpha',
          source: 'note',
          importance: 4,
          tags: ['alpha'],
          date: '2026-08-22',
          lifecycle: 'active',
          superseded_by: null,
          relationships: {},
        },
        right_lesson: {
          id: 'alpha/old',
          text: 'The cache must be enabled.',
          title: 'Old guidance',
          topic: 'alpha',
          source: 'note',
          importance: 4,
          tags: ['alpha'],
          date: '2026-08-20',
          lifecycle: 'active',
          superseded_by: null,
          relationships: {},
        },
      },
    ],
  }
}

async function mockContradictions(page: Page) {
  await page.route('**/contradictions?*', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(candidateReport()),
    })
  })
}

test('dedicated potential contradiction review route is reachable', async ({ page }) => {
  await mockContradictions(page)

  await page.goto('/#/contradictions')

  await expect(
    page.getByRole('heading', { name: 'Potential contradiction review' }),
  ).toBeVisible()

  await expect(page).toHaveURL(/#\/contradictions$/)
})

test('candidate surfacing is advisory and explainable, never proof wording', async ({ page }) => {
  await mockContradictions(page)

  await page.goto('/#/contradictions')
  await page.getByRole('button', { name: 'Run review' }).click()

  await expect(page.getByText('Potential candidate')).toBeVisible()
  await expect(page.getByText('Why surfaced')).toBeVisible()
  await expect(page.getByText('Same topic')).toBeVisible()
  await expect(page.getByText('Opposing modal cue')).toBeVisible()
  await expect(page.getByText('Retrieval score')).toBeVisible()
  await expect(page.getByText(/retrieval metadata/i)).toBeVisible()
  await expect(page.getByText(/advisory review cue/i)).toBeVisible()

  await expect(page.getByText(/verified contradiction/i)).toHaveCount(0)
  await expect(page.getByText(/proven contradiction/i)).toHaveCount(0)
  await expect(page.getByText(/factual verification/i)).toHaveCount(0)
  await expect(page.getByText(/truth judgment/i)).toHaveCount(0)
})

test('auxiliary and canonical decisions are visibly distinct', async ({ page }) => {
  await mockContradictions(page)

  await page.goto('/#/contradictions')
  await page.getByRole('button', { name: 'Run review' }).click()

  const auxiliary = page.getByRole('region', { name: 'Auxiliary decisions' })
  await expect(auxiliary).toBeVisible()
  await expect(auxiliary.getByRole('button', { name: 'Different context' })).toBeVisible()
  await expect(auxiliary.getByRole('button', { name: 'Dismiss candidate' })).toBeVisible()

  const canonical = page.getByRole('region', { name: 'Directional canonical actions' })
  await expect(canonical).toBeVisible()
  await expect(canonical.getByRole('button', { name: 'Superseded by' })).toBeVisible()
  await expect(canonical.getByRole('button', { name: 'Corrects' })).toBeVisible()
  await expect(canonical.getByRole('button', { name: 'Contradicts' })).toBeVisible()

  await expect(auxiliary.getByRole('button', { name: 'Contradicts' })).toHaveCount(0)
  await expect(canonical.getByRole('button', { name: 'Different context' })).toHaveCount(0)
})

test('contradicts canonical action requires explicit direction and exact request body', async ({ page }) => {
  await mockContradictions(page)

  let resolveBody: unknown = null

  await page.route('**/contradictions/resolve', async (route) => {
    resolveBody = route.request().postDataJSON()

    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        vault_id: 'vault-test',
        decision: 'contradicts',
        mutated_lesson_id: 'alpha/new',
        referenced_lesson_id: 'alpha/old',
        canonical_success: true,
        canonical_changed: true,
        derived_refresh_success: true,
        partial_success: false,
        canonical_revision: revisionA,
        revision: 2,
        noop_reason: null,
        refresh_error: null,
      }),
    })
  })

  await page.goto('/#/contradictions')
  await page.getByRole('button', { name: 'Run review' }).click()
  await page.getByRole('button', { name: 'Contradicts' }).click()

  const confirm = page.getByRole('button', { name: 'Save directional contradiction' })
  await expect(confirm).toBeDisabled()

  await page.getByLabel('alpha/new contradicts alpha/old').check()
  await expect(confirm).toBeEnabled()
  await confirm.click()

  expect(resolveBody).toEqual({
    decision: 'contradicts',
    source_id: 'alpha/new',
    target_id: 'alpha/old',
    expected_source_revision: revisionA,
  })

  await expect(
    page.getByText('Only this selected directional relationship is written.'),
  ).toBeVisible()
})

test('different context is saved as auxiliary review state without canonical mutation', async ({ page }) => {
  await mockContradictions(page)

  let dismissBody: unknown = null
  let resolveCalls = 0

  await page.route('**/contradictions/dismiss', async (route) => {
    dismissBody = route.request().postDataJSON()
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        vault_id: 'vault-test',
        left_id: 'alpha/new',
        right_id: 'alpha/old',
        decision: 'different-context',
        canonical_success: false,
        canonical_changed: false,
        derived_refresh_success: null,
      }),
    })
  })

  await page.route('**/contradictions/resolve', async (route) => {
    resolveCalls += 1
    await route.abort()
  })

  await page.goto('/#/contradictions')
  await page.getByRole('button', { name: 'Run review' }).click()
  await page.getByRole('button', { name: 'Different context' }).click()

  expect(dismissBody).toEqual({
    decision: 'different-context',
    left_id: 'alpha/new',
    right_id: 'alpha/old',
    left_fingerprint: 'left-fingerprint',
    right_fingerprint: 'right-fingerprint',
    note: null,
  })
  expect(resolveCalls).toBe(0)

  await expect(
    page.getByText('Auxiliary review decision saved. Canonical Markdown was not changed.'),
  ).toBeVisible()
})

test('dismiss candidate uses auxiliary endpoint only', async ({ page }) => {
  await mockContradictions(page)

  let dismissBody: unknown = null

  await page.route('**/contradictions/dismiss', async (route) => {
    dismissBody = route.request().postDataJSON()
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        vault_id: 'vault-test',
        left_id: 'alpha/new',
        right_id: 'alpha/old',
        decision: 'dismissed',
        canonical_success: false,
        canonical_changed: false,
        derived_refresh_success: null,
      }),
    })
  })

  await page.goto('/#/contradictions')
  await page.getByRole('button', { name: 'Run review' }).click()
  await page.getByRole('button', { name: 'Dismiss candidate' }).click()

  expect(dismissBody).toEqual({
    decision: 'dismissed',
    left_id: 'alpha/new',
    right_id: 'alpha/old',
    left_fingerprint: 'left-fingerprint',
    right_fingerprint: 'right-fingerprint',
    note: null,
  })
})

test('superseded-by requires explicit direction and exact request body', async ({ page }) => {
  await mockContradictions(page)
  let resolveBody: unknown = null

  await page.route('**/contradictions/resolve', async (route) => {
    resolveBody = route.request().postDataJSON()
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        vault_id: 'vault-test',
        decision: 'superseded-by',
        mutated_lesson_id: 'alpha/old',
        referenced_lesson_id: 'alpha/new',
        canonical_success: true,
        canonical_changed: true,
        derived_refresh_success: true,
        partial_success: false,
        canonical_revision: revisionB,
        revision: 2,
        noop_reason: null,
        refresh_error: null,
      }),
    })
  })

  await page.goto('/#/contradictions')
  await page.getByRole('button', { name: 'Run review' }).click()
  await page.getByRole('button', { name: 'Superseded by' }).click()

  const confirm = page.getByRole('button', { name: 'Save directional supersession' })
  await expect(confirm).toBeDisabled()

  await page.getByLabel('alpha/old is superseded by alpha/new').check()
  await confirm.click()

  expect(resolveBody).toEqual({
    decision: 'superseded-by',
    superseded_id: 'alpha/old',
    replacement_id: 'alpha/new',
    expected_superseded_revision: revisionB,
  })
})

test('corrects requires explicit direction and exact request body', async ({ page }) => {
  await mockContradictions(page)
  let resolveBody: unknown = null

  await page.route('**/contradictions/resolve', async (route) => {
    resolveBody = route.request().postDataJSON()
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        vault_id: 'vault-test',
        decision: 'corrects',
        mutated_lesson_id: 'alpha/new',
        referenced_lesson_id: 'alpha/old',
        canonical_success: true,
        canonical_changed: true,
        derived_refresh_success: true,
        partial_success: false,
        canonical_revision: revisionA,
        revision: 2,
        noop_reason: null,
        refresh_error: null,
      }),
    })
  })

  await page.goto('/#/contradictions')
  await page.getByRole('button', { name: 'Run review' }).click()
  await page.getByRole('button', { name: 'Corrects' }).click()

  const confirm = page.getByRole('button', { name: 'Save directional correction' })
  await expect(confirm).toBeDisabled()

  await page.getByLabel('alpha/new corrects alpha/old').check()
  await confirm.click()

  expect(resolveBody).toEqual({
    decision: 'corrects',
    correcting_id: 'alpha/new',
    corrected_id: 'alpha/old',
    expected_correcting_revision: revisionA,
  })
})

test('stale canonical resolution remains visible without automatic retry', async ({ page }) => {
  await mockContradictions(page)

  let resolveCalls = 0
  let getCalls = 0

  await page.route('**/contradictions?*', async (route) => {
    getCalls += 1
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(candidateReport()),
    })
  })

  await page.route('**/contradictions/resolve', async (route) => {
    resolveCalls += 1
    await route.fulfill({
      status: 409,
      contentType: 'application/json',
      body: JSON.stringify({
        detail: {
          code: 'contradiction_stale',
          message: 'stale',
        },
      }),
    })
  })

  await page.goto('/#/contradictions')
  await page.getByRole('button', { name: 'Run review' }).click()
  await page.getByRole('button', { name: 'Contradicts' }).click()
  await page.getByLabel('alpha/new contradicts alpha/old').check()
  await page.getByRole('button', { name: 'Save directional contradiction' }).click()

  await expect(
    page.getByText('This candidate changed. Refresh the contradiction review before resolving.'),
  ).toBeVisible()

  expect(resolveCalls).toBe(1)
  expect(getCalls).toBe(1)
  await expect(page.getByText('Potential candidate')).toBeVisible()
})

test('recovery indeterminate forbids blind retry', async ({ page }) => {
  await mockContradictions(page)

  await page.route('**/contradictions/resolve', async (route) => {
    await route.fulfill({
      status: 503,
      contentType: 'application/json',
      body: JSON.stringify({
        detail: {
          code: 'contradiction_recovery_indeterminate',
          message: 'canonical state indeterminate',
          recovery: {
            retry_safe: false,
            message: 'Canonical state may already have changed; do not blindly retry the canonical mutation.',
          },
        },
      }),
    })
  })

  await page.goto('/#/contradictions')
  await page.getByRole('button', { name: 'Run review' }).click()
  await page.getByRole('button', { name: 'Contradicts' }).click()
  await page.getByLabel('alpha/new contradicts alpha/old').check()
  await page.getByRole('button', { name: 'Save directional contradiction' }).click()

  await expect(
    page.getByText('Canonical state is indeterminate. Do not blindly retry this action.'),
  ).toBeVisible()
})

test('canonical partial success is not presented as total failure', async ({ page }) => {
  await mockContradictions(page)

  await page.route('**/contradictions/resolve', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        vault_id: 'vault-test',
        decision: 'contradicts',
        mutated_lesson_id: 'alpha/new',
        referenced_lesson_id: 'alpha/old',
        canonical_success: true,
        canonical_changed: true,
        derived_refresh_success: false,
        partial_success: true,
        canonical_revision: revisionA,
        revision: 2,
        noop_reason: null,
        refresh_error: 'refresh failed',
      }),
    })
  })

  await page.goto('/#/contradictions')
  await page.getByRole('button', { name: 'Run review' }).click()
  await page.getByRole('button', { name: 'Contradicts' }).click()
  await page.getByLabel('alpha/new contradicts alpha/old').check()
  await page.getByRole('button', { name: 'Save directional contradiction' }).click()

  await expect(
    page.getByText(
      'Canonical resolution was saved, but derived contradiction review data could not be refreshed.',
    ),
  ).toBeVisible()

  await expect(page.getByText(/resolution failed/i)).toHaveCount(0)
})

test('loading empty and store error states are coherent', async ({ page }) => {
  let release: (() => void) | null = null

  await page.route('**/contradictions?*', async (route) => {
    await new Promise<void>((resolve) => {
      release = resolve
    })
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        ...candidateReport(),
        returned_candidates: 0,
        candidates: [],
      }),
    })
  })

  await page.goto('/#/contradictions')
  await page.getByRole('button', { name: 'Run review' }).click()

  await expect(
    page.getByText('Potential contradiction review in progress'),
  ).toBeVisible()

  release?.()

  await expect(page.getByText('No potential contradiction candidates')).toBeVisible()

  await page.unroute('**/contradictions?*')
  await page.route('**/contradictions?*', async (route) => {
    await route.fulfill({
      status: 503,
      contentType: 'application/json',
      body: JSON.stringify({
        detail: {
          code: 'contradiction_store_failed',
          message: 'Contradiction-review state could not be read safely.',
        },
      }),
    })
  })

  await page.getByRole('button', { name: 'Run review' }).click()

  await expect(
    page.getByText('Contradiction review state could not be read safely'),
  ).toBeVisible()
})

test('italian contradiction review keeps advisory semantics', async ({ page }) => {
  await mockContradictions(page)

  await page.goto('/#/contradictions')
  await page.getByTestId('language-control').selectOption('it')

  await expect(
    page.getByRole('heading', { name: 'Revisione potenziali contraddizioni' }),
  ).toBeVisible()

  await page.getByRole('button', { name: 'Avvia revisione' }).click()

  await expect(page.getByText('Candidato potenziale')).toBeVisible()
  await expect(page.getByText('Perché emerso')).toBeVisible()
  await expect(page.getByText('Decisioni ausiliarie')).toBeVisible()
  await expect(page.getByText('Azioni canoniche direzionali')).toBeVisible()
  await expect(
    page.getByText(/nessun giudizio automatico di verità/i),
  ).toBeVisible()
})

test('duplicate review remains semantically distinct', async ({ page }) => {
  await page.goto('/#/duplicates')

  await expect(
    page.getByRole('heading', { name: 'Duplicate review' }),
  ).toBeVisible()

  await expect(page.getByText('Potential contradiction review')).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'Different context' })).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'Contradicts' })).toHaveCount(0)
})
