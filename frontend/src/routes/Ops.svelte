<script lang="ts">
  import {
    api,
    type HealthResponse,
    type TrainResponse,
    type VaultDoctorProblem,
    type VaultDoctorReportResponse,
  } from '../lib/api'

  let health = $state<HealthResponse | null>(null)
  let trainResult = $state<TrainResponse | null>(null)
  let doctorReport = $state<VaultDoctorReportResponse | null>(null)
  let loadingHealth = $state(false)
  let training = $state(false)
  let importing = $state(false)
  let refreshing = $state(false)
  let runningDoctor = $state(false)
  let error = $state('')
  let doctorError = $state('')
  let log = $state<string[]>([])

  function pushLog(line: string) {
    const ts = new Date().toLocaleTimeString()
    log = [`[${ts}] ${line}`, ...log].slice(0, 20)
  }

  function groupDoctorProblems(problems: VaultDoctorProblem[]) {
    const problemsByCode = new Map<string, VaultDoctorProblem[]>()
    for (const problem of problems) {
      const group = problemsByCode.get(problem.code)
      if (group) {
        group.push(problem)
      } else {
        problemsByCode.set(problem.code, [problem])
      }
    }
    return [...problemsByCode.entries()]
      .sort(([left], [right]) => (left < right ? -1 : left > right ? 1 : 0))
      .map(([code, groupedProblems]) => ({ code, problems: groupedProblems }))
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

  async function vaultImport() {
    importing = true
    error = ''
    pushLog('import vault avviato…')
    try {
      const res = await api.vaultImport()
      pushLog(`import ok — ${res.n_lessons} lessons`)
      await refreshHealth()
    } catch (e) {
      error = e instanceof Error ? e.message : String(e)
      pushLog(`import errore: ${error}`)
    } finally {
      importing = false
    }
  }

  async function fullRefresh() {
    refreshing = true
    error = ''
    pushLog('refresh completo avviato…')
    try {
      const res = await api.opsRefresh(true)
      pushLog(res.import_result.message)
      if (res.train_result) {
        pushLog(`train ok — ${res.train_result.n_lessons} lessons`)
      }
      trainResult = res.train_result ?? null
      await refreshHealth()
    } catch (e) {
      error = e instanceof Error ? e.message : String(e)
      pushLog(`refresh errore: ${error}`)
    } finally {
      refreshing = false
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

  async function runDoctor() {
    runningDoctor = true
    doctorError = ''
    doctorReport = null
    pushLog('vault doctor avviato…')
    try {
      doctorReport = await api.vaultDoctor()
      pushLog(
        doctorReport.valid
          ? `vault doctor ok — ${doctorReport.files_checked} file controllati`
          : `vault doctor: ${doctorReport.error_count} errori trovati`,
      )
    } catch (e) {
      doctorError = e instanceof Error ? e.message : String(e)
      pushLog(`vault doctor errore: ${doctorError}`)
    } finally {
      runningDoctor = false
    }
  }

  refreshHealth()
</script>

<div class="ops">
  <section class="card">
    <h2>Stato e manutenzione</h2>
    <p class="meta">Aggiorna i contenuti, il modello di ricerca e lo stato locale.</p>

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
      <button class="btn" onclick={refreshHealth} disabled={loadingHealth}>Aggiorna stato</button>
      <button class="btn" onclick={vaultImport} disabled={importing}>Aggiorna dal vault</button>
      <button class="btn btn-primary" onclick={train} disabled={training}>
        {training ? 'Aggiornamento del modello…' : 'Aggiorna il modello di ricerca'}
      </button>
      <button class="btn btn-primary" onclick={fullRefresh} disabled={refreshing}>
        {refreshing ? 'Aggiornamento…' : 'Aggiorna tutto'}
      </button>
    </div>

    {#if trainResult}
      <p class="ok">{trainResult.message}</p>
    {/if}
    {#if error}
      <p class="error">{error}</p>
    {/if}
  </section>

  <section class="card doctor" aria-live="polite">
    <h3>Controllo del vault</h3>
    <p class="meta">Controllo in sola lettura della struttura e dei metadati del vault.</p>
    <div class="actions">
      <button class="btn" onclick={runDoctor} disabled={runningDoctor}>
        {runningDoctor ? 'Controllo in corso…' : 'Esegui controllo'}
      </button>
    </div>

    {#if doctorError}
      <p class="error">{doctorError}</p>
    {/if}

    {#if doctorReport}
      <p class={doctorReport.valid ? 'ok' : 'error'}>
        {doctorReport.valid ? 'Vault healthy' : 'Vault not healthy'}
      </p>
      <p class="meta">
        {doctorReport.files_checked} file controllati · {doctorReport.unique_ids} ID univoci ·
        {doctorReport.error_count} errori
      </p>

      {#if doctorReport.problems.length > 0}
        <div class="doctor-diagnostic-groups">
          {#each groupDoctorProblems(doctorReport.problems) as group}
            <section class="doctor-diagnostic-group">
              <h4>{group.code} ({group.problems.length} {group.problems.length === 1 ? 'finding' : 'findings'})</h4>
              <ul class="doctor-diagnostics">
                {#each group.problems as problem}
                  <li>
                    <div class="diagnostic-details">
                      <code>{problem.path}</code>
                      {#if problem.field}
                        <span class="diagnostic-field">field: {problem.field}</span>
                      {/if}
                      <span class="tag severity-error">{problem.severity}</span>
                    </div>
                    <p>{problem.message}</p>
                  </li>
                {/each}
              </ul>
            </section>
          {/each}
        </div>
      {/if}
    {/if}
  </section>

  <section class="card">
    <h3>Registro attività</h3>
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

  h2, h3, h4 {
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

  .doctor-diagnostics {
    list-style: none;
    padding: 0;
    margin: 12px 0 0;
    display: grid;
    gap: 8px;
  }

  .doctor-diagnostic-groups {
    display: grid;
    gap: 12px;
    margin-top: 12px;
  }

  .doctor-diagnostic-group h4 {
    margin-bottom: 6px;
    font-size: 0.9rem;
  }

  .doctor-diagnostics li {
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 10px;
  }

  .doctor-diagnostics code {
    color: var(--muted);
    font-size: 0.82rem;
  }

  .diagnostic-details {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
  }

  .diagnostic-field {
    color: var(--muted);
    font-size: 0.82rem;
  }

  .doctor-diagnostics p {
    margin: 6px 0 0;
  }

  .severity-error {
    background: #fbe5e3;
    color: var(--err);
  }
</style>
