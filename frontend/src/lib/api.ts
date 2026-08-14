export interface Lesson {
  id: string
  text: string
  topic?: string | null
  source?: string | null
  importance?: number | null
  tags?: string[] | null
  date?: string | null
  title?: string | null
  created_at?: string | null
}

export interface LessonSearchRequest {
  q?: string | null
  topic_in?: string[] | null
  source_in?: string[] | null
  importance_gte?: number | null
  importance_lte?: number | null
  limit?: number
}

export interface ExportSearchRequest extends LessonSearchRequest {
  include_frontmatter?: boolean
  ids_in?: string[] | null
}

export interface ExportSearchResponse {
  markdown: string
  n_lessons: number
}

export interface SimilarItem {
  id: string
  score: number
  text_preview: string
  rank?: number | null
  topic?: string | null
  tags_shared?: string[] | null
}

export interface SimilarMeta {
  data_mtime_ns: number
  model_mtime_ns: number
  top_k: number
  min_score: number
  query_topic?: string | null
  query_tags?: string[] | null
}

export interface SimilarResponse {
  query: string
  results: SimilarItem[]
  meta?: SimilarMeta | null
}

export interface HealthResponse {
  status: string
  has_data: boolean
  has_model: boolean
}

export interface RuntimeInfoResponse {
  version: string
}

export interface DashboardCandidateSummary {
  total: number
  staged: number
  in_review: number
  rejected: number
  approved: number
}

export interface DashboardSummaryResponse {
  health_status: string
  vault_exists: boolean
  vault_markdown_files: number | null
  projection_exists: boolean
  model_exists: boolean
  stats: StatsSummaryResponse | null
  candidates: DashboardCandidateSummary | null
}

export type RuntimePathRole =
  | 'authoritative_user_data'
  | 'persistent_application_state'
  | 'derived_rebuildable_artifact'
  | 'cache_temporary_state'

export type RuntimePathProvenanceKind =
  | 'configuration_override'
  | 'legacy_override'
  | 'platform_default'
  | 'product_default'
  | 'runtime_override'
  | 'managed_registry'

export interface RuntimePathProvenanceResponse {
  kind: RuntimePathProvenanceKind
  variable: string | null
  deprecated: boolean
}

export interface RuntimePathResponse {
  key: string
  path: string
  role: RuntimePathRole
  exists: boolean
  kind: 'directory' | 'file'
  provenance: RuntimePathProvenanceResponse
}

export interface SettingsRuntimeResponse {
  version: string
  health: HealthResponse
  paths: RuntimePathResponse[]
}

export interface AboutResponse {
  product_name: string
  version: string
  tagline: string
  attribution: string
  license_id: string
  license_summary: string
  license_url: string
  local_first_statement: string
  repository_url: string
  issue_tracker_url: string
  releases_url: string
  changelog_url: string
  documentation_url: string
  python_version: string
  platform_system: string
  platform_release: string
}

export interface DiagnosticsPreviewResponse {
  product_name: string
  version: string
  python_version: string
  platform_system: string
  platform_release: string
  health: HealthResponse
  paths: RuntimePathResponse[]
}

export interface TrainResponse {
  message: string
  n_lessons: number
  topics: string[]
}

export interface VaultStatusResponse {
  vault_dir: string
  exists: boolean
  vault_id?: string | null
  display_name?: string | null
}

export interface ManagedVault {
  id: string
  name: string
  path: string
  active: boolean
  available: boolean
  lesson_count: number | null
}

export interface VaultTreeNode {
  type: 'dir' | 'file'
  name: string
  path?: string
  id?: string
  children?: VaultTreeNode[]
}

export interface VaultTreeResponse {
  vault_dir: string
  tree: VaultTreeNode
}

export interface VaultImportResponse {
  message: string
  n_lessons: number
  output_path: string
  topics: string[]
}

export interface VaultDoctorProblem {
  code: string
  message: string
  path: string
  field?: string | null
  severity: 'error'
}

