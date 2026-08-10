export type LessonDeletionNotice = 'deleted' | 'refresh-failed'

const storageKey = 'lele-manager.lesson-deletion-notice'

export function setLessonDeletionNotice(notice: LessonDeletionNotice): void {
  try {
    sessionStorage.setItem(storageKey, notice)
  } catch {
    // A blocked session store must not prevent safe post-delete navigation.
  }
}

export function consumeLessonDeletionNotice(): LessonDeletionNotice | null {
  try {
    const value = sessionStorage.getItem(storageKey)
    sessionStorage.removeItem(storageKey)
    return value === 'deleted' || value === 'refresh-failed' ? value : null
  } catch {
    return null
  }
}
