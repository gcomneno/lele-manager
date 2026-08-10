<script lang="ts">
  import { tick } from 'svelte'
  import type { Lesson } from '../lib/api'
  import { messages } from '../lib/i18n'

  interface Props {
    lesson: Lesson | null
    oncancel: () => void
    onconfirm: (lesson: Lesson) => Promise<void>
  }

  let { lesson, oncancel, onconfirm }: Props = $props()
  let dialog = $state<HTMLDialogElement>()
  let cancelButton = $state<HTMLButtonElement>()
  let submitting = $state(false)

  $effect(() => {
    if (lesson && !dialog?.open) {
      void (async () => {
        await tick()
        dialog?.showModal()
        cancelButton?.focus()
      })()
    } else if (!lesson && dialog?.open) {
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
    if (!lesson || submitting) return
    submitting = true
    try {
      await onconfirm(lesson)
    } finally {
      submitting = false
    }
  }
</script>

<dialog
  bind:this={dialog}
  aria-labelledby="delete-lesson-title"
  oncancel={onCancel}
  onclose={onClose}
>
  {#if lesson}
    <div class="dialog-content">
      <h2 id="delete-lesson-title">{$messages.deleteLessonTitle}</h2>
      <dl>
        <div>
          <dt>{$messages.fieldTitle}</dt>
          <dd>{lesson.title?.trim() || $messages.deleteLessonUntitled}</dd>
        </div>
        <div>
          <dt>{$messages.deleteLessonId}</dt>
          <dd class="lesson-id">{lesson.id}</dd>
        </div>
      </dl>
      <p>{$messages.deleteLessonCanonical}</p>
      <p>{$messages.deleteLessonIrreversible}</p>
      <div class="dialog-actions">
        <button bind:this={cancelButton} type="button" disabled={submitting} onclick={() => dialog?.close()}>
          {$messages.deleteLessonCancel}
        </button>
        <button class="delete-button" type="button" disabled={submitting} onclick={() => void confirm()}>
          {submitting ? $messages.deleteLessonDeleting : $messages.deleteLessonDelete}
        </button>
      </div>
    </div>
  {/if}
</dialog>

<style>
  dialog {
    width: min(480px, calc(100vw - 32px));
    padding: 0;
    border: 1px solid var(--border);
    border-radius: var(--radius-lg);
    color: var(--color-text);
    background: var(--color-surface);
    box-shadow: 0 18px 48px rgb(36 28 22 / 28%);
  }

  dialog::backdrop { background: rgb(36 28 22 / 42%); }
  .dialog-content { padding: var(--space-4); }
  h2 { margin: 0 0 var(--space-3); }
  dl { display: grid; gap: var(--space-2); margin: 0 0 var(--space-3); }
  dl div { display: grid; gap: 2px; }
  dt { color: var(--color-text-muted); font-size: 0.85rem; }
  dd { margin: 0; overflow-wrap: anywhere; }
  .lesson-id { font-family: ui-monospace, monospace; font-size: 0.9rem; }
  .dialog-actions { display: flex; justify-content: flex-end; gap: var(--space-2); margin-top: var(--space-4); }
  button { border: 1px solid var(--border); border-radius: var(--radius-sm); background: var(--color-surface); color: var(--color-text); padding: 7px 11px; }
  .delete-button { border-color: #a22; background: #a22; color: white; font-weight: 700; }
  .delete-button:focus-visible, button:focus-visible { outline: 3px solid var(--accent); outline-offset: 2px; }
</style>
