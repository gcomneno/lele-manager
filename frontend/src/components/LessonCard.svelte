<script lang="ts">
  import type {
    Lesson,
    LessonLifecycleState,
  } from '../lib/api'

  interface Props {
    lesson: Lesson
    selected?: boolean
    lifecycleLabels?: Record<LessonLifecycleState, string>
    onclick?: () => void
  }

  let {
    lesson,
    selected = false,
    lifecycleLabels,
    onclick,
  }: Props = $props()

  const defaultLabels: Record<LessonLifecycleState, string> = {
    active: 'Active',
    'review-needed': 'Review needed',
    deprecated: 'Deprecated',
    archived: 'Archived',
  }

  let lifecycle = $derived<LessonLifecycleState>(
    lesson.lifecycle ?? 'active',
  )
  let lifecycleLabel = $derived(
    (lifecycleLabels ?? defaultLabels)[lifecycle],
  )
</script>

<button
  class="lesson-card"
  class:selected
  class:non-active={lifecycle !== 'active'}
  data-lifecycle={lifecycle}
  type="button"
  {onclick}
>
  <div class="top">
    <strong>{lesson.id}</strong>
    <span class="meta">{lesson.topic ?? '—'}</span>
  </div>

  {#if lifecycle !== 'active'}
    <div
      class={`lifecycle-badge lifecycle-${lifecycle}`}
      data-testid={`lifecycle-${lesson.id}`}
    >
      {lifecycleLabel}
    </div>
  {/if}

  <div class="meta row">
    <span>importance {lesson.importance ?? '?'}</span>
    <span>{lesson.source ?? '—'}</span>
    <span>{lesson.date ?? ''}</span>
  </div>
  <p>{(lesson.text ?? '').slice(0, 220)}{(lesson.text?.length ?? 0) > 220 ? '…' : ''}</p>
</button>

<style>
  .lesson-card {
    width: 100%;
    text-align: left;
    border: 1px solid var(--border);
    background: var(--surface);
    border-radius: var(--radius);
    padding: 12px;
    cursor: pointer;
  }

  .lesson-card:hover,
  .lesson-card.selected {
    border-color: var(--accent);
    background: #fffaf5;
  }

  .lesson-card.non-active {
    border-width: 2px;
  }

  .top {
    display: flex;
    justify-content: space-between;
    gap: 8px;
    margin-bottom: 4px;
  }

  .lifecycle-badge {
    display: inline-flex;
    width: fit-content;
    margin: 4px 0 8px;
    padding: 3px 8px;
    border: 1px solid currentColor;
    border-radius: 999px;
    font-size: 0.78rem;
    font-weight: 800;
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }

  .lifecycle-review-needed {
    color: #7a4b00;
    background: #fff4d6;
  }

  .lifecycle-deprecated {
    color: #8b1717;
    background: #fff0f0;
  }

  .lifecycle-archived {
    color: #4d5156;
    background: #f0f1f2;
  }

  .row {
    display: flex;
    gap: 12px;
    flex-wrap: wrap;
    margin-bottom: 8px;
  }

  p {
    margin: 0;
    line-height: 1.45;
  }
</style>
