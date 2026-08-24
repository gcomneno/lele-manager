import { expect, test } from '@playwright/test'

const hybridLesson = {
  id: 'hybrid/lexical',
  title: 'Python retries',
  text: 'Use idempotency keys for retryable operations.',
  topic: 'python',
  source: 'notes',
  importance: 4,
  tags: ['python', 'retries'],
  lifecycle: 'active',
  rank: 1,
  hybrid_score: 1.7,
  semantic_available: true,
  why: [
    { code: 'exact-title-match' },
    { code: 'topic-match', value: 0.5 },
    { code: 'semantic-similarity', value: 0.84 },
  ],
}

test('Browse explains hybrid search results without exposing raw ranking values', async ({
  page,
}) => {
  await page.route('**/lessons/search', route =>
    route.fulfill({ json: [hybridLesson] }),
  )

  await page.goto('/app/#/browse')

  const explanation = page.getByTestId(
    'search-explanation-hybrid/lexical',
  )

  await expect(explanation).toBeVisible()
  await expect(explanation).toContainText('Why this result?')
  await expect(explanation).toContainText('Exact title match')
  await expect(explanation).toContainText('Query matches the topic')
  await expect(explanation).toContainText(
    'Conceptually related to the query',
  )

  await expect(explanation).not.toContainText('1.7')
  await expect(explanation).not.toContainText('0.84')
  await expect(page.getByText('Minimum similarity')).toHaveCount(0)
  await expect(page.getByText('Maximum results')).toHaveCount(0)
})

test('Browse explains semantic degradation without treating it as an error', async ({
  page,
}) => {
  await page.route('**/lessons/search', route =>
    route.fulfill({
      json: [
        {
          ...hybridLesson,
          semantic_available: false,
          why: [{ code: 'exact-title-match' }],
        },
      ],
    }),
  )

  await page.goto('/app/#/browse')

  await expect(
    page.getByTestId('semantic-degraded-hybrid/lexical'),
  ).toContainText(
    'Semantic matching is unavailable; these results use deterministic search signals only.',
  )

  await expect(page.getByText(/error/i)).toHaveCount(0)
})

test('Italian Browse localizes hybrid search explanations', async ({
  page,
}) => {
  await page.addInitScript(() => {
    localStorage.setItem('lele-manager.locale', 'it')
  })

  await page.route('**/lessons/search', route =>
    route.fulfill({
      json: [
        {
          ...hybridLesson,
          semantic_available: true,
          why: [
            { code: 'exact-title-match' },
            { code: 'semantic-similarity', value: 0.84 },
          ],
        },
      ],
    }),
  )

  await page.goto('/app/#/browse')

  const explanation = page.getByTestId(
    'search-explanation-hybrid/lexical',
  )

  await expect(explanation).toContainText(
    'Perché questo risultato?',
  )
  await expect(explanation).toContainText(
    'Corrispondenza esatta nel titolo',
  )
  await expect(explanation).toContainText(
    'Concettualmente correlata alla ricerca',
  )
  await expect(explanation).not.toContainText('0.84')
})
