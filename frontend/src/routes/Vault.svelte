<script lang="ts">
  import { onMount } from 'svelte'
  import { FormStatus } from 'giadaware-ui-components'
  import type { FormStatusTone } from 'giadaware-ui-components'
  import {
    Button,
    FormActions,
    Panel,
  } from 'giadaware-ui-components/studio'
  import { api, type ManagedVault, type VaultRestorePreview, type VaultTreeResponse } from '../lib/api'
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
  let restoreTargetId = $state('')
  let restorePreview = $state<VaultRestorePreview | null>(null)
  let restoreConfirmation = $state('')
  let restoreMessage = $state('')
  let restoreTone = $state<FormStatusTone>('info')
  let snapshotBusy = $state(false)
  let restoreBusy = $state(false)

  async function load() {
    loading = true
    error = ''

    try {
      const status = await api.vaultStatus()
      vaults = await api.vaults()
      if (!restoreTargetId) restoreTargetId = status.vault_id ?? ''

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
    restorePreview = null
    restoreConfirmation = ''
    restoreMessage = ''
  }

  function selectRestoreTarget() {
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
    restoreBusy = true
    restoreMessage = $messages.vaultRestorePreviewing
    restoreTone = 'info'
    try {
      restorePreview = await api.previewVaultRestore(restoreTargetId, restoreArtifact)
      restoreMessage = ''
    } catch (e) {
      restorePreview = null
      restoreMessage = e instanceof Error ? e.message : $messages.vaultRestoreFailed
      restoreTone = 'error'
    } finally { restoreBusy = false }
  }

  async function restoreSnapshot() {
    if (!restoreArtifact || !restorePreview) return
    restoreBusy = true
    restoreMessage = $messages.vaultRestoreRestoring
    restoreTone = 'info'
    try {
      const result = await api.restoreVaultSnapshot(restorePreview.target_vault_id, restoreArtifact, restorePreview.plan_digest)
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
    } finally { restoreBusy = false }
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
    <label>{$messages.vaultRestoreArtifact} <input type="file" accept=".zip,application/zip" onchange={selectRestoreArtifact} /></label>
    <label>{$messages.vaultRestoreTarget}
      <select bind:value={restoreTargetId} onchange={selectRestoreTarget}>
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
