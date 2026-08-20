<script lang="ts">
  import { FormStatus } from 'giadaware-ui-components'
  import {
    Button,
    Panel,
  } from 'giadaware-ui-components/studio'
  import {
    ApiError,
    api,
    type FreshnessReasonCode,
    type Lesson,
    type LessonDetail,
    type LessonLifecycleState,
    type LessonRelationships,
    type LessonRelationshipType,
    type SimilarItem,
    type SimilarMeta,
  } from '../lib/api'
  import { navigate } from '../lib/router'
  import { formatMessage, messages } from '../lib/i18n'
  import { deleteLessonWithOutcome } from '../lib/lessonDeletion'
  import { setLessonDeletionNotice } from '../lib/lessonDeletionNotice'
  import { renderMarkdown } from '../lib/markdown'
  import SimilarPanel from '../components/SimilarPanel.svelte'
  import DeleteLessonDialog from '../components/DeleteLessonDialog.svelte'
  import RevisionHistoryPanel from '../components/RevisionHistoryPanel.svelte'

  interface Props {
    id: string
  }

  let { id }: Props = $props()

  let lesson = $state<LessonDetail | null>(null)
  let similar = $state<SimilarItem[]>([])
  let similarMeta = $state<SimilarMeta | null>(null)
  let loading = $state(true)
  let similarLoading = $state(false)
  let error = $state('')
  let similarError = $state('')
  let deleteTarget = $state<Lesson | null>(null)
  let deleteError = $state('')
  let reviewLoading = $state(false)
  let reviewStatus = $state('')
  let reviewStatusTone = $state<'success' | 'warning' | 'error'>('success')

  async function load(showLoading = true) {
    if (showLoading) {
      loading = true
    }
    error = ''

    try {
      lesson = await api.getLesson(id)
    } catch (e) {
      if (showLoading) {
        lesson = null
      }
      error = e instanceof Error ? e.message : String(e)
    } finally {
      if (showLoading) {
        loading = false
      }
    }
  }

  const relationshipTypes: LessonRelationshipType[] = [
    'derives-from',
    'corrects',
    'extends',
    'contradicts',
    'see-also',
  ]

  function relationshipLabel(type: LessonRelationshipType): string {
    switch (type) {
      case 'derives-from':
        return $messages.relationshipDerivesFrom
      case 'corrects':
        return $messages.relationshipCorrects
      case 'extends':
        return $messages.relationshipExtends
      case 'contradicts':
        return $messages.relationshipContradicts
      case 'see-also':
        return $messages.relationshipSeeAlso
    }
  }

  function hasRelationships(
    value: LessonRelationships | undefined,
  ): boolean {
    return relationshipTypes.some(
      (type) => (value?.[type]?.length ?? 0) > 0,
    )
  }

  function freshnessReasonLabel(code: FreshnessReasonCode): string {
    switch (code) {
      case 'lifecycle-review-needed':
        return $messages.freshnessReasonLifecycle
      case 'review-overdue':
        return $messages.freshnessReasonOverdue
      case 'corrected-by-related-knowledge':
        return $messages.freshnessReasonCorrected
      case 'extended-by-related-knowledge':
        return $messages.freshnessReasonExtended
      case 'superseded':
        return $messages.freshnessReasonSuperseded
    }
  }

  function lifecycleLabel(state: LessonLifecycleState): string {
    switch (state) {
      case 'review-needed':
        return $messages.lifecycleReviewNeeded
      case 'deprecated':
        return $messages.lifecycleDeprecated
      case 'archived':
        return $messages.lifecycleArchived
      case 'active':
        return $messages.lifecycleActive
    }
  }

  async function recordReview() {
    if (!lesson?.canonical_revision || reviewLoading) return

    reviewLoading = true
    reviewStatus = ''

    try {
      await api.markLessonReviewed(
        lesson.id,
        lesson.canonical_revision,
      )
      reviewStatus = $messages.freshnessReviewRecorded
      reviewStatusTone = 'success'
      await load(false)
    } catch (e) {
      if (
        e instanceof ApiError
        && e.code === 'lesson_review_refresh_failed'
        && e.recovery?.canonical_saved === true
      ) {
        reviewStatus = $messages.freshnessReviewRefreshFailed
        reviewStatusTone = 'warning'
        await load(false)
      } else if (
        e instanceof ApiError
        && e.code === 'lesson_revision_stale'
      ) {
        reviewStatus = $messages.freshnessReviewStale
        reviewStatusTone = 'error'
        await load(false)
      } else {
        reviewStatus = $messages.freshnessReviewFailed
        reviewStatusTone = 'error'
      }
    } finally {
      reviewLoading = false
    }
  }

  async function loadSimilar() {
    similarLoading = true
    similarError = ''

    try {
      const resp = await api.similarById(
        id,
        8,
        0.05,
        true,
      )
      similar = resp.results
      similarMeta = resp.meta ?? null
    } catch (e) {
      similar = []
      similarError = e instanceof Error
        ? e.message
        : String(e)
    } finally {
      similarLoading = false
    }
  }

  function inspectSimilarity() {
    document.getElementById('lesson-similarity')?.focus()
  }

  async function deleteLesson(lessonToDelete: Lesson) {
    deleteError = ''
    try {
      const outcome = await deleteLessonWithOutcome(lessonToDelete.id)
      setLessonDeletionNotice(
        outcome.kind === 'refreshed' ? 'deleted' : 'refresh-failed',
      )
      deleteTarget = null
      navigate({ view: 'browse' })
    } catch {
      deleteError = $messages.lessonDeleteFailed
      deleteTarget = null
    }
  }

  $effect(() => {
    if (!id) return
    load()
    loadSimilar()
  })