export interface VaultDoctorReportResponse {
  valid: boolean
  files_checked: number
  checked_files: string[]
  unique_ids: number
  error_count: number
  problems: VaultDoctorProblem[]
}

export interface VaultRestorePreview {
  plan_digest: string
  target_vault_id: string
  target_name: string
  target_path: string
  source_vault_id: string
  source_vault_name: string
  canonical_file_count: number
  additions: string[]
  replacements: string[]
  removals: string[]
  unchanged: string[]
  editorial_state: string[]
  derived_effects: string[]
}

export interface VaultRestoreResponse {
  canonical_restored: boolean
  rollback_succeeded: boolean | null
  derived_reconciled: boolean
  derived_error: string | null
  preview: VaultRestorePreview
}

export type VaultTransferOperation = 'merge' | 'copy' | 'move'
export type VaultTransferResolution = 'transfer' | 'keep_destination' | 'skip'
export type VaultTransferClassification = 'new' | 'identical' | 'already_present' | 'same_id' | 'path_conflict' | 'likely_duplicate'

export interface VaultTransferSelection {
  lesson_id: string
  resolution?: VaultTransferResolution | null
}

export interface VaultTransferItemPreview {
  lesson_id: string
  source_path: string
  source_sha256: string
  destination_path: string
  destination_sha256: string | null
  classification: VaultTransferClassification
  resolution: VaultTransferResolution | null
  duplicate_lesson_ids: string[]
}

export interface VaultTransferPreview {
  plan_digest: string
  operation: VaultTransferOperation
  source_vault_id: string
  source_name: string
  source_path: string
  destination_vault_id: string
  destination_name: string
  destination_path: string
  items: VaultTransferItemPreview[]
}

export interface VaultTransferResult {
  lesson_id: string
  source_path: string
  destination_path: string
  outcome: string
  destination_canonical: string
  destination_derived: string
  source_canonical: string
  source_derived: string
}

export interface VaultTransferResponse {
  preview: VaultTransferPreview
  items: VaultTransferResult[]
  destination_derived_reconciled: boolean | null
  destination_derived_error: string | null
  source_derived_reconciled: boolean | null
  source_derived_error: string | null
}

export interface VaultTransferSourceLesson {
  lesson_id: string
  source_path: string
}

export type VaultDangerOperation = 'empty' | 'reset' | 'delete' | 'merge_delete_source'

export interface VaultDangerPreview {
  plan_digest: string
  operation: VaultDangerOperation
  vault_id: string
  vault_name: string
  vault_path: string
  active: boolean
  approved_count: number
  filesystem_entry_count: number
  candidate_state_present: boolean
  duplicate_decision_count: number
  confirmation_text: string
  deletes: string[]
  keeps: string[]
  destination_vault_id: string | null
  destination_name: string | null
  destination_path: string | null
  merge_verified: boolean
}

export interface VaultDangerResult {
  preview: VaultDangerPreview
  backup_path: string | null
  canonical_deleted: number
  canonical_complete: boolean
  canonical_error: string | null
  editorial_cleared: boolean | null
  editorial_error: string | null
  derived_cleared: boolean | null
  derived_error: string | null
  vault_directory_deleted: boolean | null
  vault_directory_error: string | null
  registry_removed: boolean | null
  registry_error: string | null
  partial: boolean
}

export interface LessonVaultWrite {
  text: string
  topic: string
  source?: string
  importance?: number
  tags?: string[] | null
  date?: string | null
  title?: string | null
}

export interface LessonVaultCreate extends LessonVaultWrite {
  id?: string | null
}

export interface LessonDeleteResponse {
  lesson_id: string
  relative_vault_path: string
  canonical_deleted: true
  refresh_outcome: { refreshed: boolean }
}

export interface BulkLessonDeleteRequest {
  lesson_ids: string[]
}

export interface BulkLessonDeleteDeletedItem {
  lesson_id: string
  relative_vault_path: string
}

export interface BulkLessonDeleteFailedItem {
  lesson_id: string
  code: 'not_found' | 'storage_error'
}

