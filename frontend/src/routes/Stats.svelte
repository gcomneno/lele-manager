<script lang="ts">
  import { onMount } from 'svelte'
  import { FormStatus } from 'giadaware-ui-components'
  import {
    Panel,
    Surface,
  } from 'giadaware-ui-components/studio'
  import { api, type StatsSummaryResponse } from '../lib/api'
  import { messages } from '../lib/i18n'

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

<Panel title={$messages.statsTitle} class="stats">
  {#if loading}
    <p class="meta">{$messages.commonLoading}</p>
  {:else if error}
    <FormStatus
      message={error}
      tone="error"
      style="--giu-form-status-padding: var(--space-2) var(--space-3)"
    />
  {:else if stats}
    <div class="kpis">
      <Surface class="kpi">
        <span class="label">LeLe</span>
        <strong>{stats.n_lessons}</strong>
      </Surface>

      <Surface class="kpi">
        <span class="label">Topic</span>
        <strong>{stats.n_topics}</strong>
      </Surface>

      <Surface class="kpi">
        <span class="label">{$messages.statsUniqueTags}</span>
        <strong>{stats.n_unique_tags}</strong>
      </Surface>

      <Surface class="kpi">
        <span class="label">{$messages.statsAverageLength}</span>
        <strong>{stats.avg_text_length} {$messages.statsCharacters}</strong>
      </Surface>

      <Surface class="kpi">
        <span class="label">{$messages.statsAverageImportance}</span>
        <strong>{stats.avg_importance ?? '—'}</strong>
      </Surface>
    </div>

    <div class="grid">
      <div>
        <h3>{$messages.statsByTopic}</h3>

        {#if stats.by_topic.length === 0}
          <p class="meta">{$messages.statsNoData}</p>
        {:else}
          <ul class="bars">
            {#each stats.by_topic as row}
              <li>
                <span class="name">{row.topic}</span>
                <span class="bar-wrap">
                  <span
                    class="bar"
                    style:width="{Math.min(100, row.count * 8)}%"
                  ></span>
                </span>
                <span class="count">{row.count}</span>
              </li>
            {/each}
          </ul>
        {/if}
      </div>

      <div>
        <h3>{$messages.statsTopTags}</h3>

        {#if stats.top_tags.length === 0}
          <p class="meta">{$messages.statsNoTags}</p>
        {:else}
          <ul class="tags">
            {#each stats.top_tags as row}
              <li>
                <span class="tag">{row.tag}</span>
                <span class="meta">×{row.count}</span>
              </li>
            {/each}
          </ul>
        {/if}
      </div>
    </div>
  {/if}
</Panel>

<style>
  h3 {
    margin: 0 0 12px;
  }

  .kpis {
    display: grid;
    grid-template-columns: repeat(
      auto-fit,
      minmax(120px, 1fr)
    );
    gap: 12px;
    margin-bottom: 20px;
  }

  .label {
    display: block;
    margin-bottom: 4px;
    color: var(--muted);
    font-size: 0.8rem;
  }

  .grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 20px;
  }

  .bars {
    display: grid;
    gap: 8px;
    margin: 0;
    padding: 0;
    list-style: none;
  }

  .bars li {
    display: grid;
    grid-template-columns: 100px 1fr 32px;
    align-items: center;
    gap: 8px;
    font-size: 0.9rem;
  }

  .bar-wrap {
    height: 10px;
    overflow: hidden;
    border-radius: 4px;
    background: var(--color-surface-subtle);
  }

  .bar {
    display: block;
    height: 100%;
    background: var(--accent);
  }

  .tags {
    display: grid;
    gap: 6px;
    margin: 0;
    padding: 0;
    list-style: none;
  }

  @media (max-width: 800px) {
    .grid {
      grid-template-columns: 1fr;
    }
  }
</style>
