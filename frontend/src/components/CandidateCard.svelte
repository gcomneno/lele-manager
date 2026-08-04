<script lang="ts">
  import type { Candidate } from '../lib/api'

  interface Props {
    candidate: Candidate
    selected?: boolean
    onclick?: () => void
  }

  let { candidate, selected = false, onclick }: Props = $props()

  function shortId(id: string): string {
    return id.startsWith('sha256:') ? id.slice(7, 19) : id.slice(0, 12)
  }
</script>

<button
  class="candidate-card"
  class:selected
  type="button"
  aria-label={`Apri candidato ${shortId(candidate.candidate_id)}`}
  {onclick}
>
  <span class={`state state-${candidate.state}`}>{candidate.state}</span>
  <strong>{candidate.provenance.source_logical_name}</strong>
  <span class="meta identity">{shortId(candidate.candidate_id)} · rev {candidate.revision}</span>
  <span class="meta">
    {candidate.provenance.source_kind}
    {#if candidate.provenance.chunk_index !== null}
      · chunk {candidate.provenance.chunk_index}
    {/if}
  </span>
  <span class="preview">
    {candidate.effective_text.slice(0, 150)}{candidate.effective_text.length > 150 ? '…' : ''}
  </span>
</button>

<style>
  .candidate-card {
    display: grid;
    grid-template-columns: auto 1fr;
    gap: 5px 9px;
    width: 100%;
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 11px;
    text-align: left;
    color: var(--text);
    background: var(--surface);
  }

  .candidate-card:hover,
  .candidate-card.selected {
    border-color: var(--accent);
    background: #fffaf5;
  }

  strong,
  .preview {
    min-width: 0;
    overflow-wrap: anywhere;
  }

  .identity,
  .preview {
    grid-column: 1 / -1;
  }

  .preview {
    line-height: 1.35;
    font-size: 0.9rem;
  }

  .state {
    align-self: start;
    border-radius: 999px;
    padding: 2px 7px;
    font-size: 0.7rem;
    font-weight: 700;
    color: white;
    background: var(--muted);
  }

  .state-in_review { background: var(--warn); }
  .state-approved { background: var(--ok); }
  .state-rejected { background: var(--err); }
</style>
