<script lang="ts">
  import { api, type Lesson, type SimilarItem } from '../lib/api'
  import { navigate } from '../lib/router'
  import { renderMarkdown } from '../lib/markdown'
  import SimilarPanel from '../components/SimilarPanel.svelte'

  interface Props {
    id: string
  }

  let { id }: Props = $props()

  let lesson = $state<Lesson | null>(null)
  let similar = $state<SimilarItem[]>([])
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
      const resp = await api.similarById(id, 8, 0.05)
      similar = resp.results
    } catch (e) {
      similar = []
      similarError = e instanceof Error ? e.message : String(e)
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
  <p class="error">{error}</p>
{:else if lesson}
  <div class="detail-layout">
    <section class="card main-pane">
      <div class="head">
        <div>
          <h2>{lesson.id}</h2>
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
        </div>
        <button class="btn" onclick={() => navigate({ view: 'editor', id: lesson!.id })}>
          Modifica
        </button>
      </div>

      {#if lesson.title}
        <h3>{lesson.title}</h3>
      {/if}

      <article class="markdown-body">
        {@html renderMarkdown(lesson.text ?? '')}
      </article>
    </section>

    <SimilarPanel
      title="LeLe simili"
      items={similar}
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

  .head {
    display: flex;
    justify-content: space-between;
    gap: 12px;
    margin-bottom: 16px;
  }

  h2 {
    margin: 0 0 8px;
    word-break: break-word;
  }

  h3 {
    margin-top: 0;
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