export interface BulkRefreshOutcome {
  attempted: boolean
  refreshed: boolean
}

export interface BulkLessonDeleteResponse {
  requested_count: number
  deleted: BulkLessonDeleteDeletedItem[]
  failed: BulkLessonDeleteFailedItem[]
  refresh_outcome: BulkRefreshOutcome
}

export interface OpsRefreshResponse {
  import_result: VaultImportResponse
  train_result?: TrainResponse | null
}

export interface TagCount {
  tag: string
  count: number
}

export interface TopicCount {
  topic: string
  count: number
}

export interface MetadataOption {
  value: string
  count: number
}

export interface EditorMetadataOptionsResponse {
  topics: MetadataOption[]
  tags: MetadataOption[]
  sources: MetadataOption[]
}

export interface StatsSummaryResponse {
  n_lessons: number
  n_topics: number
  n_unique_tags: number
  avg_text_length: number
  avg_importance: number | null
  top_tags: TagCount[]
  by_topic: TopicCount[]
}

export interface TimelineBucket {
  key: string
  count: number
  lesson_ids: string[]
}

export interface TimelineResponse {
  group_by: string
  buckets: TimelineBucket[]
}

export type DuplicateKind = 'exact' | 'near'

export interface DuplicateLessonSnapshot extends Lesson {
  path?: string | null
}

export interface DuplicatePair {
  left_id: string
  right_id: string
  left_position: number
  right_position: number
  left_path?: string | null
  right_path?: string | null
  kind: DuplicateKind
  score: number
  reasons: string[]
  shared_tags: string[]
  left_fingerprint: string
  right_fingerprint: string
  resolution_available: boolean
  resolution_problem?: string | null
  left_lesson: DuplicateLessonSnapshot
  right_lesson: DuplicateLessonSnapshot
}

export interface DuplicateReportResponse {
  lessons_analyzed: number
  total_pairs: number
  exact_pairs: number
  near_pairs: number
  min_score: number
  exact_only: boolean
  suppressed_pairs: number
  pairs: DuplicatePair[]
}

export interface DuplicateDecisionResponse {
  left_id: string
  right_id: string
  left_fingerprint: string
  right_fingerprint: string
  decided_at: string
}

export interface DuplicateMergeResponse {
  completed: boolean
  survivor_id: string
  survivor_written: boolean
  superseded_id: string
  superseded_deleted: boolean
  refresh_outcome: { attempted: boolean; refreshed: boolean }
  failure?: { code: string; message: string } | null
}

export interface DuplicateQuery {
  min_score: number
  exact_only: boolean
  limit?: number | null
}

export type CandidateState = 'staged' | 'in_review' | 'rejected' | 'approved'
export type SourceKind = 'markdown' | 'plain_text' | 'stdin' | 'in_memory'

export interface ApprovalDestination {
  lesson_id: string
  relative_vault_path: string
}

export interface CandidateProvenance {
  source_kind: SourceKind
  source_logical_name: string
  source_fingerprint: string
  ingested_at: string
  chunk_index: number | null
  source_span: { start: number; end: number } | null
  run_metadata: Record<string, unknown>
  transformations: Record<string, unknown>[]
}

export interface CandidateReviewEvent {
  revision: number
  action: 'revised' | 'accepted' | 'rejected' | 'approved'
  occurred_at: string
  previous_state: CandidateState
  resulting_state: CandidateState
  reason: string | null
}

export interface CanonicalMetadata {
  topic: string
  source: string
  importance: number
  tags: string[]
  date: string
  title: string
}

export interface Candidate {
  candidate_id: string
  state: CandidateState
  revision: number
  original_text: string
  proposed_text: string | null
  effective_text: string
  proposed_metadata: CanonicalMetadata | null
  approval_destination: ApprovalDestination | null
  provenance: CandidateProvenance
  review_history: CandidateReviewEvent[]
}

export interface RawSourceInput {
  content: string
  source_kind: SourceKind
  logical_name: string
  max_characters: number
}

