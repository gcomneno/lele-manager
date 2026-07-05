<script lang="ts">
  import type { SimilarItem, SimilarMeta } from '../lib/api'
  import { navigate } from '../lib/router'

  interface Props {
    title?: string
    items: SimilarItem[]
    meta?: SimilarMeta | null
    loading?: boolean
    error?: string
    explain?: boolean
    onclickItem?: (id: string) => void
  }

  let {
    title = 'Simili',
    items,
    meta = null,
    loading = false,
    error = '',
    explain = true,
    onclickItem,
  }: Props = $props()

  function handleClick(id: string) {
    if (onclickItem) onclickItem(id)
    else navigate({ view: 'detail', id })
  }
</script>

<section class="card similar-panel">
  <h3>{explain ? 'Perché simile?' : title}</h3>

  {#if explain && meta}
    <p class="explain-meta">
      top_k={meta.top_k}, min_score={meta.min_score.toFixed(2)}
      {#if meta.query_topic}
        · query topic: <strong>{meta.query_topic}</strong>
      {/if}
      {#if meta.query_tags?.length}
        · tag query: {meta.query_tags.join(', ')}
      {/if}
    </p>
  {/if}

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
            <div class="row-top">
              {#if explain && item.rank != null}
                <span class="rank">#{item.rank}</span>
              {/if}
              <span class="score">{item.score.toFixed(2)}</span>
              {#if explain && item.topic}
                <span class="topic">{item.topic}</span>
              {/if}
            </div>
            <span class="id">{item.id}</span>
            <span class="preview">{item.text_preview}</span>
            {#if explain && item.tags_shared?.length}
              <span class="tags-shared">tag in comune: {item.tags_shared.join(', ')}</span>
            {/if}
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

  .explain-meta {
    margin: 0 0 12px;
    font-size: 0.8rem;
    color: var(--muted);
    line-height: 1.4;
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

  .row-top {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 8px;
  }

  .rank {
    font-size: 0.75rem;
    font-weight: 700;
    color: var(--muted);
  }

  .score {
    color: var(--accent);
    font-weight: 700;
    font-size: 0.85rem;
  }

  .topic {
    font-size: 0.75rem;
    padding: 2px 6px;
    border-radius: 999px;
    background: #f0ebe3;
    color: var(--text);
  }

  .id {
    font-family: ui-monospace, monospace;
    font-size: 0.8rem;
  }

  .preview {
    color: var(--muted);
    font-size: 0.85rem;
  }

  .tags-shared {
    font-size: 0.75rem;
    color: var(--accent);
  }
</style>
