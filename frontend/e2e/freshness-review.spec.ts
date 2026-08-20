import { expect, test, type Page } from '@playwright/test'

const lessonId = 'freshness/review-action'
const encodedId = encodeURIComponent(lessonId)
const fp0 = `sha256:${'0'.repeat(64)}`
const fp1 = `sha256:${'1'.repeat(64)}`

async function mockFreshnessDetail(page: Page) {
  let revision = fp0
  let reviewedAt: string | null = null
  let lifecycle: 'active' | 'review-needed' = 'review-needed'
  const reviewRequests: unknown[] = []

  await page.route('**/lesson-history?*', route =>
    route.fulfill({
      json: {
        lesson_id: lessonId,
        current_canonical_revision: revision,
        revisions: [],
      },
    }),
  )

  await page.route('**/lessons/**', async route => {
    const request = route.request()
    const pathname = new URL(request.url()).pathname

    if (pathname.endsWith('/similar')) {
      return route.fulfill({
        json: {
          query: lessonId,
          results: [],
          meta: {
            top_k: 8,
            min_score: 0.05,
          },
        },
      })
    }

    if (pathname.endsWith('/review')) {
      reviewRequests.push(request.postDataJSON())
      reviewedAt = '2026-08-20'
      lifecycle = 'active'
      revision = fp1

      return route.fulfill({
        json: {
          lesson_id: lessonId,
          reviewed_at: reviewedAt,
          lifecycle,
          revision: 1,
          canonical_revision: revision,
          canonical_changed: true,
          refresh_outcome: {
            refreshed: true,
          },
        },
      })
    }

    return route.fulfill({
      json: {
        id: lessonId,
        title: 'Freshness review',
        text: 'Knowledge with explicit review attention.',
        topic: 'freshness',
        source: 'note',
        importance: 4,
        tags: ['freshness'],
        date: '2025-01-01',
        reviewed_at: reviewedAt,
        review_interval_days: 180,
        lifecycle,
        superseded_by: null,
        supersedes: [],
        relationships: {},
        incoming_relationships: {},
        canonical_revision: revision,
        freshness: {
          review_needed: reviewedAt === null,
          lifecycle,
          baseline_date: reviewedAt ?? '2025-01-01',
          age_days: reviewedAt === null ? 596 : 0,
          review_interval_days: 180,
          reasons: reviewedAt === null
            ? [{
                code: 'lifecycle-review-needed',
                message: 'review needed',
                related_lesson_ids: [],
              }]
            : [],
        },
      },
    })
  })

  return {
    reviewRequests,
  }
}

test('Detail explains freshness and records an explicit review', async ({
  page,
}) => {
  const calls = await mockFreshnessDetail(page)

  await page.goto(`/app/#/lesson/${encodedId}`)

  const panel = page.getByTestId('detail-freshness')

  await expect(panel).toContainText('Review attention')
  await expect(panel).toContainText('Review suggested')
  await expect(panel).toContainText(
    'Canonical lifecycle explicitly requests review.',
  )
  await expect(panel).toContainText('Never explicitly reviewed')

  await panel.getByRole('button', {
    name: 'Record review',
    exact: true,
  }).click()

  await expect.poll(() => calls.reviewRequests.length).toBe(1)
  expect(calls.reviewRequests[0]).toEqual({
    expected_revision: fp0,
  })

  await expect(panel).toContainText('Review recorded.')
  await expect(panel).toContainText('2026-08-20')
  await expect(panel).toContainText('No review signal')

  await page.getByLabel('Language').selectOption('it')

  await expect(panel).toContainText('Attenzione revisione')
  await expect(
    panel.getByRole('button', {
      name: 'Registra revisione',
      exact: true,
    }),
  ).toBeVisible()
})