export interface IngestionResult {
  preview: boolean
  source: { kind: SourceKind; logical_name: string; fingerprint: string }
  chunking: { max_characters: number }
  candidate_ids: string[]
  created_candidate_ids: string[]
  skipped_candidate_ids: string[]
  pending_candidate_ids: string[]
  counts: { planned: number; created: number; skipped: number; pending: number }
  candidates: Candidate[]
}

export interface CandidateFilters {
  state?: CandidateState | ''
  source_kind?: SourceKind | ''
  source_fingerprint?: string
  source_logical_name?: string
  chunk_index?: number | null
}

export interface CandidateListResponse {
  count: number
  candidates: Candidate[]
}

export interface CandidateRevisionInput {
  expected_revision: number
  proposed_text?: string
  proposed_metadata?: CanonicalMetadata
  reason?: string
}

export interface ApprovalResult {
  candidate_id: string
  candidate_revision: number
  lesson_id: string
  relative_vault_path: string
  vault_write_outcome: 'created' | 'identical'
  candidate_state_changed: boolean
  refresh_outcome: { refreshed: boolean }
}

export interface ApiErrorDetail {
  code: string
  message: string
  recovery?: Record<string, unknown> | null
}

function isApiErrorDetail(value: unknown): value is ApiErrorDetail {
  if (typeof value !== 'object' || value === null) return false
  const candidate = value as Record<string, unknown>
  return typeof candidate.code === 'string' && typeof candidate.message === 'string'
}

export class ApiError extends Error {
  readonly status: number
  readonly detail: unknown
  readonly code: string | null
  readonly recovery: Record<string, unknown> | null

  constructor(status: number, detail: unknown) {
    const message =
      typeof detail === 'string'
        ? detail
        : detail != null
          ? JSON.stringify(detail)
          : `HTTP ${status}`
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
    this.code = isApiErrorDetail(detail) ? detail.code : null
    this.recovery = isApiErrorDetail(detail) ? (detail.recovery ?? null) : null
  }
}

async function responseError(resp: Response): Promise<ApiError> {
  const data = (await resp.json().catch(() => ({}))) as { detail?: unknown }
  return new ApiError(resp.status, data.detail)
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const resp = await fetch(path, init)
  const data = await resp.json().catch(() => ({}))
  if (!resp.ok) {
    throw new ApiError(resp.status, (data as { detail?: unknown }).detail)
  }
  return data as T
}


