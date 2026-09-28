import { expect, test } from '@playwright/test'

const lesson = {
  id: 'python/releases',
  text: 'Python 3.12 was released in October 2023.',
  topic: 'python',
  source: 'private-test-source',
  importance: 3,
  tags: ['python', 'release'],
  date: '2026-09-25',
  title: 'Python releases',
  lifecycle: 'active',
  superseded_by: null,
  relationships: {},
  incoming_relationships: {},
  canonical_revision: 'sha256:canonical-a',
  supersedes: [],
  freshness: null,
}

test('detail factual verification requires explicit consent before remote processing', async ({
  page,
}) => {
  const posts: unknown[] = []

  await page.route(
    '**/lessons/python%2Freleases',
    route => route.fulfill({ json: lesson }),
  )

  await page.route(
    '**/lessons/python%2Freleases/similar?*',
    route => route.fulfill({
      json: {
        query: 'python/releases',
        results: [],
      },
    }),
  )

  await page.route(
    '**/lessons/python%2Freleases/factual-verification',
    async route => {
      if (route.request().method() === 'GET') {
        await route.fulfill({
          json: {
            lesson_id: 'python/releases',
            remote_processing_approved: false,
            assessments: [],
          },
        })
        return
      }

      posts.push(route.request().postDataJSON())

      await route.fulfill({
        json: {
          lesson_id: 'python/releases',
          remote_processing_approved: true,
          assessments: [
            {
              lesson_id: 'python/releases',
              canonical_revision: 'sha256:canonical-a',
              claim: {
                claim_id: 'release-date',
                text: 'Python 3.12 was released in October 2023.',
                classification: 'stable-factual',
              },
              outcome: 'supported',
              evidence: [
                {
                  source_id: 'python-3.12-release',
                  source_uri:
                    'https://www.python.org/downloads/release/python-3120/',
                  source_title: 'Python 3.12.0',
                  retrieved_at: '2026-09-25T05:00:00+00:00',
                  excerpt:
                    'Python 3.12.0 was released on October 2, 2023.',
                },
              ],
              checked_at: '2026-09-25T06:00:00+00:00',
              explanation:
                'The primary release page supports the release-date claim.',
              stale: false,
            },
            {
              lesson_id: 'python/releases',
              canonical_revision: 'sha256:canonical-a',
              claim: {
                claim_id: 'preference',
                text: 'Python 3.12 feels nicer.',
                classification: 'subjective',
              },
              outcome: 'not-verifiable',
              evidence: [],
              checked_at: '2026-09-25T06:00:00+00:00',
              explanation:
                'The claim is subjective and is not suitable for external factual verification.',
              stale: false,
            },
          ],
        },
      })
    },
  )

  await page.goto('/app/#/lesson/python%2Freleases')

  const panel = page.getByTestId('factual-verification')

  await expect(panel).toBeVisible()
  await expect(panel).toContainText('Factual verification')
  await expect(panel).toContainText(
    'Nothing is sent for external verification automatically.',
  )

  expect(posts).toEqual([])

  const verify = panel.getByRole('button', {
    name: 'Verify factual claims',
  })

  await expect(verify).toBeDisabled()

  await panel.getByRole('checkbox', {
    name: /approve sending only bounded claims/i,
  }).check()

  await expect(verify).toBeEnabled()
  await verify.click()

  expect(posts).toEqual([
    {
      remote_processing_approved: true,
    },
  ])

  await expect(panel).toContainText('Supported')
  await expect(panel).toContainText(
    'Python 3.12 was released in October 2023.',
  )
  await expect(panel).toContainText('Python 3.12.0')
  await expect(panel).toContainText('Not externally verifiable')
  await expect(panel).toContainText('Python 3.12 feels nicer.')
})

test('detail shows persisted stale factual verification without remote processing', async ({
  page,
}) => {
  let postCount = 0

  await page.route(
    '**/lessons/python%2Freleases',
    route => route.fulfill({ json: lesson }),
  )

  await page.route(
    '**/lessons/python%2Freleases/similar?*',
    route => route.fulfill({
      json: {
        query: 'python/releases',
        results: [],
      },
    }),
  )

  await page.route(
    '**/lessons/python%2Freleases/factual-verification',
    async route => {
      if (route.request().method() === 'POST') {
        postCount += 1
        await route.fulfill({ status: 500 })
        return
      }

      await route.fulfill({
        json: {
          lesson_id: 'python/releases',
          remote_processing_approved: false,
          assessments: [
            {
              lesson_id: 'python/releases',
              canonical_revision: 'sha256:old',
              claim: {
                claim_id: 'release-date',
                text: 'Python 3.12 was released in October 2023.',
                classification: 'stable-factual',
              },
              outcome: 'supported',
              evidence: [
                {
                  source_id: 'python-3.12-release',
                  source_uri:
                    'https://www.python.org/downloads/release/python-3120/',
                  source_title: 'Python 3.12.0',
                  retrieved_at: '2026-01-01T05:00:00+00:00',
                  excerpt:
                    'Python 3.12.0 was released on October 2, 2023.',
                },
              ],
              checked_at: '2026-01-01T06:00:00+00:00',
              explanation: 'Previously supported.',
              stale: true,
            },
          ],
        },
      })
    },
  )

  await page.goto('/app/#/lesson/python%2Freleases')

  const panel = page.getByTestId('factual-verification')

  await expect(panel).toContainText('Supported')
  await expect(panel).toContainText('Stale verification')
  expect(postCount).toBe(0)
})
