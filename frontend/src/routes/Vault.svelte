<script lang="ts">
  import { onMount } from 'svelte'
  import { api, type Lesson } from '../lib/api'
  import { navigate } from '../lib/router'

  let lessons = $state<Lesson[]>([])
  let loading = $state(true)
  let error = $state('')

  type Group = { topic: string; items: Lesson[] }

  let groups = $derived.by(() => {
    const map = new Map<string, Lesson[]>()
    for (const lesson of lessons) {
      const key = lesson.topic ?? '(senza topic)'
      if (!map.has(key)) map.set(key, [])
      map.get(key)!.push(lesson)
    }
    return [...map.entries()]
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([topic, items]) => ({ topic, items }))
  })

  onMount(async () => {
    try {
      lessons = await api.listLessons(500)
    } catch (e) {
      error = e instanceof Error ? e.message : String(e)
    } finally {
      loading = false
    }
  })
</script>

<section class="card">
  <h2>Vault</h2>
  <p class="meta">
    Vista raggruppata per topic (da dataset JSONL). Filesystem reale → Fase 2 (<code>GET /vault/tree</code>).
  </p>

  {#if loading}
    <p class="meta">Caricamento…</p>
  {:else if error}
    <p class="error">{error}</p>
  {:else if groups.length === 0}
    <p class="meta">Nessuna LeLe nel dataset.</p>
  {:else}
  <div class="tree">
    {#each groups as group}
      <details open>
        <summary>{group.topic} <span class="meta">({group.items.length})</span></summary>
        <ul>
          {#each group.items as lesson}
            <li>
              <button type="button" onclick={() => navigate({ view: 'detail', id: lesson.id })}>
                {lesson.id}
              </button>
            </li>
          {/each}
        </ul>
      </details>
    {/each}
  </div>
  {/if}
</section>

<style>
  h2 {
    margin: 0 0 8px;
  }

  .tree {
    display: grid;
    gap: 10px;
    margin-top: 12px;
  }

  details {
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 8px 12px;
    background: #fffdf9;
  }

  summary {
    cursor: pointer;
    font-weight: 600;
  }

  ul {
    margin: 8px 0 0;
    padding-left: 18px;
  }

  li button {
    background: none;
    border: none;
    color: var(--accent);
    padding: 2px 0;
    text-align: left;
    font-family: ui-monospace, monospace;
    font-size: 0.85rem;
  }
</style>
