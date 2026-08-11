<script lang="ts">
  import { onMount } from 'svelte'
  import { FormStatus } from 'giadaware-ui-components'
  import type { FormStatusTone } from 'giadaware-ui-components'
  import {
    Button,
    FormActions,
    Panel,
  } from 'giadaware-ui-components/studio'
  import { api, type ManagedVault, type VaultTreeResponse } from '../lib/api'
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

  async function load() {
    loading = true
    error = ''

    try {
      const status = await api.vaultStatus()
      vaults = await api.vaults()

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
