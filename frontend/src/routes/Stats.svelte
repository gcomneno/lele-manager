<script lang="ts">
  import { onMount } from 'svelte'
  import { api, type StatsSummaryResponse } from '../lib/api'

  let stats = $state<StatsSummaryResponse | null>(null)
  let loading = $state(true)
  let error = $state('')

  onMount(async () => {
    try {
      stats = await api.statsSummary()
    } catch (e) {
      error = e instanceof Error ? e.message : String(e)
    } finally {
      loading = false
    }
  })
</script>

<section class="card stats">
  <h2>Statistiche</h2>

  {#if loading}
    <p class="meta">Caricamento…</p>
  {:else if error}
    <p class="error">{error}</p>
  {:else if stats}
    <div class="kpis">
      <div class="kpi"><span class="label">LeLe</span><strong>{stats.n_lessons}</strong></div>
      <div class="kpi"><span class="label">Topic</span><strong>{stats.n_topics}</strong></div>
      <div class="kpi"><span class="label">Tag unici</span><strong>{stats.n_unique_tags}</strong></div>
      <div class="kpi"><span class="label">Lunghezza media</span><strong>{stats.avg_text_length} ch</strong></div>
      <div class="kpi">
        <span class="label">Importance media</span>
        <strong>{stats.avg_importance ?? '—'}</strong>
      </div>
    </div>

    <div class="grid">
      <div>
        <h3>Per topic</h3>
        {#if stats.by_topic.length === 0}
          <p class="meta">Nessun dato.</p>
        {:else}
          <ul class="bars">
            {#each stats.by_topic as row}
              <li>
                <span class="name">{row.topic}</span>
                <span class="bar-wrap"><span class="bar" style:width="{Math.min(100, row.count * 8)}%"></span></span>
                <span class="count">{row.count}</span>
              </li>
            {/each}
          </ul>
        {/if}
      </div>

      <div>
        <h3>Tag più comuni</h3>
        {#if stats.top_tags.length === 0}
          <p class="meta">Nessun tag.</p>
        {:else}
          <ul class="tags">
            {#each stats.top_tags as row}
              <li><span class="tag">{row.tag}</span> <span class="meta">×{row.count}</span></li>
            {/each}
          </ul>
        {/if}
      </div>
    </div>
  {/if}
</section>

<style>
  h2, h3 {
    margin: 0 0 12px;
  }

  .kpis {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
    gap: 12px;
    margin-bottom: 20px;
  }

  .kpi {
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 12px;
    background: #fffdf9;
  }

  .label {
    display: block;
    font-size: 0.8rem;
    color: var(--muted);
    margin-bottom: 4px;
  }

  .grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 20px;
  }

  .bars {
    list-style: none;
    margin: 0;
    padding: 0;
    display: grid;
    gap: 8px;
  }

  .bars li {
    display: grid;
    grid-template-columns: 100px 1fr 32px;
    gap: 8px;
    align-items: center;
    font-size: 0.9rem;
  }

  .bar-wrap {
    background: #f0ebe3;
    border-radius: 4px;
    height: 10px;
    overflow: hidden;
  }

  .bar {
    display: block;
    height: 100%;
    background: var(--accent);
  }

  .tags {
    list-style: none;
    margin: 0;
    padding: 0;
    display: grid;
    gap: 6px;
  }

  @media (max-width: 800px) {
    .grid {
      grid-template-columns: 1fr;
    }
  }
</style>
