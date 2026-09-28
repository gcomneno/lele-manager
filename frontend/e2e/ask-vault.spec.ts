import { expect, test } from '@playwright/test'

const alpha = {
  id: 'python/alpha',
  text: 'Alpha canonical body',
  title: 'Alpha',
  lifecycle: 'active',
}

const beta = {
  id: 'python/beta',
  text: 'Beta canonical body',
  title: 'Beta',
  lifecycle: 'review-needed',
}

test('Ask this Vault submits the exact visible scope and exposes generated synthesis with canonical citations', async ({
  page,
}) => {
  const requests: unknown[] = []

  await page.route('**/context-packs', route =>
    route.fulfill({ json: [] }),
  )

  await page.route('**/lessons/search', route =>
    route.fulfill({
      json: [alpha, beta],
    }),
  )

  await page.route('**/ask-vault', async route => {
    const body = route.request().postDataJSON()
    requests.push(body)

    await route.fulfill({
      json: {
        outcome: 'answered',
        answer: 'Use Alpha while Beta needs review.',
        generated_synthesis: true,
        citations: [
          {
            lesson_id: 'python/alpha',
            title: 'Alpha',
            lifecycle: 'active',
            superseded_by: null,
          },
          {
            lesson_id: 'python/beta',
            title: 'Beta',
            lifecycle: 'review-needed',
            superseded_by: null,
          },
        ],
        scope_lesson_ids: [
          'python/alpha',
          'python/beta',
        ],
      },
    })
  })

  await page.goto('/app/#/browse')

  await page
    .getByRole('button', {
      name: 'Search',
      exact: true,
    })
    .click()

  const ask = page.getByTestId('ask-vault-results')

  await expect(ask).toContainText(
    'Grounded scope: 2 LeLe',
  )

  await ask
    .getByLabel('Question')
    .fill('What should I use?')

  await ask
    .getByRole('button', {
      name: 'Ask this Vault',
      exact: true,
    })
    .click()

  expect(requests).toEqual([
    {
      lesson_ids: [
        'python/alpha',
        'python/beta',
      ],
      question: 'What should I use?',
    },
  ])

  const result = page.getByTestId(
    'ask-vault-results-result',
  )

  await expect(result).toContainText(
    'Generated synthesis',
  )
  await expect(result).toContainText(
    'Use Alpha while Beta needs review.',
  )
  await expect(result).toContainText(
    'Supporting LeLe',
  )

  await expect(
    page.getByTestId(
      'ask-vault-citation-python/alpha',
    ),
  ).toContainText('Active')

  await expect(
    page.getByTestId(
      'ask-vault-citation-python/beta',
    ),
  ).toContainText('Review needed')
})

test('Ask this Vault presents insufficient support distinctly from an answer', async ({
  page,
}) => {
  await page.route('**/context-packs', route =>
    route.fulfill({ json: [] }),
  )

  await page.route('**/lessons/search', route =>
    route.fulfill({
      json: [alpha],
    }),
  )

  await page.route('**/ask-vault', route =>
    route.fulfill({
      json: {
        outcome: 'insufficient-support',
        answer:
          'The maintained LeLe do not contain enough information to answer.',
        generated_synthesis: true,
        citations: [],
        scope_lesson_ids: ['python/alpha'],
      },
    }),
  )

  await page.goto('/app/#/browse')

  await page
    .getByRole('button', {
      name: 'Search',
      exact: true,
    })
    .click()

  const ask = page.getByTestId('ask-vault-results')

  await ask
    .getByLabel('Question')
    .fill('Unknown detail?')

  await ask
    .getByRole('button', {
      name: 'Ask this Vault',
      exact: true,
    })
    .click()

  const result = page.getByTestId(
    'ask-vault-results-result',
  )

  await expect(result).toContainText(
    'Insufficient Vault support',
  )

  await expect(result).not.toContainText(
    'Supporting LeLe',
  )
})

test('Ask this Vault localizes its boundary in Italian without changing machine scope', async ({
  page,
}) => {
  await page.addInitScript(() => {
    localStorage.setItem(
      'lele-manager.locale',
      'it',
    )
  })

  await page.route('**/context-packs', route =>
    route.fulfill({ json: [] }),
  )

  await page.route('**/lessons/search', route =>
    route.fulfill({
      json: [alpha],
    }),
  )

  await page.route('**/ask-vault', route =>
    route.fulfill({
      json: {
        outcome: 'answered',
        answer: 'Risposta fondata.',
        generated_synthesis: true,
        citations: [
          {
            lesson_id: 'python/alpha',
            title: 'Alpha',
            lifecycle: 'active',
            superseded_by: null,
          },
        ],
        scope_lesson_ids: ['python/alpha'],
      },
    }),
  )

  await page.goto('/app/#/browse')

  await page
    .getByRole('button', {
      name: 'Cerca',
      exact: true,
    })
    .click()

  const ask = page.getByTestId('ask-vault-results')

  await expect(ask).toContainText(
    'Chiedi a questo Vault',
  )

  await ask
    .getByLabel('Domanda')
    .fill('Cosa dice il Vault?')

  await ask
    .getByRole('button', {
      name: 'Chiedi a questo Vault',
      exact: true,
    })
    .click()

  await expect(
    page.getByTestId('ask-vault-results-result'),
  ).toContainText('Sintesi generata')
})
