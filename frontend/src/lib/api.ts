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

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const resp = await fetch(path, init)
  const data = await resp.json().catch(() => ({}))
  if (!resp.ok) {
    const detail = (data as { detail?: unknown }).detail
    const msg =
      typeof detail === 'string'
        ? detail
        : detail != null
          ? JSON.stringify(detail)
          : `HTTP ${resp.status}`
    throw new Error(msg)
  }
  return data as T
}

export const api = {
  health: () => request<HealthResponse>('/health'),

  listLessons: (limit = 50) =>
    request<Lesson[]>(`/lessons?limit=${encodeURIComponent(limit)}`),

  searchLessons: (body: LessonSearchRequest) =>
    request<Lesson[]>('/lessons/search', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),

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

  trainTopic: () =>
    request<TrainResponse>('/train/topic', { method: 'POST' }),

  vaultStatus: () => request<VaultStatusResponse>('/vault/status'),

  vaultTree: () => request<VaultTreeResponse>('/vault/tree'),

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

  opsRefresh: (train = true) =>
    request<OpsRefreshResponse>(`/ops/refresh?train=${train ? 'true' : 'false'}`, {
      method: 'POST',
    }),

  statsSummary: () => request<StatsSummaryResponse>('/stats/summary'),

  statsTimeline: (groupBy: 'year' | 'month' | 'topic' = 'month') =>
    request<TimelineResponse>(`/stats/timeline?group_by=${encodeURIComponent(groupBy)}`),
}
