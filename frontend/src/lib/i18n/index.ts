import { derived, writable } from 'svelte/store'

import { en, type Messages } from './en'
import { it } from './it'

export type Locale = 'en' | 'it'

export const DEFAULT_LOCALE: Locale = 'en'
export const LOCALE_STORAGE_KEY = 'lele-manager.locale'

const dictionaries: Record<Locale, Messages> = {
  en,
  it,
}

export function isLocale(value: unknown): value is Locale {
  return value === 'en' || value === 'it'
}

function loadPersistedLocale(): Locale {
  if (typeof window === 'undefined') {
    return DEFAULT_LOCALE
  }

  try {
    const persisted = window.localStorage.getItem(
      LOCALE_STORAGE_KEY,
    )

    return isLocale(persisted)
      ? persisted
      : DEFAULT_LOCALE
  } catch {
    return DEFAULT_LOCALE
  }
}

export const locale = writable<Locale>(
  loadPersistedLocale(),
)

export const messages = derived(
  locale,
  ($locale) => dictionaries[$locale],
)

export function setLocale(value: string): Locale {
  const nextLocale = isLocale(value)
    ? value
    : DEFAULT_LOCALE

  locale.set(nextLocale)

  if (typeof window !== 'undefined') {
    try {
      window.localStorage.setItem(
        LOCALE_STORAGE_KEY,
        nextLocale,
      )
    } catch {
      // Persistence is best-effort; the active locale still changes.
    }
  }

  return nextLocale
}
