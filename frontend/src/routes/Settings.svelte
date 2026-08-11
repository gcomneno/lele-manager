<script lang="ts">
  import { onMount } from 'svelte'
  import { FormStatus } from 'giadaware-ui-components'
  import {
    Button,
    FormActions,
    Panel,
    Surface,
  } from 'giadaware-ui-components/studio'
  import {
    api,
    type DiagnosticsPreviewResponse,
    type RuntimePathResponse,
    type RuntimePathRole,
  } from '../lib/api'
  import { formatMessage, messages } from '../lib/i18n'

  let runtime = $state<Awaited<ReturnType<typeof api.settingsRuntime>> | null>(null)
  let loading = $state(true)
  let error = $state('')
  let copyMessage = $state('')
  let diagnostics = $state<DiagnosticsPreviewResponse | null>(null)
  let diagnosticsText = $state('')
  let diagnosticsCopyMessage = $state('')
  let diagnosticsLoading = $state(false)
  let diagnosticsError = $state('')

  function roleLabel(role: RuntimePathRole): string {
    switch (role) {
      case 'authoritative_user_data':
        return $messages.settingsRoleAuthoritative
      case 'persistent_application_state':
        return $messages.settingsRolePersistent
      case 'derived_rebuildable_artifact':
        return $messages.settingsRoleDerived
      case 'cache_temporary_state':
        return $messages.settingsRoleCache
    }
  }

  function provenanceLabel(item: RuntimePathResponse): string {
    switch (item.provenance.kind) {
      case 'configuration_override':
        return $messages.settingsProvenanceOverride
      case 'legacy_override':
        return $messages.settingsProvenanceLegacy
      case 'platform_default':
        return $messages.settingsProvenancePlatform
      case 'product_default':
        return $messages.settingsProvenanceProduct
      case 'runtime_override':
        return $messages.settingsProvenanceRuntime
      case 'managed_registry':
        return $messages.settingsProvenanceRegistry
    }
  }

  async function load() {
    loading = true
    error = ''
    try {
      runtime = await api.settingsRuntime()
    } catch (err) {
      runtime = null
      error = err instanceof Error ? err.message : String(err)
    } finally {
      loading = false
    }
  }

  async function copyPath(path: string) {
    copyMessage = ''
    try {
      if (!navigator.clipboard?.writeText) {
        throw new Error('Clipboard API unavailable')
      }
      await navigator.clipboard.writeText(path)
      copyMessage = $messages.settingsCopiedPath
    } catch {
      copyMessage = $messages.settingsCopyFailed
    }
  }

  async function generateDiagnostics() {
    diagnosticsLoading = true
    diagnosticsError = ''
    diagnostics = null
    diagnosticsText = ''
    diagnosticsCopyMessage = ''

    try {
      const payload = await api.diagnosticsPreview()
      diagnostics = payload
      diagnosticsText = JSON.stringify(payload, null, 2)
    } catch (err) {
      diagnosticsError = err instanceof Error ? err.message : String(err)
    } finally {
      diagnosticsLoading = false
    }
  }

  async function copyDiagnostics() {
    if (!diagnosticsText) return

    diagnosticsCopyMessage = ''
    try {
      if (!navigator.clipboard?.writeText) {
        throw new Error('Clipboard API unavailable')
      }
      await navigator.clipboard.writeText(diagnosticsText)
      diagnosticsCopyMessage = $messages.diagnosticsCopied
    } catch {
      diagnosticsCopyMessage = $messages.diagnosticsCopyFailed
    }
  }

  function saveDiagnostics() {
    if (!diagnostics || !diagnosticsText) return

    const blob = new Blob([diagnosticsText], {
      type: 'application/json;charset=utf-8',
    })
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = `lele-manager-diagnostics-${diagnostics.version}.json`
    anchor.click()
    URL.revokeObjectURL(url)
  }

  onMount(load)
</script>

