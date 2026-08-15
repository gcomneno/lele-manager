<script lang="ts">
  import { FormStatus } from 'giadaware-ui-components'
  import { Button, Panel } from 'giadaware-ui-components/studio'
  import {
    ApiError,
    api,
    type LessonDetail,
    type LessonRevisionHistoryResponse,
    type LessonRevisionSummary,
  } from '../lib/api'
  import { messages } from '../lib/i18n'

  interface Props {
    lesson: LessonDetail
    onchanged: () => Promise<void>
  }

  let { lesson, onchanged }: Props = $props()

  let history = $state<LessonRevisionHistoryResponse | null>(null)
  let loading = $state(false)
  let error = $state('')
  let diff = $state('')
  let diffLoading = $state(false)
  let diffError = $state('')
  let compareFrom = $state<number | null>(null)
  let compareTo = $state<number | null>(null)
  let rollbackTarget = $state<LessonRevisionSummary | null>(null)
  let rollbackReason = $state('')
  let rollbackRunning = $state(false)
  let rollbackMessage = $state('')
  let rollbackTone = $state<'success' | 'warning' | 'error'>('success')

  function revisionLabel(item: LessonRevisionSummary): string {
    return `#${item.revision}`
  }

  function actionLabel(item: LessonRevisionSummary): string {
    switch (item.action) {
      case 'baseline':
        return $messages.revisionActionBaseline
      case 'edit':
        return $messages.revisionActionEdit
      case 'rollback':
        return $messages.revisionActionRollback
    }
  }

  function formatTimestamp(value: string): string {
    const parsed = new Date(value)
    return Number.isNaN(parsed.getTime())
      ? value
      : parsed.toLocaleString()
  }

  async function loadHistory() {
    loading = true
    error = ''
    diff = ''
    diffError = ''

    try {
      history = await api.lessonHistory(lesson.id)

      const revisions = history.revisions
      if (revisions.length >= 2) {
        compareFrom = revisions[revisions.length - 2].revision
        compareTo = revisions[revisions.length - 1].revision
      } else {
        compareFrom = null
        compareTo = null
      }
    } catch (e) {
      history = null
      error = e instanceof Error ? e.message : String(e)
    } finally {
      loading = false
    }
  }

  async function compare() {
    if (compareFrom == null || compareTo == null) return

    diffLoading = true
    diffError = ''
    diff = ''

    try {
      const response = await api.lessonRevisionDiff(
        lesson.id,
        compareFrom,
        compareTo,
      )
      diff = response.unified_diff
    } catch (e) {
      diffError = e instanceof Error ? e.message : String(e)
    } finally {
      diffLoading = false
    }
  }

  function requestRollback(item: LessonRevisionSummary) {
    rollbackTarget = item
    rollbackReason = ''
    rollbackMessage = ''
  }

  function cancelRollback() {
    if (rollbackRunning) return
    rollbackTarget = null
    rollbackReason = ''
  }

  async function confirmRollback() {
    if (!rollbackTarget) return

    const expectedRevision = lesson.canonical_revision
    if (!expectedRevision) return

    rollbackRunning = true
    rollbackMessage = ''

    try {
      await api.rollbackLessonRevision(
        lesson.id,
        rollbackTarget.revision,
        expectedRevision,
        rollbackReason,
      )
      rollbackTone = 'success'
      rollbackMessage = $messages.revisionRollbackSuccess
      rollbackTarget = null
      rollbackReason = ''
      await onchanged()
      await loadHistory()
    } catch (e) {
      if (e instanceof ApiError && e.code === 'lesson_revision_stale') {
        rollbackTone = 'error'
        rollbackMessage = $messages.revisionRollbackStale
      } else if (
        e instanceof ApiError
        && e.code === 'lesson_rollback_refresh_failed'
        && e.recovery?.canonical_saved === true
      ) {
        rollbackTone = 'warning'
        rollbackMessage = $messages.revisionRollbackRefreshFailed
        rollbackTarget = null
        rollbackReason = ''
        await onchanged()
        await loadHistory()
      } else {
        rollbackTone = 'error'
        rollbackMessage = e instanceof Error ? e.message : String(e)
      }
    } finally {
      rollbackRunning = false
    }
  }

  $effect(() => {
    lesson.id
    lesson.canonical_revision
    loadHistory()
  })
</script>

