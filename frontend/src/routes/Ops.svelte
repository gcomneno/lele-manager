<script lang="ts">
  import {
    api,
    type HealthResponse,
    type TrainResponse,
    type VaultDoctorProblem,
    type VaultDoctorReportResponse,
  } from '../lib/api'
  import { formatMessage, messages } from '../lib/i18n'

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

  function filesCheckedLabel(count: number): string {
    return formatMessage(
      count === 1
        ? $messages.opsFileChecked
        : $messages.opsFilesChecked,
      { count },
    )
  }

  function errorsLabel(count: number): string {
    return formatMessage(
      count === 1
        ? $messages.opsErrorCount
        : $messages.opsErrorsCount,
      { count },
    )
  }

  function findingsLabel(count: number): string {
    return count === 1
      ? $messages.opsFinding
      : $messages.opsFindings
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
        formatMessage(
          $messages.opsHealthOk,
          {
            dataset: health.has_data
              ? $messages.opsPresent
              : $messages.opsMissing,
            model: health.has_model
              ? $messages.opsPresent
              : $messages.opsMissing,
          },
        ),
      )
    } catch (e) {
      health = null
      error = e instanceof Error ? e.message : String(e)
      pushLog(
        formatMessage(
          $messages.opsHealthError,
          { error },
        ),
      )
    } finally {
      loadingHealth = false
    }
  }

  async function vaultImport() {
    importing = true
    error = ''
    pushLog($messages.opsImportStarted)
    try {
      const res = await api.vaultImport()
      pushLog(
        formatMessage(
          $messages.opsImportOk,
          { count: res.n_lessons },
        ),
      )
      await refreshHealth()
    } catch (e) {
      error = e instanceof Error ? e.message : String(e)
      pushLog(
        formatMessage(
          $messages.opsImportError,
          { error },
        ),
      )
    } finally {
      importing = false
    }
  }

  async function fullRefresh() {
    refreshing = true
    error = ''
    pushLog($messages.opsRefreshStarted)
    try {
      const res = await api.opsRefresh(true)
      pushLog($messages.opsRefreshImported)
      if (res.train_result) {
        pushLog(
          formatMessage(
            $messages.opsTrainOk,
            {
              count: res.train_result.n_lessons,
              topics: res.train_result.topics.join(', '),
            },
          ),
        )
      }
      trainResult = res.train_result ?? null
      await refreshHealth()
    } catch (e) {
      error = e instanceof Error ? e.message : String(e)
      pushLog(
        formatMessage(
          $messages.opsRefreshError,
          { error },
        ),
      )
    } finally {
      refreshing = false
    }
  }

  async function train() {
    training = true
    error = ''
    trainResult = null
    pushLog($messages.opsTrainStarted)
    try {
      trainResult = await api.trainTopic()
      pushLog(
        formatMessage(
          $messages.opsTrainOk,
          {
            count: trainResult.n_lessons,
            topics: trainResult.topics.join(', '),
          },
        ),
      )
      await refreshHealth()
    } catch (e) {
      error = e instanceof Error ? e.message : String(e)
      pushLog(
        formatMessage(
          $messages.opsTrainError,
          { error },
        ),
      )
    } finally {
      training = false
    }
  }

  async function runDoctor() {
    runningDoctor = true
    doctorError = ''
    doctorReport = null
    pushLog($messages.opsDoctorStarted)
    try {
      doctorReport = await api.vaultDoctor()
      pushLog(
        doctorReport.valid
          ? formatMessage(
              $messages.opsDoctorOk,
              {
                files: filesCheckedLabel(
                  doctorReport.files_checked,
                ),
              },
            )
          : formatMessage(
              $messages.opsDoctorIssues,
              {
                errors: errorsLabel(
                  doctorReport.error_count,
                ),
              },
            ),
      )
    } catch (e) {
      doctorError = e instanceof Error ? e.message : String(e)
      pushLog(
        formatMessage(
          $messages.opsDoctorError,
          { error: doctorError },
        ),
      )
    } finally {
      runningDoctor = false
    }
  }

  refreshHealth()
</script>

