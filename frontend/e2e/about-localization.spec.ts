import { expect, test, type Page } from '@playwright/test'
import { en } from '../src/lib/i18n/en'
import { it } from '../src/lib/i18n/it'
import type { AboutResponse } from '../src/lib/api'

const about: AboutResponse = {
  product_name: 'LeLe Manager', version: '1.10.1',
  tagline: 'Your local-first lessons learned workspace', attribution: 'GiadaWare',
  license_id: 'MIT',
  license_summary: 'Open-source software distributed under the MIT License.',
  license_url: '/app/LICENSE',
  local_first_statement:
    'LeLe Manager itself introduces no account, telemetry, cloud storage, or remote knowledge service.',
  repository_url: 'https://github.com/gcomneno/lele-manager',
  issue_tracker_url: 'https://github.com/gcomneno/lele-manager/issues',
  releases_url: 'https://github.com/gcomneno/lele-manager/releases',
  changelog_url: 'https://github.com/gcomneno/lele-manager/blob/main/CHANGELOG.md',
  documentation_url: 'https://github.com/gcomneno/lele-manager/blob/main/docs/gui-user-guide.md',
  python_version: '3.12.0', platform_system: 'Linux', platform_release: 'fixture',
}

// Explicit copy inventory: descriptions, metadata, actions and accessible names.
const copy = {
  en: {
    title: 'About', language: 'Language',
    tagline: 'Your local-first lessons learned workspace',
    version: 'Version', license: 'License',
    summary: 'Open-source software distributed under the MIT License.',
    fullLicense: 'Full license', runtime: 'Runtime', localFirst: 'Local-first',
    statement: 'LeLe Manager itself introduces no account, telemetry, cloud storage, or remote knowledge service.',
    links: ['Repository', 'Issue tracker', 'Releases', 'Changelog', 'Documentation'],
  },
  it: {
    title: 'Informazioni', language: 'Lingua',
    tagline: 'Il tuo spazio di lavoro locale per le lezioni apprese',
    version: 'Versione', license: 'Licenza',
    summary: 'Software open source distribuito con licenza MIT.',
    fullLicense: 'Licenza completa', runtime: 'Ambiente di esecuzione',
    localFirst: 'Priorità ai dati locali',
    statement: 'LeLe Manager non introduce account, telemetria, archiviazione nel cloud o servizi remoti per la gestione della conoscenza.',
    links: ['Codice sorgente', 'Segnalazioni', 'Versioni rilasciate', 'Registro delle modifiche', 'Documentazione'],
  },
} as const

async function expectAbout(page: Page, locale: keyof typeof copy) {
  const text = copy[locale]
  const panel = page.getByRole('region', { name: text.title, exact: true })
  // Exact full content also detects residual copy from the previous locale.
  await expect(panel).toHaveText([
    text.title, about.product_name, text.tagline, about.attribution,
    text.version, about.version, text.license, about.license_id, text.summary,
    text.fullLicense, text.runtime, 'Linux fixture', 'Python 3.12.0',
    text.localFirst, text.statement, ...text.links,
  ].join(' '), { useInnerText: true })
  await expect(panel.getByRole('heading', { name: text.title, exact: true })).toBeVisible()
  await expect(panel.getByRole('heading', { name: about.product_name, exact: true })).toBeVisible()
  await expect(panel.getByRole('link', { name: text.fullLicense, exact: true }))
    .toHaveAttribute('href', about.license_url)
  const support = panel.getByRole('navigation', { name: text.title, exact: true })
  const urls = [about.repository_url, about.issue_tracker_url, about.releases_url,
    about.changelog_url, about.documentation_url]
  for (const [index, label] of text.links.entries()) {
    const link = support.getByRole('link', { name: label, exact: true })
    await expect(link).toHaveAttribute('href', urls[index]!)
    await expect(link).toHaveAttribute('target', '_blank')
    await expect(link).toHaveAttribute('rel', 'noreferrer')
  }
  await expect(page.getByLabel(text.language, { exact: true })).toHaveValue(locale)
  await expect(page.locator('a[href="#/about"]')).toHaveAccessibleName(text.title)
  await expect(page).toHaveURL(/#\/about$/)
}

test('Italian catalog preserves the canonical English keys and About placeholders', () => {
  expect(Object.keys(it).sort()).toEqual(Object.keys(en).sort())
  for (const key of Object.keys(en) as (keyof typeof en)[]) {
    if (key.startsWith('about')) {
      expect(it[key].match(/\{\w+\}/g) ?? []).toEqual(en[key].match(/\{\w+\}/g) ?? [])
      expect(it[key].trim()).not.toBe('')
    }
  }
})

for (const initial of ['en', 'it'] as const) {
  test(`About is fully localized from ${initial} and switches without stale copy`, async ({ page }) => {
    await page.addInitScript((locale) => {
      if (localStorage.getItem('lele-manager.locale') === null) {
        localStorage.setItem('lele-manager.locale', locale)
      }
    }, initial)
    let requests = 0
    await page.route('**/about', (route) => {
      requests += 1
      return route.fulfill({ json: about })
    })
    await page.goto('/app/#/about')
    await expectAbout(page, initial)
    const other = initial === 'en' ? 'it' : 'en'
    await page.getByLabel(copy[initial].language, { exact: true }).selectOption(other)
    await expectAbout(page, other)
    await page.getByLabel(copy[other].language, { exact: true }).selectOption(initial)
    await expectAbout(page, initial)
    expect(requests).toBe(1)
    expect(await page.evaluate(() => localStorage.getItem('lele-manager.locale'))).toBe(initial)
    await page.reload()
    await expectAbout(page, initial)
  })
}

test('About loading and error messages follow locale changes immediately', async ({ page }) => {
  let release!: () => void
  const pending = new Promise<void>((resolve) => { release = resolve })
  await page.route('**/about', async (route) => {
    await pending
    await route.fulfill({ status: 503, json: { detail: 'fixture-unavailable' } })
  })
  await page.goto('/app/#/about')
  const panel = page.locator('.about')
  await expect(panel).toContainText('Loading product information…')
  await page.getByLabel('Language', { exact: true }).selectOption('it')
  await expect(panel).toHaveText('Informazioni Caricamento delle informazioni sul prodotto…', { useInnerText: true })
  await page.getByLabel('Lingua', { exact: true }).selectOption('en')
  await expect(panel).toHaveText('About Loading product information…', { useInnerText: true })
  await page.getByLabel('Language', { exact: true }).selectOption('it')
  release()
  await expect(panel.getByRole('alert')).toHaveText('Impossibile caricare le informazioni: fixture-unavailable')
  await expect(panel).not.toContainText('Caricamento')
  await page.getByLabel('Lingua', { exact: true }).selectOption('en')
  await expect(panel.getByRole('alert')).toHaveText('Unable to load About information: fixture-unavailable')
  await expect(panel).not.toContainText('Impossibile')
  await page.getByLabel('Language', { exact: true }).selectOption('it')
  await expect(panel.getByRole('alert')).toHaveText('Impossibile caricare le informazioni: fixture-unavailable')
  await expect(panel).not.toContainText('Unable')
  await expect(panel.getByRole('navigation')).toHaveCount(0)
})