<Panel title={$messages.settingsTitle} class="settings">
  <p class="settings-intro">{$messages.settingsIntro}</p>

  {#if loading}
    <p class="meta">{$messages.settingsLoading}</p>
  {:else if error}
    <FormStatus
      message={formatMessage($messages.settingsError, { error })}
      tone="error"
    />
  {:else if runtime}
    <section aria-labelledby="diagnostics-status">
      <div class="section-heading">
        <h2 id="diagnostics-status">{$messages.settingsStatus}</h2>
      </div>
      <div class="runtime-summary">
      <Surface>
        <span class="label">{$messages.settingsVersion}</span>
        <strong>{runtime.version}</strong>
      </Surface>
      <Surface>
        <span class="label">{$messages.settingsHealth}</span>
        <strong>{runtime.health.status === 'ok' ? $messages.settingsAvailable : runtime.health.status}</strong>
      </Surface>
      <Surface>
        <span class="label">{$messages.settingsDataset}</span>
        <strong>{runtime.health.has_data ? $messages.settingsAvailable : $messages.settingsNotAvailable}</strong>
      </Surface>
      <Surface>
        <span class="label">{$messages.settingsSearchModel}</span>
        <strong>{runtime.health.has_model ? $messages.settingsReady : $messages.settingsNotAvailable}</strong>
      </Surface>
      </div>
    </section>

    <section class="diagnostics" aria-labelledby="diagnostic-package">
      <div class="section-heading">
        <h2 id="diagnostic-package">{$messages.diagnosticsTitle}</h2>
        <p class="meta">{$messages.diagnosticsIntro}</p>
      </div>

      <FormActions style="--giu-form-actions-gap: var(--space-2)">
        <Button size="compact" onclick={generateDiagnostics} disabled={diagnosticsLoading}>
          {diagnosticsLoading ? $messages.diagnosticsGenerating : $messages.diagnosticsGenerate}
        </Button>
        <Button variant="secondary" size="compact" onclick={copyDiagnostics} disabled={!diagnosticsText}>
          {$messages.diagnosticsCopy}
        </Button>
        <Button variant="secondary" size="compact" onclick={saveDiagnostics} disabled={!diagnosticsText}>
          {$messages.diagnosticsExport}
        </Button>
      </FormActions>

      {#if diagnosticsError}
        <FormStatus message={formatMessage($messages.diagnosticsError, { error: diagnosticsError })} tone="error" />
      {/if}

      {#if diagnosticsCopyMessage}
        <FormStatus
          message={diagnosticsCopyMessage}
          tone={diagnosticsCopyMessage === $messages.diagnosticsCopied ? 'success' : 'error'}
        />
      {/if}

      {#if diagnosticsText}
        <div class="diagnostic-preview" data-testid="diagnostic-preview">
          <h3>{$messages.diagnosticsPreviewTitle}</h3>
          <p class="meta">{$messages.diagnosticsPreviewHelp}</p>
          <pre>{diagnosticsText}</pre>
        </div>
      {/if}
    </section>

    <section class="support" aria-labelledby="diagnostics-support">
      <div class="section-heading">
        <h2 id="diagnostics-support">{$messages.diagnosticsSupportTitle}</h2>
        <p class="meta">{$messages.diagnosticsSupportIntro}</p>
        <p class="meta">
          {#if diagnostics}
            {formatMessage($messages.diagnosticsSupportAttach, { filename: `lele-manager-diagnostics-${diagnostics.version}.json` })}
          {:else}
            {$messages.diagnosticsSupportBeforeGenerate}
          {/if}
        </p>
      </div>
      <a
        class="support-action"
        href="https://github.com/gcomneno/lele-manager/issues/new?template=bug_report.yml"
        target="_blank"
        rel="noreferrer"
      >
        {$messages.diagnosticsSupportAction}
      </a>
    </section>

    {#if copyMessage}
      <FormStatus
        message={copyMessage}
        tone={copyMessage === $messages.settingsCopiedPath ? 'success' : 'error'}
      />
    {/if}

    <details class="technical-details" data-testid="technical-details">
      <summary>{$messages.diagnosticsTechnicalDetails}</summary>
      <section aria-labelledby="settings-runtime-paths">
        <div class="section-heading">
          <h2 id="settings-runtime-paths">{$messages.settingsRuntimePaths}</h2>
          <p class="meta">{$messages.settingsRuntimePathsDescription}</p>
        </div>

        <div class="path-list">
        {#each runtime.paths as item}
          <Surface>
            <div class="path-heading">
              <strong>{roleLabel(item.role)}</strong>
              <span class:item-present={item.exists} class="path-state">
                {item.exists ? $messages.settingsExists : $messages.settingsMissing}
              </span>
            </div>

            <dl>
              <div>
                <dt>{$messages.settingsPath}</dt>
                <dd><code>{item.path}</code></dd>
              </div>
              <div>
                <dt>{$messages.settingsSource}</dt>
                <dd>
                  {provenanceLabel(item)}
                  {#if item.provenance.variable}
                    · <code>{item.provenance.variable}</code>
                  {/if}
                  {#if item.provenance.deprecated}
                    · {$messages.settingsDeprecated}
                  {/if}
                </dd>
              </div>
            </dl>

            <FormActions
              style="--giu-form-actions-gap: var(--space-2); margin-top: var(--space-3)"
            >
              <Button
                variant="secondary"
                size="compact"
                onclick={() => copyPath(item.path)}
              >
                {$messages.settingsCopyPath}
              </Button>
            </FormActions>
          </Surface>
        {/each}
        </div>
      </section>
    </details>
  {/if}
</Panel>

<style>
  .settings-intro {
    margin-top: 0;
  }

  .runtime-summary,
  .path-list {
    display: grid;
    gap: var(--space-3);
  }

  .runtime-summary {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    margin-bottom: var(--space-5);
  }

  .runtime-summary :global(.giu-surface) {
    display: grid;
    gap: var(--space-1);
  }

  .section-heading {
    margin-bottom: var(--space-3);
  }

  .section-heading h2 {
    margin-bottom: var(--space-1);
  }

  .path-heading {
    display: flex;
    justify-content: space-between;
    gap: var(--space-3);
    align-items: start;
  }

  .path-state {
    font-size: 0.85rem;
    font-weight: 700;
  }

  .item-present {
    color: var(--color-success);
  }

  dl {
    display: grid;
    gap: var(--space-2);
    margin: var(--space-3) 0 0;
  }

  dl > div {
    display: grid;
    gap: var(--space-1);
  }

  dt {
    color: var(--color-text-muted);
    font-size: 0.78rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }

  dd {
    margin: 0;
    overflow-wrap: anywhere;
  }

  code {
    font-size: 0.9em;
  }

  .diagnostics {
    margin-top: var(--space-6);
  }

  .support,
  .technical-details {
    margin-top: var(--space-6);
  }

  .technical-details summary {
    cursor: pointer;
    font-weight: 700;
  }

  .technical-details section {
    margin-top: var(--space-4);
  }

  .support-action {
    display: inline-flex;
    align-items: center;
    min-height: 2.25rem;
    padding: 0 var(--space-3);
    border-radius: var(--radius-md);
    background: var(--color-brand-600);
    color: var(--color-text-inverse);
    font-weight: 700;
    text-decoration: none;
  }

  .support-action:focus-visible {
    outline: 3px solid var(--color-focus);
    outline-offset: 3px;
  }

  .diagnostic-preview {
    margin-top: var(--space-3);
  }

  .diagnostic-preview h3 {
    margin-bottom: var(--space-1);
  }

  .diagnostic-preview pre {
    margin: var(--space-3) 0 0;
    padding: var(--space-3);
    overflow: auto;
    max-height: 32rem;
    white-space: pre;
    border-radius: var(--radius-md);
    background: var(--surface-subtle);
    border: 1px solid var(--border);
    font-size: 0.82rem;
  }

  @media (max-width: 720px) {
    .runtime-summary {
      grid-template-columns: 1fr;
    }

    .path-heading {
      display: grid;
    }
  }
</style>