export const api = {
  health: () => request<HealthResponse>('/health'),

  runtimeInfo: () => request<RuntimeInfoResponse>('/runtime/info'),

  dashboardSummary: () =>
    request<DashboardSummaryResponse>('/dashboard/summary'),

  settingsRuntime: () =>
    request<SettingsRuntimeResponse>('/settings/runtime'),

  about: () =>
    request<AboutResponse>('/about'),

  diagnosticsPreview: () =>
    request<DiagnosticsPreviewResponse>('/diagnostics/preview'),

  duplicates: ({ min_score, exact_only, limit }: DuplicateQuery) => {
    const params = new URLSearchParams({
      min_score: String(min_score),
      exact_only: String(exact_only),
    })
    if (limit != null) params.set('limit', String(limit))
    return request<DuplicateReportResponse>(`/duplicates?${params.toString()}`)
  },

  markNotDuplicates: (pair: Pick<DuplicatePair, 'left_id' | 'right_id' | 'left_fingerprint' | 'right_fingerprint'>) =>
    request<DuplicateDecisionResponse>('/duplicates/not-duplicates', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(pair),
    }),

  mergeDuplicates: (body: {
    survivor_id: string
    superseded_id: string
    expected_survivor_fingerprint: string
    expected_superseded_fingerprint: string
    result: LessonVaultWrite
  }) => request<DuplicateMergeResponse>('/duplicates/merge', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
  }),

  listLessons: (limit = 50) =>
    request<Lesson[]>(`/lessons?limit=${encodeURIComponent(limit)}`),

  searchLessons: (body: LessonSearchRequest) =>
    request<Lesson[]>('/lessons/search', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),

  exportSearch: async (
    body: ExportSearchRequest,
    format: 'markdown' | 'json' = 'markdown',
  ): Promise<string | ExportSearchResponse> => {
    const resp = await fetch(`/export/search?format=${encodeURIComponent(format)}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
    if (!resp.ok) {
      throw await responseError(resp)
    }
    if (format === 'json') {
      return (await resp.json()) as ExportSearchResponse
    }
    return resp.text()
  },

  getLesson: (id: string) =>
    request<Lesson>(`/lessons/${encodeURIComponent(id)}`),

  similarById: (id: string, topK = 5, minScore = 0, explain = false) =>
    request<SimilarResponse>(
      `/lessons/${encodeURIComponent(id)}/similar?top_k=${topK}&min_score=${minScore}&explain=${explain ? 'true' : 'false'}`,
    ),

  similarByText: (text: string, topK = 5, minScore = 0.1, explain = false) =>
    request<SimilarResponse>(`/similar?explain=${explain ? 'true' : 'false'}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text, top_k: topK, min_score: minScore }),
    }),

  editorSuggest: (text: string, topK = 5, minScore = 0.1, explain = false) =>
    request<SimilarResponse>(`/editor/suggest?explain=${explain ? 'true' : 'false'}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text, top_k: topK, min_score: minScore }),
    }),

  editorMetadataOptions: () =>
    request<EditorMetadataOptionsResponse>('/editor/metadata-options'),

  trainTopic: () =>
    request<TrainResponse>('/train/topic', { method: 'POST' }),

  vaultStatus: () => request<VaultStatusResponse>('/vault/status'),

  vaults: () => request<ManagedVault[]>('/vaults'),

  downloadVaultSnapshot: async (id: string): Promise<Blob> => {
    const resp = await fetch(`/vaults/${encodeURIComponent(id)}/snapshot`)
    if (!resp.ok) throw await responseError(resp)
    return resp.blob()
  },

  previewVaultRestore: (id: string, artifact: Blob) =>
    request<VaultRestorePreview>(`/vaults/${encodeURIComponent(id)}/restore/preview`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/zip' },
      body: artifact,
    }),

  restoreVaultSnapshot: (id: string, artifact: Blob, planDigest: string) =>
    request<VaultRestoreResponse>(`/vaults/${encodeURIComponent(id)}/restore?plan_digest=${encodeURIComponent(planDigest)}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/zip' },
      body: artifact,
    }),

  previewVaultTransfer: (body: {
    source_vault_id: string
    destination_vault_id: string
    operation: VaultTransferOperation
    selections: VaultTransferSelection[]
  }) => request<VaultTransferPreview>('/vault-transfers/preview', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
  }),

  executeVaultTransfer: (body: {
    source_vault_id: string
    destination_vault_id: string
    operation: VaultTransferOperation
    selections: VaultTransferSelection[]
    plan_digest: string
  }) => request<VaultTransferResponse>('/vault-transfers/execute', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
  }),

  vaultTransferSourceLessons: (id: string) =>
    request<VaultTransferSourceLesson[]>(`/vault-transfers/sources/${encodeURIComponent(id)}/lessons`),

  previewVaultDanger: (body: {
    vault_id: string
    operation: VaultDangerOperation
    destination_vault_id?: string | null
  }) => request<VaultDangerPreview>('/vault-danger/preview', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
  }),

  executeVaultDanger: (body: {
    vault_id: string
    operation: VaultDangerOperation
    destination_vault_id?: string | null
    plan_digest: string
    confirmation: string
    backup_before: boolean
  }) => request<VaultDangerResult>('/vault-danger/execute', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
  }),

  createVault: (name: string, path: string) => request<ManagedVault>('/vaults/create', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, path }),
  }),

  registerVault: (name: string, path: string) => request<ManagedVault>('/vaults/register', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, path }),
  }),

  renameVault: (id: string, name: string) => request<ManagedVault>(`/vaults/${encodeURIComponent(id)}`, {
    method: 'PATCH', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name }),
  }),

  activateVault: (id: string) => request<VaultStatusResponse>(`/vaults/${encodeURIComponent(id)}/activate`, { method: 'POST' }),

  removeVault: (id: string) => request<void>(`/vaults/${encodeURIComponent(id)}`, { method: 'DELETE' }),

  vaultTree: () => request<VaultTreeResponse>('/vault/tree'),

  vaultDoctor: () => request<VaultDoctorReportResponse>('/vault/doctor'),

  vaultImport: () =>
    request<VaultImportResponse>('/vault/import', { method: 'POST' }),

  createVaultLesson: (body: LessonVaultCreate) =>
    request<Lesson>('/vault/lessons', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),

  updateLesson: (id: string, body: LessonVaultWrite) =>
    request<Lesson>(`/lessons/${encodeURIComponent(id)}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),

  deleteLesson: (id: string) =>
    request<LessonDeleteResponse>(`/lessons/${encodeURIComponent(id)}`, {
      method: 'DELETE',
    }),

  bulkDeleteLessons: (lessonIds: string[]) =>
    request<BulkLessonDeleteResponse>('/lessons/bulk-delete', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ lesson_ids: lessonIds } satisfies BulkLessonDeleteRequest),
    }),

  opsRefresh: (train = true) =>
    request<OpsRefreshResponse>(`/ops/refresh?train=${train ? 'true' : 'false'}`, {
      method: 'POST',
    }),

  statsSummary: () => request<StatsSummaryResponse>('/stats/summary'),

  statsTimeline: (groupBy: 'year' | 'month' | 'topic' = 'month') =>
    request<TimelineResponse>(`/stats/timeline?group_by=${encodeURIComponent(groupBy)}`),

  previewIngestion: (body: RawSourceInput) =>
    request<IngestionResult>('/api/v1/tritalele/ingestion/preview', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),

  stageIngestion: (body: RawSourceInput) =>
    request<IngestionResult>('/api/v1/tritalele/ingestion/stage', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),

  listCandidates: (filters: CandidateFilters = {}) => {
    const query = new URLSearchParams()
    if (filters.state) query.set('state', filters.state)
    if (filters.source_kind) query.set('source_kind', filters.source_kind)
    if (filters.source_fingerprint?.trim()) {
      query.set('source_fingerprint', filters.source_fingerprint.trim())
    }
    if (filters.source_logical_name?.trim()) {
      query.set('source_logical_name', filters.source_logical_name.trim())
    }
    if (filters.chunk_index != null) query.set('chunk_index', String(filters.chunk_index))
    const suffix = query.size ? `?${query.toString()}` : ''
    return request<CandidateListResponse>(`/api/v1/tritalele/candidates${suffix}`)
  },

  getCandidate: (candidateId: string) =>
    request<Candidate>(`/api/v1/tritalele/candidates/${encodeURIComponent(candidateId)}`),

  reviseCandidate: (candidateId: string, body: CandidateRevisionInput) =>
    request<Candidate>(`/api/v1/tritalele/candidates/${encodeURIComponent(candidateId)}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),

  acceptCandidate: (candidateId: string, expectedRevision: number, reason?: string) =>
    request<Candidate>(
      `/api/v1/tritalele/candidates/${encodeURIComponent(candidateId)}/accept`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          expected_revision: expectedRevision,
          ...(reason?.trim() ? { reason: reason.trim() } : {}),
        }),
      },
    ),

  rejectCandidate: (candidateId: string, expectedRevision: number, reason?: string) =>
    request<Candidate>(
      `/api/v1/tritalele/candidates/${encodeURIComponent(candidateId)}/reject`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          expected_revision: expectedRevision,
          ...(reason?.trim() ? { reason: reason.trim() } : {}),
        }),
      },
    ),

  approveCandidate: (candidateId: string, expectedRevision: number) =>
    request<ApprovalResult>(
      `/api/v1/tritalele/candidates/${encodeURIComponent(candidateId)}/approve`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ expected_revision: expectedRevision }),
      },
    ),
}
