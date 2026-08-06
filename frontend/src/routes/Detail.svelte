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
  import { renderMarkdown } from '../lib/markdown'
  import SimilarPanel from '../components/SimilarPanel.svelte'

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

  $effect(() => {
    if (!id) return
    load()
    loadSimilar()
  })
</script>

{#if loading}
  <p class="meta">Caricamento…</p>
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
          Modifica
        </Button>
      {/snippet}

      <div class="meta row">
        <span>topic: {lesson.topic ?? '—'}</span>
        <span>source: {lesson.source ?? '—'}</span>
        <span>importance: {lesson.importance ?? '?'}</span>
        <span>date: {lesson.date ?? '—'}</span>
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
      title="LeLe simili"
      items={similar}
      meta={similarMeta}
      explain={true}
      loading={similarLoading}
      error={similarError}
    />
  </div>
{/if}

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

  @media (max-width: 900px) {
    .detail-layout {
      grid-template-columns: 1fr;
    }
  }
</style>
