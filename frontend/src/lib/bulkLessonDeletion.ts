import {
  ApiError,
  api,
  type BulkLessonDeleteResponse,
  type BulkRefreshOutcome,
} from './api'

export type BulkLessonDeletionOutcome =
  | { kind: 'refreshed'; response: BulkLessonDeleteResponse }
  | { kind: 'refresh-failed'; response: BulkLessonDeleteResponse }

function isRefreshOutcome(value: unknown): value is BulkRefreshOutcome {
  if (typeof value !== 'object' || value === null) return false
  const item = value as Record<string, unknown>
  return typeof item.attempted === 'boolean' && typeof item.refreshed === 'boolean'
}

function bulkRecovery(error: unknown): BulkLessonDeleteResponse | null {
  if (!(error instanceof ApiError) || error.code !== 'bulk_lessons_deleted_refresh_failed') {
    return null
  }
  const recovery = error.recovery
  if (
    !recovery
    || typeof recovery.requested_count !== 'number'
    || !Array.isArray(recovery.deleted)
    || !Array.isArray(recovery.failed)
    || !isRefreshOutcome(recovery.refresh_outcome)
  ) {
    return null
  }
  return recovery as unknown as BulkLessonDeleteResponse
}

export async function bulkDeleteLessonsWithOutcome(
  lessonIds: string[],
): Promise<BulkLessonDeletionOutcome> {
  try {
    return { kind: 'refreshed', response: await api.bulkDeleteLessons(lessonIds) }
  } catch (error) {
    const recovery = bulkRecovery(error)
    if (recovery) return { kind: 'refresh-failed', response: recovery }
    throw error
  }
}
