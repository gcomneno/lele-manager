<script lang="ts">
  import { onMount } from 'svelte'
  import { api, type HealthResponse } from '../lib/api'

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
    <span class="dot err"></span>
    <span class="error">API offline</span>
  {:else if health}
    <span class="dot ok"></span>
    <span>API</span>
    <span class="sep">·</span>
    <span class:warn={!health.has_data}>dataset {health.has_data ? 'ok' : 'mancante'}</span>
    <span class="sep">·</span>
    <span class:warn={!health.has_model}>modello {health.has_model ? 'ok' : 'mancante'}</span>
  {:else}
    <span class="meta">health…</span>
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

  .warn {
    color: var(--warn);
  }

  .sep {
    opacity: 0.5;
  }
</style>