<div class="ops">
  <section class="card">
    <h2>{$messages.opsTitle}</h2>
    <p class="meta">{$messages.opsDescription}</p>

    <div class="health-grid">
      <div>
        <span class="label">API</span>
        <strong class="ok">{health?.status ?? '…'}</strong>
      </div>
      <div>
        <span class="label">{$messages.opsDataset}</span>
        <strong class={health?.has_data ? 'ok' : 'warn'}>{health?.has_data ? $messages.healthOk : $messages.healthMissing}</strong>
      </div>
      <div>
        <span class="label">{$messages.opsSearchModel}</span>
        <strong class={health?.has_model ? 'ok' : 'warn'}>{health?.has_model ? $messages.healthOk : $messages.healthMissing}</strong>
      </div>
    </div>

    <div class="actions maintenance-actions">
      <button class="btn" onclick={refreshHealth} disabled={loadingHealth}>{$messages.opsRefreshStatus}</button>
      <button class="btn" onclick={vaultImport} disabled={importing}>{$messages.opsRefreshVault}</button>
      <button class="btn btn-primary" onclick={train} disabled={training}>
        {training
          ? $messages.opsUpdatingModel
          : $messages.opsUpdateModel}
      </button>
      <button class="btn btn-primary" onclick={fullRefresh} disabled={refreshing}>
        {refreshing
          ? $messages.opsUpdatingAll
          : $messages.opsUpdateAll}
      </button>
    </div>

    {#if trainResult}
      <p class="ok">
        {formatMessage(
          $messages.opsTrainOk,
          {
            count: trainResult.n_lessons,
            topics: trainResult.topics.join(', '),
          },
        )}
      </p>
    {/if}
    {#if error}
      <p class="error">{error}</p>
    {/if}
  </section>

  <section class="card doctor" aria-live="polite">
    <div
      class="doctor-layout"
      class:has-report={Boolean(doctorReport)}
    >
      <div class="doctor-controls">
        <h3>{$messages.opsDoctorTitle}</h3>
        <p class="meta">{$messages.opsDoctorDescription}</p>
        <div class="actions">
          <button class="btn" onclick={runDoctor} disabled={runningDoctor}>
            {runningDoctor
              ? $messages.opsDoctorRunning
              : $messages.opsDoctorRun}
          </button>
        </div>

        {#if doctorError}
          <p class="error">{doctorError}</p>
        {/if}
      </div>

      {#if doctorReport}
        <div class="doctor-result">
          <p class={doctorReport.valid ? 'ok' : 'error'}>
            {doctorReport.valid
              ? $messages.opsVaultHealthy
              : $messages.opsVaultNotHealthy}
          </p>
          <p class="meta">
            {filesCheckedLabel(doctorReport.files_checked)}
            ·
            {formatMessage(
              $messages.opsUniqueIds,
              { count: doctorReport.unique_ids },
            )}
            ·
            {errorsLabel(doctorReport.error_count)}
          </p>
        </div>
      {/if}
    </div>

    {#if doctorReport && doctorReport.problems.length > 0}
      <div class="doctor-diagnostic-groups">
        {#each groupDoctorProblems(doctorReport.problems) as group}
          <section class="doctor-diagnostic-group">
            <h4>{group.code} ({group.problems.length} {findingsLabel(group.problems.length)})</h4>
            <ul class="doctor-diagnostics">
              {#each group.problems as problem}
                <li>
                  <div class="diagnostic-details">
                    <code>{problem.path}</code>
                    {#if problem.field}
                      <span class="diagnostic-field">{$messages.opsField}: {problem.field}</span>
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
  </section>

  <section class="card">
    <h3>{$messages.opsActivityLog}</h3>
    {#if log.length === 0}
      <p class="meta">{$messages.opsNoOperations}</p>
    {:else}
      <pre>{log.join('\n')}</pre>
    {/if}
  </section>
</div>

<style>
  .ops {
    display: grid;
    gap: 16px;
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

  .health-grid > div {
    min-width: 0;
    padding: 12px 14px;
    border: 1px solid var(--border);
    border-radius: 8px;
    background: #faf8f4;
  }

  .health-grid strong {
    display: flex;
    align-items: center;
    gap: 6px;
    margin-top: 2px;
  }

  .health-grid strong::before {
    content: '';
    width: 7px;
    height: 7px;
    flex: 0 0 7px;
    border-radius: 999px;
    background: currentColor;
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

  .maintenance-actions {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    max-width: 760px;
  }

  .maintenance-actions .btn {
    width: 100%;
  }

  .doctor-layout {
    display: grid;
    gap: 20px;
    align-items: start;
  }

  .doctor-layout.has-report {
    grid-template-columns: minmax(0, 1fr) minmax(280px, 0.8fr);
  }

  .doctor-result {
    min-width: 0;
    padding-left: 20px;
    border-left: 1px solid var(--border);
  }

  .doctor-result p:first-child {
    margin-top: 0;
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

  @media (max-width: 900px) {
    .maintenance-actions {
      grid-template-columns: repeat(2, minmax(0, 1fr));
      max-width: none;
    }

    .doctor-layout.has-report {
      grid-template-columns: 1fr;
    }

    .doctor-result {
      padding-left: 0;
      padding-top: 16px;
      border-left: 0;
      border-top: 1px solid var(--border);
    }
  }

  @media (max-width: 560px) {
    .health-grid,
    .maintenance-actions {
      grid-template-columns: 1fr;
    }
  }
</style>
