<script lang="ts">
  import { FormStatus } from 'giadaware-ui-components'
  import {
    Button,
    Panel,
  } from 'giadaware-ui-components/studio'
  import {
    api,
    type Lesson,
    type SimilarItem,
    type SimilarMeta,
  } from '../lib/api'
  import { navigate } from '../lib/router'
  import { messages } from '../lib/i18n'
  import { deleteLessonWithOutcome } from '../lib/lessonDeletion'
  import { setLessonDeletionNotice } from '../lib/lessonDeletionNotice'
  import { renderMarkdown } from '../lib/markdown'
  import SimilarPanel from '../components/SimilarPanel.svelte'
  import DeleteLessonDialog from '../components/DeleteLessonDialog.svelte'

  interface Props {
    id: string
  }

  let { id }: Props = $props()

  let lesson = $state<Lesson | null>(null)
  let similar = $state<SimilarItem[]>([])
  let similarMeta = $state<SimilarMeta | null>(null)
  let loading = $state(true)
  let similarLoading = $state(false)
  let error = $state('')
  let similarError = $state('')
  let deleteTarget = $state<Lesson | null>(null)
  let deleteError = $state('')

  async function load() {
    loading = true
    error = ''

    try {
      lesson = await api.getLesson(id)
    } catch (e) {
      lesson = null
      error = e instanceof Error ? e.message : String(e)
    } finally {
      loading = false
    }
  }

  async function loadSimilar() {
    similarLoading = true
    similarError = ''

    try {
      const resp = await api.similarById(
        id,
        8,
        0.05,
        true,
      )
      similar = resp.results
      similarMeta = resp.meta ?? null
    } catch (e) {
      similar = []
      similarError = e instanceof Error
        ? e.message
        : String(e)
    } finally {
      similarLoading = false
    }
  }

  function inspectSimilarity() {
    document.getElementById('lesson-similarity')?.focus()
  }

  async function deleteLesson(lessonToDelete: Lesson) {
    deleteError = ''
    try {
      const outcome = await deleteLessonWithOutcome(lessonToDelete.id)
      setLessonDeletionNotice(
        outcome.kind === 'refreshed' ? 'deleted' : 'refresh-failed',
      )
      deleteTarget = null
      navigate({ view: 'browse' })
    } catch {
      deleteError = $messages.lessonDeleteFailed
      deleteTarget = null
    }
  }

  $effect(() => {
    if (!id) return
    load()
    loadSimilar()
  })
</script>

{#if loading}
  <p class="meta">{$messages.commonLoading}</p>
{:else if error}
  <FormStatus
    message={error}
    tone="error"
    style="--giu-form-status-padding: var(--space-2) var(--space-3)"
  />
{:else if lesson}
  <div class="detail-layout">
    <Panel title={lesson.id} class="main-pane">
      {#snippet actions()}
        <Button
          variant="secondary"
          size="compact"
          class="lele-secondary-button"
          onclick={() => navigate({
            view: 'editor',
            id: lesson!.id,
          })}
        >
          {$messages.lessonModify}
        </Button>
        <Button
          variant="secondary"
          size="compact"
          class="lele-secondary-button"
          onclick={inspectSimilarity}
        >
          {$messages.lessonInspect}
        </Button>
        <button
          type="button"
          class="delete-action"
          onclick={() => { deleteTarget = lesson }}
        >{$messages.deleteLessonDelete}</button>
      {/snippet}

      {#if deleteError}
        <FormStatus
          message={deleteError}
          tone="error"
          style="--giu-form-status-padding: var(--space-2) var(--space-3)"
        />
      {/if}

      <div class="meta row">
        <span>{$messages.fieldTopic}: {lesson.topic ?? '—'}</span>
        <span>{$messages.fieldSource}: {lesson.source ?? '—'}</span>
        <span>{$messages.fieldImportance}: {lesson.importance ?? '?'}</span>
        <span>{$messages.fieldDate}: {lesson.date ?? '—'}</span>
      </div>

      {#if lesson.tags?.length}
        <div class="tags">
          {#each lesson.tags as tag}
            <span class="tag">{tag}</span>
          {/each}
        </div>
      {/if}

      {#if lesson.title}
        <h3>{lesson.title}</h3>
      {/if}

      <article class="markdown-body">
        {@html renderMarkdown(lesson.text ?? '')}
      </article>
    </Panel>

    <SimilarPanel
      id="lesson-similarity"
      title={$messages.detailSimilarLessons}
      items={similar}
      meta={similarMeta}
      explain={true}
      loading={similarLoading}
      error={similarError}
    />
  </div>
{/if}

<DeleteLessonDialog
  lesson={deleteTarget}
  oncancel={() => { deleteTarget = null }}
  onconfirm={deleteLesson}
/>

<style>
  .detail-layout {
    display: grid;
    grid-template-columns: 1.4fr 0.8fr;
    gap: 16px;
    align-items: start;
  }

  :global(.main-pane .giu-panel__title) {
    overflow-wrap: anywhere;
  }

  h3 {
    margin-top: 16px;
  }

  .row {
    display: flex;
    flex-wrap: wrap;
    gap: 12px;
  }

  .tags {
    margin-top: 8px;
  }

  .delete-action {
    border: 1px solid #a22;
    border-radius: var(--radius-sm);
    background: var(--color-surface);
    color: #8b1717;
    font-weight: 700;
    padding: 6px 10px;
  }

  .delete-action:focus-visible {
    outline: 3px solid var(--accent);
    outline-offset: 2px;
  }

  @media (max-width: 900px) {
    .detail-layout {
      grid-template-columns: 1fr;
    }
  }
</style>
