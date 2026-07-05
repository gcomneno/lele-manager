<script lang="ts">
  import { api, type TimelineResponse } from '../lib/api'
  import { navigate } from '../lib/router'

  let groupBy = $state<'year' | 'month' | 'topic'>('month')
  let timeline = $state<TimelineResponse | null>(null)
  let loading = $state(false)
  let error = $state('')

  async function load() {
    loading = true
    error = ''
    try {
      timeline = await api.statsTimeline(groupBy)
    } catch (e) {
      timeline = null
      error = e instanceof Error ? e.message : String(e)
    } finally {
      loading = false
    }
  }

  $effect(() => {
    groupBy
    load()
  })

  function maxCount(): number {
    if (!timeline?.buckets.length) return 1
    return Math.max(...timeline.buckets.map((b) => b.count))
  }
</script>

<section class="card timeline">
  <div class="head">
    <h2>Timeline</h2>
    <div class="tabs">
      <button class:active={groupBy === 'month'} onclick={() => (groupBy = 'month')}>Mese</button>
      <button class:active={groupBy === 'year'} onclick={() => (groupBy = 'year')}>Anno</button>
      <button class:active={groupBy === 'topic'} onclick={() => (groupBy = 'topic')}>Topic</button>
    </div>
  </div>

  {#if loading}
    <p class="meta">Caricamento…</p>
  {:else if error}
    <p class="error">{error}</p>
  {:else if timeline}
    {#if timeline.buckets.length === 0}
      <p class="meta">Nessuna LeLe nel dataset.</p>
    {:else}
      <ul class="buckets">
        {#each timeline.buckets as bucket}
          <li class="bucket">
            <div class="row">
              <strong>{bucket.key}</strong>
              <span class="meta">{bucket.count} LeLe</span>
            </div>
            <div class="bar-wrap">
              <span
                class="bar"
                style:width="{(bucket.count / maxCount()) * 100}%"
              ></span>
            </div>
            <div class="ids">
              {#each bucket.lesson_ids.slice(0, 5) as lid}
                <button type="button" onclick={() => navigate({ view: 'detail', id: lid })}>{lid}</button>
              {/each}
              {#if bucket.lesson_ids.length > 5}
                <span class="meta">+{bucket.lesson_ids.length - 5} altre</span>
              {/if}
            </div>
          </li>
        {/each}
      </ul>
    {/if}
  {/if}
</section>

<style>
  .head {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 12px;
    flex-wrap: wrap;
    margin-bottom: 12px;
  }

  h2 {
    margin: 0;
  }

  .tabs {
    display: flex;
    gap: 6px;
  }

  .tabs button {
    border: 1px solid var(--border);
    background: white;
    border-radius: 8px;
    padding: 6px 12px;
    cursor: pointer;
  }

  .tabs button.active {
    background: var(--accent-soft);
    border-color: var(--accent);
    color: var(--accent);
    font-weight: 600;
  }

  .buckets {
    list-style: none;
    margin: 0;
    padding: 0;
    display: grid;
    gap: 14px;
  }

  .bucket {
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 12px;
    background: #fffdf9;
  }

  .row {
    display: flex;
    justify-content: space-between;
    margin-bottom: 8px;
  }

  .bar-wrap {
    background: #f0ebe3;
    border-radius: 4px;
    height: 12px;
    overflow: hidden;
    margin-bottom: 8px;
  }

  .bar {
    display: block;
    height: 100%;
    background: linear-gradient(90deg, var(--accent), #e8a87c);
  }

  .ids {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
  }

  .ids button {
    border: none;
    background: none;
    color: var(--accent);
    font-family: ui-monospace, monospace;
    font-size: 0.78rem;
    cursor: pointer;
    padding: 0;
  }
</style>
