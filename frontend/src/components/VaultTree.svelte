<script lang="ts">
  import { untrack } from 'svelte'
  import VaultTree from './VaultTree.svelte'
  import type { VaultTreeNode } from '../lib/api'
  import { navigate } from '../lib/router'

  interface Props {
    node: VaultTreeNode
    depth?: number
    bulkExpansion?: { open: boolean } | null
  }

  let { node, depth = 0, bulkExpansion = null }: Props = $props()
  let open = $state(untrack(() => depth < 2))

  // Each command has a new identity so repeating it also resolves mixed states.
  $effect(() => {
    if (bulkExpansion) open = bulkExpansion.open
  })
</script>

{#if node.type === 'dir'}
  <details class="dir" bind:open>
    <summary>
      {#if node.name}
        {node.name}
      {:else}
        <em>vault</em>
      {/if}
    </summary>
    {#if node.children?.length}
      <div class="children">
        {#each node.children as child}
          <VaultTree node={child} depth={depth + 1} {bulkExpansion} />
        {/each}
      </div>
    {/if}
  </details>
{:else}
  <button
    type="button"
    class="file"
    onclick={() => node.id && navigate({ view: 'detail', id: node.id })}
  >
    {node.name}
  </button>
{/if}

<style>
  .dir {
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 6px 10px;
    margin: 4px 0;
    background: #fffdf9;
  }

  summary {
    cursor: pointer;
    font-weight: 600;
  }

  .children {
    margin-left: 12px;
    margin-top: 6px;
  }

  .file {
    display: block;
    width: 100%;
    text-align: left;
    background: none;
    border: none;
    color: var(--accent);
    padding: 4px 0;
    font-family: ui-monospace, monospace;
    font-size: 0.85rem;
    cursor: pointer;
  }
</style>
