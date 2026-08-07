<script lang="ts">
  import { onMount } from 'svelte'
  import { FormStatus } from 'giadaware-ui-components'
  import type { FormStatusTone } from 'giadaware-ui-components'
  import {
    Button,
    FormActions,
    Panel,
  } from 'giadaware-ui-components/studio'
  import { api, type VaultTreeResponse } from '../lib/api'
  import { navigate } from '../lib/router'
  import { formatMessage, messages } from '../lib/i18n'
  import VaultTree from '../components/VaultTree.svelte'

  let treeData = $state<VaultTreeResponse | null>(null)
  let loading = $state(true)
  let error = $state('')
  let importMsg = $state('')
  let importTone = $state<FormStatusTone>('info')

  async function load() {
    loading = true
    error = ''

    try {
      const status = await api.vaultStatus()

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
