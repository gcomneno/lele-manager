export const en = {
  brandBrowseAccessible: 'LeLe Manager, browse',
  brandTagline: 'Your local space for your “Lessons Learned”',

  navBrowse: 'Browse',
  navTimeline: 'Timeline',
  navStatistics: 'Statistics',
  navNewLele: 'New LeLe',
  navCollection: 'Collection',
  navVault: 'Vault',
  navDuplicates: 'Duplicates',
  navSystem: 'System',

  languageLabel: 'Language',
  languageEnglish: 'English',
  languageItalian: 'Italian',

  makerOpenSource: 'Open-source software',

  newLeleAccessible: 'New LeLe',
  newLelePrefix: 'New',
} as const

export type TranslationKey = keyof typeof en

export type Messages = {
  [Key in TranslationKey]: string
}
