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
  pairs: DuplicatePair[]
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