</script>

{#if loading}
  <p class="meta">{$messages.commonLoading}</p>
{:else if error}
  <FormStatus
    message={error}
    tone="error"
    style="--giu-form-status-padding: var(--space-2) var(--space-3)"
  />
{:else if lesson}
  <div class="detail-layout">
    <Panel title={lesson.id} class="main-pane">
      {#snippet actions()}
        <Button
          variant="secondary"
          size="compact"
          class="lele-secondary-button"
          onclick={() => navigate({
            view: 'editor',
            id: lesson!.id,
          })}
        >
          {$messages.lessonModify}
        </Button>
        <Button
          variant="secondary"
          size="compact"
          class="lele-secondary-button"
          onclick={inspectSimilarity}
        >
          {$messages.lessonInspect}
        </Button>
        <button
          type="button"
          class="delete-action"
          onclick={() => { deleteTarget = lesson }}
        >{$messages.deleteLessonDelete}</button>
      {/snippet}

      {#if deleteError}
        <FormStatus
          message={deleteError}
          tone="error"
          style="--giu-form-status-padding: var(--space-2) var(--space-3)"
        />
      {/if}

      <div class="meta row">
        <span>{$messages.fieldTopic}: {lesson.topic ?? '—'}</span>
        <span>{$messages.fieldSource}: {lesson.source ?? '—'}</span>
        <span>{$messages.fieldImportance}: {lesson.importance ?? '?'}</span>
        <span>{$messages.fieldDate}: {lesson.date ?? '—'}</span>
      </div>

      {#if (lesson.lifecycle ?? 'active') !== 'active'}
        <div
          class={`detail-lifecycle lifecycle-${lesson.lifecycle}`}
          data-testid="detail-lifecycle"
        >
          {$messages.detailLifecycle}:
          {lifecycleLabel(lesson.lifecycle ?? 'active')}
        </div>
      {/if}

      {#if lesson.freshness}
        <section
          class="freshness-panel"
          aria-labelledby="detail-freshness-title"
          data-testid="detail-freshness"
        >
          <div class="freshness-heading">
            <div>
              <strong id="detail-freshness-title">
                {$messages.freshnessTitle}
              </strong>
              <p class="meta">
                {$messages.freshnessAdvisory}
              </p>
            </div>

            {#if lesson.freshness.review_needed}
              <span class="freshness-state">
                {$messages.freshnessNeedsReview}
              </span>
            {:else}
              <span class="freshness-state freshness-clear">
                {$messages.freshnessNoSignal}
              </span>
            {/if}
          </div>

          <div class="freshness-meta">
            <span>
              {$messages.freshnessLastReviewed}:
              {lesson.reviewed_at ?? $messages.freshnessNeverReviewed}
            </span>
            <span>
              {$messages.freshnessInterval}:
              {formatMessage(
                $messages.freshnessIntervalDays,
                { days: lesson.freshness.review_interval_days },
              )}
            </span>
            {#if lesson.freshness.age_days !== null}
              <span>
                {$messages.freshnessAge}:
                {formatMessage(
                  $messages.freshnessAgeDays,
                  { days: lesson.freshness.age_days },
                )}
              </span>
            {/if}
          </div>

          {#if lesson.freshness.reasons.length}
            <ul class="freshness-reasons">
              {#each lesson.freshness.reasons as reason (`${reason.code}:${reason.related_lesson_ids.join(',')}`)}
                <li>
                  <span>{freshnessReasonLabel(reason.code)}</span>
                  {#if reason.related_lesson_ids.length}
                    <span class="meta">
                      {reason.related_lesson_ids.join(', ')}
                    </span>
                  {/if}
                </li>
              {/each}
            </ul>
          {/if}

          {#if lesson.canonical_revision}
            <Button
              variant="secondary"
              size="compact"
              class="lele-secondary-button"
              onclick={recordReview}
              disabled={reviewLoading}
            >
              {reviewLoading
                ? $messages.freshnessRecordingReview
                : $messages.freshnessRecordReview}
            </Button>
          {/if}

          {#if reviewStatus}
            <FormStatus
              message={reviewStatus}
              tone={reviewStatusTone}
              style="--giu-form-status-padding: var(--space-2) var(--space-3)"
            />
          {/if}
        </section>
      {/if}

      {#if lesson.superseded_by || lesson.supersedes?.length}
        <section
          class="supersession"
          aria-label={$messages.detailSupersession}
        >
          <strong>{$messages.detailSupersession}</strong>

          {#if lesson.superseded_by}
            <button
              type="button"
              class="relationship-link"
              onclick={() => navigate({
                view: 'detail',
                id: lesson!.superseded_by!,
              })}
            >
              {$messages.detailSupersededBy}: {lesson.superseded_by}
            </button>
          {/if}

          {#each lesson.supersedes ?? [] as supersededId (supersededId)}
            <button
              type="button"
              class="relationship-link"
              onclick={() => navigate({
                view: 'detail',
                id: supersededId,
              })}
            >
              {$messages.detailSupersedes}: {supersededId}
            </button>
          {/each}
        </section>
      {/if}

      {#if hasRelationships(lesson.relationships) || hasRelationships(lesson.incoming_relationships)}
        <section
          class="relationships"
          aria-label={$messages.detailRelationships}
          data-testid="detail-relationships"
        >
          <strong>{$messages.detailRelationships}</strong>

          {#if hasRelationships(lesson.relationships)}
            <div class="relationship-group">
              <span class="relationship-heading">
                {$messages.detailOutgoingRelationships}
              </span>
              {#each relationshipTypes as relationshipType}
                {#each lesson.relationships?.[relationshipType] ?? [] as targetId (`${relationshipType}:${targetId}`)}
                  <button
                    type="button"
                    class="relationship-link"
                    onclick={() => navigate({
                      view: 'detail',
                      id: targetId,
                    })}
                  >
                    {relationshipLabel(relationshipType)}: {targetId}
                  </button>
                {/each}
              {/each}
            </div>
          {/if}

          {#if hasRelationships(lesson.incoming_relationships)}
            <div class="relationship-group">
              <span class="relationship-heading">
                {$messages.detailIncomingRelationships}
              </span>
              {#each relationshipTypes as relationshipType}
                {#each lesson.incoming_relationships?.[relationshipType] ?? [] as sourceId (`${relationshipType}:${sourceId}`)}
                  <button
                    type="button"
                    class="relationship-link"
                    onclick={() => navigate({
                      view: 'detail',
                      id: sourceId,
                    })}
                  >
                    {relationshipLabel(relationshipType)} ← {sourceId}
                  </button>
                {/each}
              {/each}
            </div>
          {/if}
        </section>
      {/if}

      {#if lesson.tags?.length}
        <div class="tags">
          {#each lesson.tags as tag}
            <span class="tag">{tag}</span>
          {/each}
        </div>
      {/if}

      {#if lesson.title}
        <h3>{lesson.title}</h3>
      {/if}

      <article class="markdown-body">
        {@html renderMarkdown(lesson.text ?? '')}
      </article>
    </Panel>

    <div class="detail-sidebar">
      <SimilarPanel
        id="lesson-similarity"
        title={$messages.detailSimilarLessons}
        items={similar}
        meta={similarMeta}
        explain={true}
        loading={similarLoading}
        error={similarError}
      />

      {#if lesson.canonical_revision}
        <RevisionHistoryPanel
          lesson={lesson}
          onchanged={async () => {
            await load(false)
            await loadSimilar()
          }}
        />
      {/if}
    </div>
  </div>
{/if}

<DeleteLessonDialog
  lesson={deleteTarget}
  oncancel={() => { deleteTarget = null }}
  onconfirm={deleteLesson}
/>

<style>
  .detail-layout {
    display: grid;
    grid-template-columns: 1.4fr 0.8fr;
    gap: 16px;
    align-items: start;
  }

  .detail-sidebar {
    display: grid;
    gap: 16px;
  }

  :global(.main-pane .giu-panel__title) {
    overflow-wrap: anywhere;
  }

  h3 {
    margin-top: 16px;
  }

  .row {
    display: flex;
    flex-wrap: wrap;
    gap: 12px;
  }

  .tags {
    margin-top: 8px;
  }

  .detail-lifecycle {
    width: fit-content;
    margin-top: var(--space-3);
    padding: 4px 9px;
    border: 1px solid currentColor;
    border-radius: 999px;
    font-size: 0.8rem;
    font-weight: 800;
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }

  .lifecycle-review-needed {
    color: #7a4b00;
    background: #fff4d6;
  }

  .lifecycle-deprecated {
    color: #8b1717;
    background: #fff0f0;
  }

  .lifecycle-archived {
    color: #4d5156;
    background: #f0f1f2;
  }

  .freshness-panel {
    display: grid;
    gap: var(--space-3);
    margin-top: var(--space-3);
    padding: var(--space-3);
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
  }

  .freshness-heading {
    display: flex;
    flex-wrap: wrap;
    align-items: start;
    justify-content: space-between;
    gap: var(--space-2);
  }

  .freshness-heading p {
    margin: var(--space-1) 0 0;
  }

  .freshness-state {
    width: fit-content;
    padding: 3px 8px;
    border: 1px solid currentColor;
    border-radius: 999px;
    color: #7a4b00;
    background: #fff4d6;
    font-size: 0.78rem;
    font-weight: 800;
  }

  .freshness-clear {
    color: var(--ok);
    background: var(--color-surface);
  }

  .freshness-meta {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-3);
    color: var(--muted);
    font-size: 0.85rem;
  }

  .freshness-reasons {
    display: grid;
    gap: var(--space-1);
    margin: 0;
    padding-left: var(--space-4);
  }

  .freshness-reasons li {
    display: grid;
    gap: 2px;
  }

  .supersession {
    display: grid;
    justify-items: start;
    gap: var(--space-2);
    margin-top: var(--space-3);
    padding: var(--space-3);
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
  }

  .relationships {
    display: grid;
    justify-items: start;
    gap: var(--space-3);
    margin-top: var(--space-3);
    padding: var(--space-3);
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
  }

  .relationship-group {
    display: grid;
    justify-items: start;
    gap: var(--space-2);
  }

  .relationship-heading {
    color: var(--muted);
    font-size: 0.85rem;
    font-weight: 700;
  }

  .relationship-link {
    border: 0;
    padding: 0;
    background: transparent;
    color: var(--accent);
    font: inherit;
    text-align: left;
    text-decoration: underline;
    cursor: pointer;
    overflow-wrap: anywhere;
  }

  .relationship-link:focus-visible {
    outline: 3px solid var(--accent);
    outline-offset: 3px;
  }

  .delete-action {
    border: 1px solid #a22;
    border-radius: var(--radius-sm);
    background: var(--color-surface);
    color: #8b1717;
    font-weight: 700;
    padding: 6px 10px;
  }

  .delete-action:focus-visible {
    outline: 3px solid var(--accent);
    outline-offset: 2px;
  }

  @media (max-width: 900px) {
    .detail-layout {
      grid-template-columns: 1fr;
    }
  }
</style>