<Panel title={$messages.revisionHistoryTitle} class="revision-panel">
  {#if loading}
    <p class="meta">{$messages.commonLoading}</p>
  {:else if error}
    <FormStatus
      message={error}
      tone="error"
      style="--giu-form-status-padding: var(--space-2) var(--space-3)"
    />
  {:else if history}
    {#if rollbackMessage}
      <FormStatus
        message={rollbackMessage}
        tone={rollbackTone}
        style="--giu-form-status-padding: var(--space-2) var(--space-3)"
      />
    {/if}

    <p class="revision-current">
      {$messages.revisionCurrentFingerprint}:
      <code>{history.current_canonical_revision.slice(0, 20)}…</code>
    </p>

    {#if history.revisions.length === 0}
      <p class="meta">{$messages.revisionHistoryEmpty}</p>
    {:else}
      <ol class="revision-list">
        {#each [...history.revisions].reverse() as item (item.revision)}
          <li class="revision-item">
            <div class="revision-heading">
              <strong>{revisionLabel(item)}</strong>
              <span>{actionLabel(item)}</span>
              <time datetime={item.occurred_at}>
                {formatTimestamp(item.occurred_at)}
              </time>
            </div>

            {#if item.rollback_from_revision != null}
              <div class="meta">
                {$messages.revisionRestoredFrom}
                #{item.rollback_from_revision}
              </div>
            {/if}

            {#if item.reason}
              <div class="revision-reason">{item.reason}</div>
            {/if}

            <code class="revision-fingerprint">
              {item.canonical_fingerprint.slice(0, 20)}…
            </code>

            {#if item.revision !== history.revisions[history.revisions.length - 1]?.revision}
              <Button
                variant="secondary"
                size="compact"
                onclick={() => requestRollback(item)}
              >
                {$messages.revisionRollback}
              </Button>
            {/if}
          </li>
        {/each}
      </ol>

      {#if history.revisions.length >= 2}
        <section class="compare-block" aria-label={$messages.revisionCompareTitle}>
          <strong>{$messages.revisionCompareTitle}</strong>

          <div class="compare-controls">
            <label>
              <span>{$messages.revisionCompareFrom}</span>
              <select bind:value={compareFrom}>
                {#each history.revisions as item}
                  <option value={item.revision}>#{item.revision}</option>
                {/each}
              </select>
            </label>

            <label>
              <span>{$messages.revisionCompareTo}</span>
              <select bind:value={compareTo}>
                {#each history.revisions as item}
                  <option value={item.revision}>#{item.revision}</option>
                {/each}
              </select>
            </label>

            <Button
              variant="secondary"
              size="compact"
              onclick={compare}
              disabled={diffLoading || compareFrom === compareTo}
            >
              {diffLoading
                ? $messages.revisionComparing
                : $messages.revisionCompare}
            </Button>
          </div>

          {#if diffError}
            <FormStatus
              message={diffError}
              tone="error"
              style="--giu-form-status-padding: var(--space-2) var(--space-3)"
            />
          {/if}

          {#if diff}
            <pre class="revision-diff">{diff}</pre>
          {/if}
        </section>
      {/if}
    {/if}
  {/if}
</Panel>

{#if rollbackTarget}
  <div
    class="dialog-backdrop"
    role="presentation"
    onclick={(event) => {
      if (event.currentTarget === event.target) cancelRollback()
    }}
  >
    <div
      class="rollback-dialog"
      role="dialog"
      aria-modal="true"
      aria-labelledby="revision-rollback-title"
    >
      <h2 id="revision-rollback-title">
        {$messages.revisionRollbackConfirmTitle}
      </h2>

      <p>
        {$messages.revisionRollbackConfirmBody}
        <strong>#{rollbackTarget.revision}</strong>.
      </p>

      <p class="meta">
        {$messages.revisionRollbackCreatesNew}
      </p>

      <label>
        <span>{$messages.revisionRollbackReason}</span>
        <input
          bind:value={rollbackReason}
          placeholder={$messages.revisionRollbackReasonPlaceholder}
        />
      </label>

      <div class="dialog-actions">
        <Button
          variant="secondary"
          onclick={cancelRollback}
          disabled={rollbackRunning}
        >
          {$messages.commonCancel}
        </Button>

        <Button
          onclick={confirmRollback}
          disabled={rollbackRunning}
        >
          {rollbackRunning
            ? $messages.revisionRollbackRunning
            : $messages.revisionRollbackConfirm}
        </Button>
      </div>
    </div>
  </div>
{/if}

<style>
  .revision-current {
    margin-top: 0;
    overflow-wrap: anywhere;
  }

  .revision-list {
    display: grid;
    gap: var(--space-3);
    padding-left: 1.25rem;
  }

  .revision-item {
    display: grid;
    gap: var(--space-2);
    padding-bottom: var(--space-3);
    border-bottom: 1px solid var(--border);
  }

  .revision-heading {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-2);
    align-items: baseline;
  }

  .revision-heading time,
  .revision-fingerprint,
  .meta {
    color: var(--muted);
    font-size: 0.8rem;
  }

  .revision-reason {
    white-space: pre-wrap;
  }

  .compare-block {
    display: grid;
    gap: var(--space-3);
    margin-top: var(--space-4);
  }

  .compare-controls {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-3);
    align-items: end;
  }

  .compare-controls label {
    display: grid;
    gap: var(--space-1);
  }

  select,
  input {
    box-sizing: border-box;
    padding: 7px 9px;
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
    background: var(--color-surface);
    color: var(--text);
  }

  .revision-diff {
    max-height: 420px;
    overflow: auto;
    padding: var(--space-3);
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
    background: #f7f7f7;
    white-space: pre;
    font-size: 0.8rem;
  }

  .dialog-backdrop {
    position: fixed;
    inset: 0;
    z-index: 50;
    display: grid;
    place-items: center;
    padding: var(--space-4);
    background: rgb(0 0 0 / 45%);
  }

  .rollback-dialog {
    width: min(520px, 100%);
    display: grid;
    gap: var(--space-3);
    padding: var(--space-5);
    border-radius: var(--radius-md);
    background: var(--color-surface);
    box-shadow: 0 20px 60px rgb(0 0 0 / 25%);
  }

  .rollback-dialog h2,
  .rollback-dialog p {
    margin: 0;
  }

  .rollback-dialog label {
    display: grid;
    gap: var(--space-1);
  }

  .dialog-actions {
    display: flex;
    justify-content: flex-end;
    gap: var(--space-2);
  }
</style>
