<script lang="ts">
  import { onMount } from 'svelte'
  import { api, type HealthResponse } from '../lib/api'
  import { messages } from '../lib/i18n'

  let health: HealthResponse | null = $state(null)
  let error = $state('')

  async function refresh() {
    try {
      error = ''
      health = await api.health()
    } catch (e) {
      health = null
      error = e instanceof Error ? e.message : String(e)
    }
  }

  onMount(() => {
    refresh()
    const id = setInterval(refresh, 15000)
    return () => clearInterval(id)
  })
</script>

<div class="health-bar">
  {#if error}
    <span
      class="status-item error"
      aria-label={$messages.healthApiOffline}
    >
      <span class="dot err" aria-hidden="true"></span>
      <span>{$messages.healthApiOffline}</span>
    </span>
  {:else if health}
    <span
      class="status-item"
      aria-label={`API: ${$messages.healthOk}`}
    >
      <span class="dot ok" aria-hidden="true"></span>
      <span>API</span>
    </span>

    <span class="sep">·</span>

    <span
      class="status-item"
      class:warn={!health.has_data}
      aria-label={`${$messages.healthDataset}: ${
        health.has_data
          ? $messages.healthOk
          : $messages.healthMissing
      }`}
    >
      <span
        class="dot"
        class:ok={health.has_data}
        class:warn={!health.has_data}
        aria-hidden="true"
      ></span>
      <span>
        {$messages.healthDataset}{#if !health.has_data}
          {$messages.healthMissing}
        {/if}
      </span>
    </span>

    <span class="sep">·</span>

    <span
      class="status-item"
      class:warn={!health.has_model}
      aria-label={`${$messages.healthModel}: ${
        health.has_model
          ? $messages.healthOk
          : $messages.healthMissing
      }`}
    >
      <span
        class="dot"
        class:ok={health.has_model}
        class:warn={!health.has_model}
        aria-hidden="true"
      ></span>
      <span>
        {$messages.healthModel}{#if !health.has_model}
          {$messages.healthMissing}
        {/if}
      </span>
    </span>
  {:else}
    <span class="meta" role="status">
      {$messages.healthLoading}
    </span>
  {/if}
</div>

<style>
  .health-bar {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 0.85rem;
    color: var(--muted);
  }

  .status-item {
    display: inline-flex;
    align-items: center;
    gap: 5px;
  }

  .dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    display: inline-block;
  }

  .dot.ok {
    background: var(--ok);
  }

  .dot.err {
    background: var(--err);
  }

  .dot.warn {
    background: var(--warn);
  }

  .warn {
    color: var(--warn);
  }

  .sep {
    opacity: 0.5;
  }
</style>
