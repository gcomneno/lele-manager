<script lang="ts">
  import type { Lesson } from '../lib/api'

  interface Props {
    lesson: Lesson
    selected?: boolean
    onclick?: () => void
  }

  let { lesson, selected = false, onclick }: Props = $props()
</script>

<button class="lesson-card" class:selected type="button" {onclick}>
  <div class="top">
    <strong>{lesson.id}</strong>
    <span class="meta">{lesson.topic ?? '—'}</span>
  </div>
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

  .top {
    display: flex;
    justify-content: space-between;
    gap: 8px;
    margin-bottom: 4px;
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
