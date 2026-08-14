<script lang="ts">
  import { onMount } from 'svelte'
  import { FormStatus } from 'giadaware-ui-components'
  import type { FormStatusTone } from 'giadaware-ui-components'
  import {
    Button,
    FormActions,
    Panel,
  } from 'giadaware-ui-components/studio'
  import { api, type ManagedVault, type VaultRestorePreview, type VaultTransferOperation, type VaultTransferPreview, type VaultTransferResolution, type VaultTransferSourceLesson, type VaultTreeResponse } from '../lib/api'
  import { navigate } from '../lib/router'
  import { formatMessage, messages } from '../lib/i18n'
  import VaultTree from '../components/VaultTree.svelte'

  let treeData = $state<VaultTreeResponse | null>(null)
  let loading = $state(true)
  let error = $state('')
  let importMsg = $state('')
  let importTone = $state<FormStatusTone>('info')
  let vaults = $state<ManagedVault[]>([])
  let vaultName = $state('')
  let vaultPath = $state('')
  let managementMessage = $state('')
  let snapshotMessage = $state('')
  let snapshotTone = $state<FormStatusTone>('info')
  let restoreArtifact = $state<File | null>(null)
  let restoreArtifactVersion = $state(0)
  let restoreTargetId = $state('')
  let restorePreview = $state<VaultRestorePreview | null>(null)
  let restoreConfirmation = $state('')
  let restoreMessage = $state('')
  let restoreTone = $state<FormStatusTone>('info')
  let snapshotBusy = $state(false)
  let restoreBusy = $state(false)
  let restoreExecuting = $state(false)
  let previewRequestVersion = $state(0)
  let transferSourceId = $state('')
  let transferDestinationId = $state('')
  let transferOperation = $state<VaultTransferOperation>('merge')
  let transferLessons = $state<VaultTransferSourceLesson[]>([])
  let selectedTransferLessonIds = $state<string[]>([])
  let transferResolutions = $state<Record<string, VaultTransferResolution>>({})
  let transferPreview = $state<VaultTransferPreview | null>(null)
  let transferBusy = $state(false)
  let transferExecuting = $state(false)
  let transferMessage = $state('')
  let transferTone = $state<FormStatusTone>('info')
  let transferRequestVersion = $state(0)

  async function load() {
    loading = true
    error = ''

    try {
      const status = await api.vaultStatus()
      vaults = await api.vaults()
      if (!restoreTargetId) restoreTargetId = status.vault_id ?? ''
      const availableVaults = vaults.filter((vault) => vault.available)
      if (!transferSourceId || !availableVaults.some((vault) => vault.id === transferSourceId)) transferSourceId = status.vault_id ?? availableVaults[0]?.id ?? ''
      ensureTransferDestination()
      if (transferSourceId) await selectTransferSource()
      else transferLessons = []

      if (!status.exists) {
        error = formatMessage(
          $messages.vaultNotFound,
          { path: status.vault_dir },
        )
        treeData = null
        return
      }

      treeData = await api.vaultTree()
    } catch (e) {
      treeData = null
      error = e instanceof Error ? e.message : String(e)
    } finally {
      loading = false
    }
  }

  async function addVault(create: boolean) {
    try {
      if (create) await api.createVault(vaultName, vaultPath)
      else await api.registerVault(vaultName, vaultPath)
      vaultName = ''
      vaultPath = ''
      managementMessage = ''
      await load()
    } catch (e) { managementMessage = e instanceof Error ? e.message : String(e) }
  }

  async function activate(id: string) {
    try {
      await api.activateVault(id)
      window.location.reload()
    } catch (e) { managementMessage = e instanceof Error ? e.message : String(e) }
  }

  async function rename(vault: ManagedVault) {
    const name = window.prompt($messages.vaultRenamePrompt, vault.name)
    if (!name) return
    try { await api.renameVault(vault.id, name); await load() }
    catch (e) { managementMessage = e instanceof Error ? e.message : String(e) }
  }

  async function remove(vault: ManagedVault) {
    if (!window.confirm(formatMessage($messages.vaultRemoveConfirm, { name: vault.name }))) return
    try { await api.removeVault(vault.id); await load() }
    catch (e) { managementMessage = e instanceof Error ? e.message : String(e) }
  }

  async function doImport() {
    importMsg = $messages.vaultImporting
    importTone = 'info'

    try {
      const res = await api.vaultImport()
      importMsg = res.message
      importTone = 'success'
      await load()
    } catch (e) {
      importMsg = e instanceof Error ? e.message : String(e)
      importTone = 'error'
    }
  }

  async function createSnapshot(vault: ManagedVault) {
    snapshotBusy = true
    snapshotMessage = $messages.vaultSnapshotCreating
    snapshotTone = 'info'
    try {
      const artifact = await api.downloadVaultSnapshot(vault.id)
      const link = document.createElement('a')
      link.href = URL.createObjectURL(artifact)
      link.download = `lele-vault-${vault.id}.snapshot.zip`
      link.click()
      URL.revokeObjectURL(link.href)
      snapshotMessage = formatMessage($messages.vaultSnapshotCreated, { name: vault.name })
      snapshotTone = 'success'
    } catch (e) {
      snapshotMessage = e instanceof Error ? e.message : $messages.vaultSnapshotFailed
      snapshotTone = 'error'
    } finally { snapshotBusy = false }
  }

  function selectRestoreArtifact(event: Event) {
    const input = event.currentTarget as HTMLInputElement
    restoreArtifact = input.files?.[0] ?? null
    restoreArtifactVersion += 1
    previewRequestVersion += 1
    restoreBusy = false
    restorePreview = null
    restoreConfirmation = ''
    restoreMessage = ''
  }

  function selectRestoreTarget() {
    previewRequestVersion += 1
    restoreBusy = false
    restorePreview = null
    restoreConfirmation = ''
    restoreMessage = ''
  }

  async function previewRestore() {
    if (!restoreArtifact || !restoreTargetId) {
      restoreMessage = $messages.vaultRestoreNeedPreview
      restoreTone = 'error'
      return
    }
    const targetId = restoreTargetId
    const artifact = restoreArtifact
    const artifactVersion = restoreArtifactVersion
    const requestVersion = ++previewRequestVersion
    restoreBusy = true
    restoreMessage = $messages.vaultRestorePreviewing
    restoreTone = 'info'
    try {
      const preview = await api.previewVaultRestore(targetId, artifact)
      if (
        requestVersion === previewRequestVersion
        && restoreTargetId === targetId
        && restoreArtifact === artifact
        && restoreArtifactVersion === artifactVersion
      ) {
        restorePreview = preview
        restoreMessage = ''
      }
    } catch (e) {
      if (requestVersion === previewRequestVersion) {
        restorePreview = null
        restoreMessage = e instanceof Error ? e.message : $messages.vaultRestoreFailed
        restoreTone = 'error'
      }
    } finally {
      if (requestVersion === previewRequestVersion) restoreBusy = false
    }
  }

  async function restoreSnapshot() {
    if (
      !restoreArtifact
      || !restorePreview
      || restorePreview.target_vault_id !== restoreTargetId
    ) {
      restorePreview = null
      restoreConfirmation = ''
      restoreMessage = $messages.vaultRestoreNeedPreview
      restoreTone = 'error'
      return
    }
    restoreBusy = true
    restoreExecuting = true
    restoreMessage = $messages.vaultRestoreRestoring
    restoreTone = 'info'
    try {
      const result = await api.restoreVaultSnapshot(restoreTargetId, restoreArtifact, restorePreview.plan_digest)
      restoreTone = result.derived_reconciled ? 'success' : 'error'
      restoreMessage = result.derived_reconciled
        ? $messages.vaultRestoreSuccess
        : formatMessage($messages.vaultRestorePartial, { error: result.derived_error ?? '' })
      restorePreview = null
      restoreConfirmation = ''
      await load()
    } catch (e) {
      restoreMessage = e instanceof Error ? e.message : $messages.vaultRestoreFailed
      restoreTone = 'error'
    } finally {
      restoreBusy = false
      restoreExecuting = false
    }
  }

  function invalidateTransferPlan(message = '') {
    transferRequestVersion += 1
    transferPreview = null
    transferMessage = message
  }

  function ensureTransferDestination() {
    const destinations = vaults.filter((vault) => vault.available && vault.id !== transferSourceId)
    if (!destinations.some((vault) => vault.id === transferDestinationId)) {
      transferDestinationId = destinations[0]?.id ?? ''
    }
  }

  function transferVaultName(id: string) {
    return (vaults.find((vault) => vault.id === id)?.name ?? id) || '—'
  }

  async function selectTransferSource() {
    invalidateTransferPlan()
    ensureTransferDestination()
    selectedTransferLessonIds = []
    transferResolutions = {}
    transferLessons = []
    if (!transferSourceId) return
    const sourceId = transferSourceId
    const version = ++transferRequestVersion
    transferBusy = true
    try {
      const lessons = await api.vaultTransferSourceLessons(sourceId)
      if (version === transferRequestVersion && transferSourceId === sourceId) transferLessons = lessons
    } catch (e) {
      if (version === transferRequestVersion) {
        transferMessage = e instanceof Error ? e.message : $messages.vaultTransferFailed
        transferTone = 'error'
      }
    } finally { if (version === transferRequestVersion) transferBusy = false }
  }

  function toggleTransferLesson(lessonId: string, checked: boolean) {
    selectedTransferLessonIds = checked
      ? [...selectedTransferLessonIds, lessonId]
      : selectedTransferLessonIds.filter((id) => id !== lessonId)
    invalidateTransferPlan()
  }

  function transferSelections() {
    return selectedTransferLessonIds.map((lesson_id) => ({ lesson_id, resolution: transferResolutions[lesson_id] ?? null }))
  }

  async function previewTransfer() {
    if (!transferSourceId || !transferDestinationId || !selectedTransferLessonIds.length) {
      transferMessage = $messages.vaultTransferNeedSelection
      transferTone = 'error'
      return
    }
    const sourceId = transferSourceId
    const destinationId = transferDestinationId
    const operation = transferOperation
    const selections = transferSelections()
    const version = ++transferRequestVersion
    transferBusy = true
    transferMessage = $messages.vaultTransferPreviewing
    transferTone = 'info'
    try {
      const preview = await api.previewVaultTransfer({ source_vault_id: sourceId, destination_vault_id: destinationId, operation, selections })
      if (version === transferRequestVersion && transferSourceId === sourceId && transferDestinationId === destinationId && transferOperation === operation) {
        transferPreview = preview
        transferMessage = ''
      }
    } catch (e) {
      if (version === transferRequestVersion) {
        transferPreview = null
        transferMessage = e instanceof Error ? e.message : $messages.vaultTransferFailed
        transferTone = 'error'
      }
    } finally { if (version === transferRequestVersion) transferBusy = false }
  }

  function setTransferResolution(lessonId: string, resolution: VaultTransferResolution) {
    transferResolutions = { ...transferResolutions, [lessonId]: resolution }
    invalidateTransferPlan($messages.vaultTransferResolutionNeedsPreview)
    transferTone = 'info'
  }

  function transferClassification(value: string) {
    const labels: Record<string, string> = {
      new: $messages.vaultTransferClassNew,
      same_id: $messages.vaultTransferClassSameId,
      likely_duplicate: $messages.vaultTransferClassLikelyDuplicate,
      path_conflict: $messages.vaultTransferClassPathConflict,
      identical: $messages.vaultTransferClassIdentical,
      already_present: $messages.vaultTransferClassAlreadyPresent,
    }
    return labels[value] ?? value
  }

  function transferPreviewMatchesCurrent() {
    if (!transferPreview) return false
    if (
      transferPreview.source_vault_id !== transferSourceId
      || transferPreview.destination_vault_id !== transferDestinationId
      || transferPreview.operation !== transferOperation
      || transferPreview.items.length !== selectedTransferLessonIds.length
    ) return false
    const selected = new Set(selectedTransferLessonIds)
    return transferPreview.items.every((item) => {
      if (!selected.has(item.lesson_id)) return false
      const expectedResolution = transferResolutions[item.lesson_id]
        ?? (item.classification === 'new' ? 'transfer' : (item.classification === 'identical' || item.classification === 'already_present' ? 'keep_destination' : null))
      return item.resolution === expectedResolution
    })
  }

  async function executeTransfer() {
    if (!transferPreviewMatchesCurrent() || !transferPreview) {
      transferPreview = null
      transferMessage = $messages.vaultTransferNeedFreshPreview
      transferTone = 'error'
      return
    }
    transferBusy = true
    transferExecuting = true
    transferMessage = $messages.vaultTransferExecuting
    transferTone = 'info'
    try {
      const result = await api.executeVaultTransfer({ source_vault_id: transferSourceId, destination_vault_id: transferDestinationId, operation: transferOperation, selections: transferSelections(), plan_digest: transferPreview.plan_digest })
      const itemFailure = result.items.some((item) => item.outcome.endsWith('_failed'))
      const partial = itemFailure || result.destination_derived_reconciled === false || result.source_derived_reconciled === false
      const completedTone: FormStatusTone = partial ? 'error' : 'success'
      const completedMessage = partial ? $messages.vaultTransferPartial : $messages.vaultTransferSuccess
      transferPreview = null
      await load()
      transferTone = completedTone
      transferMessage = completedMessage
    } catch (e) {
      transferMessage = e instanceof Error ? e.message : $messages.vaultTransferFailed
      transferTone = 'error'
    } finally { transferBusy = false; transferExecuting = false }
  }

  onMount(load)
