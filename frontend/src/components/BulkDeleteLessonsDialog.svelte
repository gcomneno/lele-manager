<script lang="ts">
  import { tick } from 'svelte'
  import type { Lesson } from '../lib/api'
  import { formatMessage, messages } from '../lib/i18n'

  interface Props {
    lessons: Lesson[]
    oncancel: () => void
    onconfirm: (lessons: Lesson[]) => Promise<void>
  }

  let { lessons, oncancel, onconfirm }: Props = $props()
  let dialog = $state<HTMLDialogElement>()
  let cancelButton = $state<HTMLButtonElement>()
  let submitting = $state(false)

  $effect(() => {
    if (lessons.length && !dialog?.open) {
      void (async () => {
        await tick()
        dialog?.showModal()
        cancelButton?.focus()
      })()
    } else if (!lessons.length && dialog?.open) {
      dialog.close()
    }
  })

  function onCancel(event: Event) {
    if (submitting) event.preventDefault()
  }

  function onClose() {
    if (!submitting) oncancel()
  }

  async function confirm() {
    if (!lessons.length || submitting) return
    submitting = true
    try {
      await onconfirm(lessons)
    } finally {
      submitting = false
    }
  }
</script>

<dialog
  bind:this={dialog}
  aria-labelledby="delete-selected-lessons-title"
  oncancel={onCancel}
  onclose={onClose}
>
  {#if lessons.length}
    <div class="dialog-content">
      <h2 id="delete-selected-lessons-title">
        {formatMessage($messages.bulkDeleteTitle, { count: lessons.length })}
      </h2>
      <p>{$messages.bulkDeleteCanonical}</p>
      <p>{$messages.deleteLessonIrreversible}</p>
      <ul aria-label={$messages.bulkDeleteTargets}>
        {#each lessons as lesson (lesson.id)}
          <li>
            <strong>{lesson.title?.trim() || $messages.deleteLessonUntitled}</strong>
            <span>{lesson.id}</span>
          </li>
        {/each}
      </ul>
      <div class="dialog-actions">
        <button bind:this={cancelButton} type="button" disabled={submitting} onclick={() => dialog?.close()}>
          {$messages.deleteLessonCancel}
        </button>
        <button class="delete-button" type="button" disabled={submitting} onclick={() => void confirm()}>
          {submitting ? $messages.bulkDeleteDeleting : $messages.bulkDeleteSelected}
        </button>
      </div>
    </div>
  {/if}
</dialog>

<style>
  dialog { width: min(560px, calc(100vw - 32px)); padding: 0; border: 1px solid var(--border); border-radius: var(--radius-lg); color: var(--color-text); background: var(--color-surface); box-shadow: 0 18px 48px rgb(36 28 22 / 28%); }
  dialog::backdrop { background: rgb(36 28 22 / 42%); }
  .dialog-content { padding: var(--space-4); }
  h2 { margin: 0 0 var(--space-3); }
  ul { display: grid; gap: var(--space-2); max-height: min(44vh, 360px); margin: var(--space-3) 0; padding-left: var(--space-4); overflow-y: auto; }
  li { display: grid; gap: 2px; overflow-wrap: anywhere; }
  li span { font-family: ui-monospace, monospace; font-size: 0.9rem; }
  .dialog-actions { display: flex; justify-content: flex-end; gap: var(--space-2); margin-top: var(--space-4); }
  button { border: 1px solid var(--border); border-radius: var(--radius-sm); background: var(--color-surface); color: var(--color-text); padding: 7px 11px; }
  .delete-button { border-color: #a22; background: #a22; color: white; font-weight: 700; }
  .delete-button:focus-visible, button:focus-visible { outline: 3px solid var(--accent); outline-offset: 2px; }
</style>
