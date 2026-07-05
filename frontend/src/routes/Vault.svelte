<script lang="ts">
  import { onMount } from 'svelte'
  import { api, type VaultTreeResponse } from '../lib/api'
  import VaultTree from '../components/VaultTree.svelte'
  import { navigate } from '../lib/router'

  let treeData = $state<VaultTreeResponse | null>(null)
  let loading = $state(true)
  let error = $state('')
  let importMsg = $state('')

  async function load() {
    loading = true
    error = ''
    try {
      const status = await api.vaultStatus()
      if (!status.exists) {
        error = `Vault non trovato: ${status.vault_dir}`
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
    importMsg = 'Import…'
    try {
      const res = await api.vaultImport()
      importMsg = res.message
      await load()
    } catch (e) {
      importMsg = e instanceof Error ? e.message : String(e)
    }
  }

  onMount(load)
</script>

<section class="card">
  <div class="head">
    <h2>Vault</h2>
    <div class="actions">
      <button class="btn" onclick={load} disabled={loading}>Refresh</button>
      <button class="btn btn-primary" onclick={doImport}>Import → JSONL</button>
      <button class="btn" onclick={() => navigate({ view: 'editor' })}>+ Nuova</button>
    </div>
  </div>

  {#if treeData}
    <p class="meta">{treeData.vault_dir}</p>
  {/if}

  {#if loading}
    <p class="meta">Caricamento…</p>
  {:else if error}
    <p class="error">{error}</p>
  {:else if treeData}
    <VaultTree node={treeData.tree} />
  {/if}

  {#if importMsg}
    <p class="ok">{importMsg}</p>
  {/if}
</section>

<style>
  .head {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 12px;
    flex-wrap: wrap;
    margin-bottom: 8px;
  }

  h2 {
    margin: 0;
  }

  .actions {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
  }
</style>