</script>

<Panel title={$messages.navVault}>
  <section class="vault-management" aria-label={$messages.vaultManagement}>
    <h2>{$messages.vaults}</h2>
    {#each vaults as vault (vault.id)}
      <div class="vault-row">
        <div><strong>{vault.name}</strong>{#if vault.active} · {$messages.vaultActive}{/if}<br /><small>{vault.path} · {vault.available ? $messages.vaultAvailable : $messages.vaultMissing}</small></div>
        <div>
          {#if !vault.active}<Button size="compact" onclick={() => activate(vault.id)}>{$messages.vaultSwitch}</Button>{/if}
          <Button variant="secondary" size="compact" onclick={() => createSnapshot(vault)} disabled={snapshotBusy}>{$messages.vaultCreateSnapshot}</Button>
          <Button variant="secondary" size="compact" onclick={() => rename(vault)}>{$messages.vaultRename}</Button>
          {#if !vault.active}<Button variant="secondary" size="compact" onclick={() => remove(vault)}>{$messages.vaultRemove}</Button>{/if}
        </div>
      </div>
    {/each}
    <h3>{$messages.vaultCreateOrRegister}</h3>
    <label>{$messages.vaultName} <input bind:value={vaultName} /></label>
    <label>{$messages.vaultDirectoryPath} <input bind:value={vaultPath} /></label>
    <FormActions><Button onclick={() => addVault(true)}>{$messages.vaultCreate}</Button><Button variant="secondary" onclick={() => addVault(false)}>{$messages.vaultRegister}</Button></FormActions>
    <p class="meta">{$messages.vaultRemovalNote}</p>
    {#if managementMessage}<FormStatus message={managementMessage} tone="error" />{/if}
  </section>
  <section class="vault-management" aria-label={$messages.vaultSnapshots}>
    <h2>{$messages.vaultSnapshots}</h2>
    <label>{$messages.vaultRestoreArtifact} <input type="file" accept=".zip,application/zip" onchange={selectRestoreArtifact} disabled={restoreExecuting} /></label>
    <label>{$messages.vaultRestoreTarget}
      <select bind:value={restoreTargetId} onchange={selectRestoreTarget} disabled={restoreExecuting}>
        {#each vaults.filter((vault) => vault.available) as vault (vault.id)}
          <option value={vault.id}>{vault.name} — {vault.path}</option>
        {/each}
      </select>
    </label>
    <FormActions><Button variant="secondary" onclick={previewRestore} disabled={restoreBusy || !restoreArtifact || !restoreTargetId}>{$messages.vaultRestorePreview}</Button></FormActions>
    {#if restorePreview}
      <div class="restore-preview">
        <h3>{$messages.vaultRestorePreviewTitle}</h3>
        <p>{formatMessage($messages.vaultRestoreSource, { name: restorePreview.source_vault_name, id: restorePreview.source_vault_id })}</p>
        <p>{formatMessage($messages.vaultRestoreTargetDetails, { name: restorePreview.target_name, id: restorePreview.target_vault_id, path: restorePreview.target_path })}</p>
        <p>{formatMessage($messages.vaultRestoreFiles, { count: restorePreview.canonical_file_count })}</p>
        <p>{$messages.vaultRestoreAdditions}: {restorePreview.additions.join(', ') || '—'}</p>
        <p>{$messages.vaultRestoreReplacements}: {restorePreview.replacements.join(', ') || '—'}</p>
        <p>{$messages.vaultRestoreRemovals}: {restorePreview.removals.join(', ') || '—'}</p>
        <p>{$messages.vaultRestoreUnchanged}: {restorePreview.unchanged.join(', ') || '—'}</p>
        <p>{formatMessage($messages.vaultRestoreEditorial, { items: restorePreview.editorial_state.join(', ') })}</p>
        <p>{formatMessage($messages.vaultRestoreDerived, { items: restorePreview.derived_effects.join(', ') })}</p>
        <label>{ $messages.vaultRestoreConfirmLabel } <input bind:value={restoreConfirmation} /></label>
        {#if restoreConfirmation !== restorePreview.target_name}<p class="meta">{$messages.vaultRestoreConfirmMismatch}</p>{/if}
        <FormActions><Button onclick={restoreSnapshot} disabled={restoreBusy || restoreConfirmation !== restorePreview.target_name}>{$messages.vaultRestoreConfirm}</Button></FormActions>
      </div>
    {/if}
    {#if snapshotMessage}<FormStatus message={snapshotMessage} tone={snapshotTone} />{/if}
    {#if restoreMessage}<FormStatus message={restoreMessage} tone={restoreTone} />{/if}
  </section>
  <section class="vault-management" aria-label={$messages.vaultTransfers}>
    <h2>{$messages.vaultTransfers}</h2>
    <p class="meta">{$messages.vaultTransferHelp}</p>
    <label>{$messages.vaultTransferSource}
      <select bind:value={transferSourceId} onchange={selectTransferSource} disabled={transferExecuting}>
        {#each vaults.filter((vault) => vault.available) as vault (vault.id)}<option value={vault.id}>{vault.name} — {vault.path}</option>{/each}
      </select>
    </label>
    <p aria-label={$messages.vaultTransferDirection}><strong>{transferVaultName(transferSourceId)}</strong> → <strong>{transferVaultName(transferDestinationId)}</strong></p>
    <label>{$messages.vaultTransferDestination}
      <select bind:value={transferDestinationId} onchange={() => invalidateTransferPlan()} disabled={transferExecuting}>
        {#each vaults.filter((vault) => vault.available && vault.id !== transferSourceId) as vault (vault.id)}<option value={vault.id}>{vault.name} — {vault.path}</option>{/each}
      </select>
    </label>
    <label>{$messages.vaultTransferOperation}
      <select bind:value={transferOperation} onchange={() => invalidateTransferPlan()} disabled={transferExecuting}>
        <option value="merge">{$messages.vaultTransferMerge}</option><option value="copy">{$messages.vaultTransferCopy}</option><option value="move">{$messages.vaultTransferMove}</option>
      </select>
    </label>
    {#if transferOperation === 'move'}<p class="meta">{$messages.vaultTransferMoveWarning}</p>{/if}
    <h3>{$messages.vaultTransferSelectLessons}</h3>
    {#each transferLessons as lesson (lesson.lesson_id)}
      <label><input type="checkbox" checked={selectedTransferLessonIds.includes(lesson.lesson_id)} onchange={(event) => toggleTransferLesson(lesson.lesson_id, (event.currentTarget as HTMLInputElement).checked)} disabled={transferExecuting} /> {lesson.lesson_id} — {lesson.source_path}</label>
    {/each}
    <FormActions><Button variant="secondary" onclick={previewTransfer} disabled={transferBusy || !selectedTransferLessonIds.length}>{$messages.vaultTransferPreview}</Button></FormActions>
    {#if transferPreview}
      <div class="restore-preview">
        <h3>{$messages.vaultTransferPreviewTitle}</h3>
        <p>{formatMessage($messages.vaultTransferSourceDetails, { name: transferPreview.source_name, id: transferPreview.source_vault_id, path: transferPreview.source_path })}</p>
        <p>{formatMessage($messages.vaultTransferDestinationDetails, { name: transferPreview.destination_name, id: transferPreview.destination_vault_id, path: transferPreview.destination_path })}</p>
        {#each transferPreview.items as item (item.lesson_id)}
          <div><strong>{item.lesson_id}</strong>: {transferClassification(item.classification)} ({item.source_path} → {item.destination_path})
            {#if item.classification !== 'new' && item.classification !== 'identical' && item.classification !== 'already_present'}
              <label>{$messages.vaultTransferResolution}<select value={transferResolutions[item.lesson_id] ?? ''} onchange={(event) => setTransferResolution(item.lesson_id, (event.currentTarget as HTMLSelectElement).value as VaultTransferResolution)}><option value="">{$messages.vaultTransferResolve}</option><option value="keep_destination">{$messages.vaultTransferKeepDestination}</option><option value="skip">{$messages.vaultTransferSkip}</option></select></label>
            {/if}
          </div>
        {/each}
        <FormActions><Button onclick={executeTransfer} disabled={transferBusy || transferPreview.items.some((item) => item.resolution === null)}>{transferOperation === 'move' ? $messages.vaultTransferConfirmMove : $messages.vaultTransferConfirm}</Button></FormActions>
      </div>
    {/if}
    {#if transferMessage}<FormStatus message={transferMessage} tone={transferTone} />{/if}
  </section>
  <FormActions
    class="vault-actions"
    style="margin-bottom: var(--space-2)"
  >
    <Button
      variant="secondary"
      size="compact"
      class="lele-secondary-button"
      onclick={load}
      disabled={loading}
    >
      {$messages.vaultRefresh}
    </Button>

    <Button
      size="compact"
      onclick={doImport}
    >
      {$messages.vaultImportJsonl}
    </Button>

    <Button
      variant="secondary"
      size="compact"
      class="lele-secondary-button"
      onclick={() => navigate({ view: 'editor' })}
    >
      {$messages.vaultNew}
    </Button>
  </FormActions>

  {#if treeData}
    <p class="meta">{treeData.vault_dir}</p>
  {/if}

  {#if loading}
    <p class="meta">{$messages.commonLoading}</p>
  {:else if error}
    <FormStatus
      message={error}
      tone="error"
      style="--giu-form-status-padding: var(--space-2) var(--space-3)"
    />
  {:else if treeData}
    <VaultTree node={treeData.tree} />
  {/if}

  {#if importMsg}
    <FormStatus
      message={importMsg}
      tone={importTone}
      style="--giu-form-status-padding: var(--space-2) var(--space-3)"
    />
  {/if}
</Panel>
