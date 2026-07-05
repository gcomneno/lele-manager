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
}

export interface SimilarResponse {
  query: string
  results: SimilarItem[]
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

  similarById: (id: string, topK = 5, minScore = 0) =>
    request<SimilarResponse>(
      `/lessons/${encodeURIComponent(id)}/similar?top_k=${topK}&min_score=${minScore}`,
    ),

  similarByText: (text: string, topK = 5, minScore = 0.1) =>
    request<SimilarResponse>('/similar', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text, top_k: topK, min_score: minScore }),
    }),

  editorSuggest: (text: string, topK = 5, minScore = 0.1) =>
    request<SimilarResponse>('/editor/suggest', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text, top_k: topK, min_score: minScore }),
    }),

  trainTopic: () =>
    request<TrainResponse>('/train/topic', { method: 'POST' }),
}
