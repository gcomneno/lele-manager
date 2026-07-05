<script lang="ts">
  import { api, type HealthResponse, type TrainResponse } from '../lib/api'

  let health = $state<HealthResponse | null>(null)
  let trainResult = $state<TrainResponse | null>(null)
  let loadingHealth = $state(false)
  let training = $state(false)
  let error = $state('')
  let log = $state<string[]>([])

  function pushLog(line: string) {
    const ts = new Date().toLocaleTimeString()
    log = [`[${ts}] ${line}`, ...log].slice(0, 20)
  }

  async function refreshHealth() {
    loadingHealth = true
    error = ''
    try {
      health = await api.health()
      pushLog(
        `health ok — dataset ${health.has_data ? 'presente' : 'mancante'}, modello ${health.has_model ? 'presente' : 'mancante'}`,
      )
    } catch (e) {
      health = null
      error = e instanceof Error ? e.message : String(e)
      pushLog(`health errore: ${error}`)
    } finally {
      loadingHealth = false
    }
  }

  async function train() {
    training = true
    error = ''
    trainResult = null
    pushLog('train avviato…')
    try {
      trainResult = await api.trainTopic()
      pushLog(`train ok — ${trainResult.n_lessons} lessons, topics: ${trainResult.topics.join(', ')}`)
      await refreshHealth()
    } catch (e) {
      error = e instanceof Error ? e.message : String(e)
      pushLog(`train errore: ${error}`)
    } finally {
      training = false
    }
  }

  refreshHealth()
</script>

<div class="ops">
  <section class="card">
    <h2>Ops / Admin</h2>
    <p class="meta">Operazioni sul dataset e sul topic model. Import vault completo → Fase 2.</p>

    <div class="health-grid">
      <div>
        <span class="label">API</span>
        <strong class="ok">{health?.status ?? '…'}</strong>
      </div>
      <div>
        <span class="label">Dataset</span>
        <strong class={health?.has_data ? 'ok' : 'warn'}>{health?.has_data ? 'ok' : 'mancante'}</strong>
      </div>
      <div>
        <span class="label">Topic model</span>
        <strong class={health?.has_model ? 'ok' : 'warn'}>{health?.has_model ? 'ok' : 'mancante'}</strong>
      </div>
    </div>

    <div class="actions">
      <button class="btn" onclick={refreshHealth} disabled={loadingHealth}>Refresh health</button>
      <button class="btn btn-primary" onclick={train} disabled={training}>
        {training ? 'Training…' : 'Train topic model'}
      </button>
    </div>

    {#if trainResult}
      <p class="ok">{trainResult.message}</p>
    {/if}
    {#if error}
      <p class="error">{error}</p>
    {/if}
  </section>

  <section class="card">
    <h3>Log operazioni</h3>
    {#if log.length === 0}
      <p class="meta">Nessuna operazione ancora.</p>
    {:else}
      <pre>{log.join('\n')}</pre>
    {/if}
  </section>
</div>

<style>
  .ops {
    display: grid;
    gap: 16px;
    max-width: 900px;
  }

  h2, h3 {
    margin: 0 0 8px;
  }

  .health-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 12px;
    margin: 16px 0;
  }

  .label {
    display: block;
    font-size: 0.8rem;
    color: var(--muted);
    margin-bottom: 4px;
  }

  .warn {
    color: var(--warn);
  }

  .actions {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
  }

  pre {
    background: #f3efe8;
    padding: 12px;
    border-radius: 8px;
    font-size: 0.82rem;
    overflow-x: auto;
    white-space: pre-wrap;
  }
</style>
