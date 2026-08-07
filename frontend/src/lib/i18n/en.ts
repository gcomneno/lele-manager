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

  commonLoading: 'Loading…',

  fieldQuery: 'Query',
  fieldTopic: 'Topic',
  fieldSource: 'Source',
  fieldImportance: 'Importance',
  fieldDate: 'Date',
  fieldTags: 'Tags',
  fieldTitle: 'Title',

  routeBrowseTitle: 'Browse',
  browseImportanceMin: 'Importance ≥',
  browseImportanceMax: 'Importance ≤',
  browseLimit: 'Limit',
  browseSearch: 'Search',
  browseListAll: 'List all',
  browseExportMarkdown: 'Export .md',
  browseExporting: 'Exporting…',
  browseReset: 'Reset',
  browseSearching: 'Searching…',
  browseExported: 'Exported {count} LeLe → Markdown',
  browseResults: '{count} results',
  browseLessons: '{count} lessons',
  browseEmpty: 'No LeLe found.',

  detailEdit: 'Edit',
  detailSimilarLessons: 'Similar LeLe',

  editorEditTitle: 'Edit LeLe',
  editorNewTitle: 'New LeLe',
  editorSaving: 'Saving…',
  editorSaveVault: 'Save to vault',
  editorBodyRequired: 'The body cannot be empty.',
  editorTopicRequired: 'Topic is required.',
  editorSaved: 'Saved to vault: {id}',
  editorIdPlaceholder: 'auto (topic/date.slug)',
  editorBodyLabel: 'Body (Markdown)',
  editorBodyPlaceholder: 'Write the lesson learned…',
  editorLiveSimilar: 'Live similarities',

  statsTitle: 'Statistics',
  statsUniqueTags: 'Unique tags',
  statsAverageLength: 'Average length',
  statsAverageImportance: 'Average importance',
  statsByTopic: 'By topic',
  statsNoData: 'No data.',
  statsTopTags: 'Most common tags',
  statsNoTags: 'No tags.',
  statsCharacters: 'chars',

  timelineTitle: 'Timeline',
  timelineMonth: 'Month',
  timelineYear: 'Year',
  timelineExport: 'Export',
  timelineEmpty: 'No LeLe in the dataset.',
  timelineMore: '+{count} more',

  vaultNotFound: 'Vault not found: {path}',
  vaultImporting: 'Importing…',
  vaultRefresh: 'Refresh',
  vaultImportJsonl: 'Import → JSONL',
  vaultNew: '+ New',

  similarWhy: 'Why similar?',
  similarDefaultTitle: 'Similar',
  similarQueryTopic: 'query topic',
  similarQueryTags: 'query tags',
  similarSharedTags: 'shared tags',
  similarEmpty: 'No results.',

  healthApiOffline: 'API offline',
  healthDataset: 'dataset',
  healthModel: 'model',
  healthOk: 'ok',
  healthMissing: 'missing',
  healthLoading: 'health…',
} as const

export type TranslationKey = keyof typeof en

export type Messages = {
  [Key in TranslationKey]: string
}
