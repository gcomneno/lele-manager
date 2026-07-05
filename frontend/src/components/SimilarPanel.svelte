<script lang="ts">
  import type { SimilarItem } from '../lib/api'
  import { navigate } from '../lib/router'

  interface Props {
    title?: string
    items: SimilarItem[]
    loading?: boolean
    error?: string
    onclickItem?: (id: string) => void
  }

  let {
    title = 'Simili',
    items,
    loading = false,
    error = '',
    onclickItem,
  }: Props = $props()

  function handleClick(id: string) {
    if (onclickItem) onclickItem(id)
    else navigate({ view: 'detail', id })
  }
</script>

<section class="card similar-panel">
  <h3>{title}</h3>

  {#if loading}
    <p class="meta">Caricamento…</p>
  {:else if error}
    <p class="error">{error}</p>
  {:else if items.length === 0}
    <p class="meta">Nessun risultato.</p>
  {:else}
    <ul>
      {#each items as item}
        <li>
          <button type="button" class="item" onclick={() => handleClick(item.id)}>
            <span class="score">{item.score.toFixed(2)}</span>
            <span class="id">{item.id}</span>
            <span class="preview">{item.text_preview}</span>
          </button>
        </li>
      {/each}
    </ul>
  {/if}
</section>

<style>
  h3 {
    margin: 0 0 12px;
  }

  ul {
    list-style: none;
    margin: 0;
    padding: 0;
    display: grid;
    gap: 8px;
  }

  .item {
    width: 100%;
    text-align: left;
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 10px;
    background: #fffdf9;
    display: grid;
    gap: 4px;
  }

  .score {
    color: var(--accent);
    font-weight: 700;
    font-size: 0.85rem;
  }

  .id {
    font-family: ui-monospace, monospace;
    font-size: 0.8rem;
  }

  .preview {
    color: var(--muted);
    font-size: 0.85rem;
  }
</style>
