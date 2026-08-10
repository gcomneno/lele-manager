import { ApiError, api, type LessonDeleteResponse } from './api'

export type LessonDeletionOutcome =
  | { kind: 'refreshed'; response: LessonDeleteResponse }
  | {
    kind: 'refresh-failed'
    lessonId: string
    relativeVaultPath: string
  }

function partialRecovery(error: unknown): {
  lessonId: string
  relativeVaultPath: string
} | null {
  if (!(error instanceof ApiError) || error.code !== 'lesson_deleted_refresh_failed') {
    return null
  }
  const recovery = error.recovery
  if (
    recovery?.canonical_deleted !== true
    || typeof recovery.lesson_id !== 'string'
    || typeof recovery.relative_vault_path !== 'string'
  ) {
    return null
  }
  return {
    lessonId: recovery.lesson_id,
    relativeVaultPath: recovery.relative_vault_path,
  }
}

export async function deleteLessonWithOutcome(
  lessonId: string,
): Promise<LessonDeletionOutcome> {
  try {
    return { kind: 'refreshed', response: await api.deleteLesson(lessonId) }
  } catch (error) {
    const recovery = partialRecovery(error)
    if (recovery) return { kind: 'refresh-failed', ...recovery }
    throw error
  }
}
