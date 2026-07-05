<script lang="ts">
  import { onMount } from 'svelte'
  import { api, type Lesson } from '../lib/api'
  import { navigate } from '../lib/router'
  import LessonCard from '../components/LessonCard.svelte'

  let q = $state('')
  let topic = $state('')
  let source = $state('')
  let importanceGte = $state('')
  let importanceLte = $state('')
  let limit = $state(20)

  let lessons = $state<Lesson[]>([])
  let loading = $state(false)
  let error = $state('')
  let status = $state('')

  async function runSearch() {
    loading = true
    error = ''
    status = 'Ricerca…'
    try {
      const body = {
        q: q.trim() || null,
        topic_in: topic.trim() ? [topic.trim()] : null,
        source_in: source.trim() ? [source.trim()] : null,
        importance_gte: importanceGte ? Number(importanceGte) : null,
        importance_lte: importanceLte ? Number(importanceLte) : null,
        limit: Number(limit) || 20,
      }
      lessons = await api.searchLessons(body)
      status = `${lessons.length} risultati`
    } catch (e) {
      lessons = []
      status = ''
      error = e instanceof Error ? e.message : String(e)
    } finally {
      loading = false
    }
  }

  async function listAll() {
    loading = true
    error = ''
    status = 'Caricamento…'
    try {
      lessons = await api.listLessons(Number(limit) || 50)
      status = `${lessons.length} lezioni`
    } catch (e) {
      lessons = []
      status = ''
      error = e instanceof Error ? e.message : String(e)
    } finally {
      loading = false
    }
  }

  function reset() {
    q = ''
    topic = ''
    source = ''
    importanceGte = ''
    importanceLte = ''
  }

  onMount(() => {
    runSearch()
  })
</script>

<div class="browse">
  <section class="card filters">
    <h2>Browse</h2>
    <div class="grid">
      <label>
        Query
        <input bind:value={q} placeholder="pytest, git, pandas…" onkeydown={(e) => e.key === 'Enter' && runSearch()} />
      </label>
      <label>
        Topic
        <input bind:value={topic} placeholder="python" />
      </label>
      <label>
        Source
        <input bind:value={source} placeholder="note" />
      </label>
      <label>
        Importance ≥
        <input type="number" min="1" max="5" bind:value={importanceGte} />
      </label>
      <label>
        Importance ≤
        <input type="number" min="1" max="5" bind:value={importanceLte} />
      </label>
      <label>
        Limit
        <input type="number" min="1" max="500" bind:value={limit} />
      </label>
    </div>
    <div class="actions">
      <button class="btn btn-primary" onclick={runSearch} disabled={loading}>Cerca</button>
      <button class="btn" onclick={listAll} disabled={loading}>Lista tutte</button>
      <button class="btn" onclick={reset}>Reset</button>
    </div>
    {#if status}<p class="ok">{status}</p>{/if}
    {#if error}<p class="error">{error}</p>{/if}
  </section>

  <section class="results">
    {#if loading}
      <p class="meta">Caricamento…</p>
    {:else if lessons.length === 0}
      <p class="meta">Nessuna LeLe trovata.</p>
    {:else}
      {#each lessons as lesson}
        <LessonCard
          {lesson}
          onclick={() => navigate({ view: 'detail', id: lesson.id })}
        />
      {/each}
    {/if}
  </section>
</div>

<style>
  .browse {
    display: grid;
    gap: 16px;
  }

  h2 {
    margin: 0 0 12px;
  }

  .grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
    gap: 12px;
  }

  label {
    display: grid;
    gap: 4px;
    font-size: 0.85rem;
    color: var(--muted);
  }

  input {
    padding: 8px 10px;
    border: 1px solid var(--border);
    border-radius: 8px;
    background: white;
    color: var(--text);
  }

  .actions {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
    margin-top: 12px;
  }

  .results {
    display: grid;
    gap: 10px;
  }
</style>
