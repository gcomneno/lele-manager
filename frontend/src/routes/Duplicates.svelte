<script lang="ts">
  import { FormStatus } from 'giadaware-ui-components'
  import {
    Button,
    FieldLabel,
    FormActions,
    Panel,
  } from 'giadaware-ui-components/studio'
  import { api, type DuplicateLessonSnapshot, type DuplicatePair, type DuplicateReportResponse } from '../lib/api'
  import { formatMessage, messages } from '../lib/i18n'

  interface LessonSide {
    heading: string
    position: number
    id: string
    lesson: DuplicateLessonSnapshot
    path: string
  }

  interface AppliedDuplicateQuery {
    minScore: number
    exactOnly: boolean
    limit: number
  }

  let minScore = $state(0.85)
  let exactOnly = $state(false)
  let limit = $state('100')
  let report = $state<DuplicateReportResponse | null>(null)
  let appliedQuery = $state<AppliedDuplicateQuery | null>(null)
  let loading = $state(false)
  let error = $state('')

  function requestLimit(): number | null {
    const parsed = Number(limit)
    return Number.isInteger(parsed) && parsed >= 1 ? parsed : null
  }

  function requestMinScore(): number | null {
    const parsed = Number(minScore)
    return Number.isFinite(parsed) && parsed >= 0 && parsed <= 1 ? parsed : null
  }

  function describeReason(reason: string): string {
    const labels: Record<string, string> = {
      duplicate_id: $messages.duplicatesReasonDuplicateId,
      exact_text: $messages.duplicatesReasonExactText,
      equivalent_metadata:
        $messages.duplicatesReasonEquivalentMetadata,
      same_title: $messages.duplicatesReasonSameTitle,
      same_topic: $messages.duplicatesReasonSameTopic,
      same_source: $messages.duplicatesReasonSameSource,
      same_date: $messages.duplicatesReasonSameDate,
      shared_tags: $messages.duplicatesReasonSharedTags,
    }

    return labels[reason] ?? $messages.duplicatesReasonDefault
  }

  function isModelError(message: string): boolean {
    return /model|modello/i.test(message)
  }

  function displayPath(pair: DuplicatePair, side: 'left' | 'right'): string {
    const direct = side === 'left' ? pair.left_path : pair.right_path
    const snapshot = side === 'left' ? pair.left_lesson : pair.right_lesson
    return direct ?? snapshot.path ?? '—'
  }

  function metadata(lesson: DuplicateLessonSnapshot): Array<[string, string | number]> {
    return [
      [$messages.fieldTitle, lesson.title ?? '—'],
      [$messages.fieldTopic, lesson.topic ?? '—'],
      [$messages.fieldSource, lesson.source ?? '—'],
      [$messages.fieldImportance, lesson.importance ?? '—'],
      [$messages.fieldDate, lesson.date ?? '—'],
      [$messages.duplicatesCreated, lesson.created_at ?? '—'],
    ]
  }

  function lessonSides(pair: DuplicatePair): LessonSide[] {
    return [
      {
        heading: $messages.duplicatesLeft,
        position: pair.left_position,
        id: pair.left_id,
        lesson: pair.left_lesson,
        path: displayPath(pair, 'left'),
      },
      {
        heading: $messages.duplicatesRight,
        position: pair.right_position,
        id: pair.right_id,
        lesson: pair.right_lesson,
        path: displayPath(pair, 'right'),
      },
    ]
  }

  async function runReview() {
    report = null
    appliedQuery = null
    error = ''

    const parsedLimit = requestLimit()
    if (parsedLimit == null) {
      error = $messages.duplicatesInvalidLimit
      return
    }
    const parsedMinScore = requestMinScore()
    if (parsedMinScore == null) {
      error = $messages.duplicatesInvalidScore
      return
    }
    const requestedExactOnly = exactOnly
    loading = true
    try {
      const response = await api.duplicates({
        min_score: parsedMinScore,
        exact_only: requestedExactOnly,
        limit: parsedLimit,
      })
      report = response
      appliedQuery = { minScore: parsedMinScore, exactOnly: requestedExactOnly, limit: parsedLimit }
    } catch (e) {
      error = e instanceof Error ? e.message : String(e)
    } finally {
      loading = false
    }
  }
</script>

<section class="duplicates">
  <Panel title={$messages.duplicatesTitle} class="controls">
    <p class="meta controls-description">
      {$messages.duplicatesDescription}
    </p>

    <div class="control-grid">
      <label>
        <FieldLabel label={$messages.duplicatesMinScore} />
        <input
          aria-label={$messages.duplicatesMinScore}
          type="number"
          min="0"
          max="1"
          step="0.01"
          bind:value={minScore}
        />
      </label>

      <label class="checkbox-label">
        <input
          aria-label={$messages.duplicatesExactOnly}
          type="checkbox"
          bind:checked={exactOnly}
        />
        <FieldLabel label={$messages.duplicatesExactOnly} />
      </label>

      <label>
        <FieldLabel label={$messages.duplicatesLimit} />
        <input
          aria-label={$messages.duplicatesLimit}
          type="number"
          min="1"
          step="1"
          bind:value={limit}
        />
      </label>
    </div>

    <FormActions
      style="--giu-form-actions-gap: var(--space-2); margin-top: var(--space-3)"
    >
      <Button
        size="compact"
        onclick={runReview}
        disabled={loading}
      >
        {loading
          ? $messages.duplicatesChecking
          : report
            ? $messages.duplicatesRefreshReview
            : $messages.duplicatesStartReview}
      </Button>
    </FormActions>
  </Panel>

  {#if loading}
    <FormStatus
      message={$messages.duplicatesCheckingStatus}
      tone="info"
      style="--giu-form-status-padding: var(--space-2) var(--space-3)"
    />
  {:else if error}
    <Panel
      title={isModelError(error)
        ? $messages.duplicatesModelUnavailable
        : $messages.duplicatesReviewFailed}
      headingLevel={3}
      class="error-state"
    >
      <FormStatus
        message={error}
        tone="error"
        style="--giu-form-status-padding: var(--space-2) var(--space-3)"
      />

      {#if isModelError(error)}
        <p class="meta">
          {$messages.duplicatesModelHelp}
        </p>
      {/if}
    </Panel>
  {:else if report && appliedQuery}
    <Panel
      title={$messages.duplicatesSummary}
      headingLevel={3}
      class="summary"
    >
      <dl class="summary-grid">
        <div><dt>{$messages.duplicatesLessonsAnalyzed}</dt><dd>{report.lessons_analyzed}</dd></div>
        <div><dt>{$messages.duplicatesTotalPairs}</dt><dd>{report.total_pairs}</dd></div>
        <div><dt>{$messages.duplicatesExactPairs}</dt><dd>{report.exact_pairs}</dd></div>
        <div><dt>{$messages.duplicatesNearPairs}</dt><dd>{report.near_pairs}</dd></div>
        <div><dt>{$messages.duplicatesAppliedMinScore}</dt><dd>{appliedQuery.minScore}</dd></div>
        <div><dt>{$messages.duplicatesAppliedLimit}</dt><dd>{appliedQuery.limit}</dd></div>
        <div><dt>{$messages.duplicatesAppliedExactOnly}</dt><dd>{appliedQuery.exactOnly ? $messages.commonYes : $messages.commonNo}</dd></div>
        <div><dt>{$messages.duplicatesPairsShown}</dt><dd>{report.pairs.length}</dd></div>
      </dl>
    </Panel>

    {#if report.pairs.length === 0}
      <section class="card empty-state">
        <h3>{$messages.duplicatesEmptyTitle}</h3>
        <p class="meta">{$messages.duplicatesEmptyHelp}</p>
      </section>
    {:else}
      <section class="pair-list" aria-label={$messages.duplicatesPairsAria}>
        {#each report.pairs as pair, index (`${pair.left_position}-${pair.right_position}-${index}`)}
          <article class="card duplicate-pair">
            <header class="pair-header">
              <h3>{formatMessage(
                $messages.duplicatesPair,
                { count: index + 1 },
              )}</h3>
              <div class="signals">
                <span class:exact={pair.kind === 'exact'} class:near={pair.kind === 'near'} class="kind">{pair.kind === 'exact' ? $messages.duplicatesKindExact : $messages.duplicatesKindNear}</span>
                <span class="score">{$messages.duplicatesScore} {pair.score.toFixed(3)}</span>
              </div>
            </header>
            <div class="reasons" aria-label={$messages.duplicatesSignalsAria}>
              {#if pair.reasons.length}
                {#each pair.reasons as reason}
                  <span class="reason" title={reason}>{describeReason(reason)} <code>{reason}</code></span>
                {/each}
              {:else}
                <span class="meta">{$messages.duplicatesSignals}: —</span>
              {/if}
              <span class="meta">{$messages.duplicatesSharedTags}: {pair.shared_tags.length ? pair.shared_tags.join(', ') : '—'}</span>
            </div>

            <div class="lessons">
              {#each lessonSides(pair) as item}
                <section class="lesson" aria-label={item.heading}>
                  <h4>{item.heading}</h4>
                  <dl class="identity">
                    <div><dt>{$messages.duplicatesPositionZero}</dt><dd>{item.position}</dd></div>
                    <div><dt>ID</dt><dd class="identity-value" title={item.id || undefined}>{item.id || '—'}</dd></div>
                    <div><dt>{$messages.duplicatesPath}</dt><dd class="identity-value" title={item.path === '—' ? undefined : item.path}>{item.path}</dd></div>
                  </dl>
                  <h5>{$messages.duplicatesText}</h5>
                  <pre>{item.lesson.text}</pre>
                  <h5>{$messages.duplicatesMetadata}</h5>
                  <dl class="metadata">
                    {#each metadata(item.lesson) as field}
                      <div><dt>{field[0]}</dt><dd>{field[1]}</dd></div>
                    {/each}
                    <div>
                      <dt>{$messages.fieldTags}</dt>
                      <dd>{item.lesson.tags?.length ? item.lesson.tags.join(', ') : '—'}</dd>
                    </div>
                  </dl>
                </section>
              {/each}
            </div>
          </article>
        {/each}
      </section>
    {/if}
  {:else}
    <p class="meta">{$messages.duplicatesInitialHelp}</p>
  {/if}
</section>

<style>
  .duplicates, .pair-list { display: grid; gap: 16px; }
  h3, h4, h5 { margin: 0; }
  .controls-description { margin: 0 0 16px; }
  .control-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; }
  label { display: grid; gap: 5px; color: var(--muted); font-size: .85rem; }
  input[type='number'] { padding: 8px 10px; border: 1px solid var(--border); border-radius: 8px; background: white; color: var(--text); }
  .checkbox-label { display: flex; align-items: center; gap: 8px; padding-top: 25px; }
  .summary-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 10px; margin: 0; }
  .summary-grid div, .identity div, .metadata div { border: 1px solid var(--border); border-radius: 7px; padding: 8px; }
  dt { color: var(--muted); font-size: .76rem; }
  dd { margin: 3px 0 0; overflow-wrap: anywhere; }
  .pair-header { display: flex; justify-content: space-between; align-items: center; gap: 12px; }
  .signals, .reasons { display: flex; align-items: center; flex-wrap: wrap; gap: 7px; }
  .kind, .score, .reason { border-radius: 999px; padding: 3px 8px; font-size: .78rem; }
  .kind.exact { background: #dff4e5; color: #146c3b; }
  .kind.near { background: #fff0d9; color: #955600; }
  .score, .reason { background: #f3efe8; }
  .reason code { color: var(--muted); font-size: .75rem; }
  .reasons { margin: 12px 0; }
  .lessons { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
  .lesson { min-width: 0; border: 1px solid var(--border); border-radius: 8px; padding: 12px; }
  .lesson h4 { margin-bottom: 10px; }
  .lesson h5 { margin: 14px 0 6px; font-size: .83rem; color: var(--muted); }
  .identity, .metadata { display: grid; grid-template-columns: repeat(auto-fit, minmax(115px, 1fr)); gap: 7px; margin: 0; }
  .identity-value {
    display: -webkit-box;
    -webkit-box-orient: vertical;
    -webkit-line-clamp: 2;
    line-clamp: 2;
    overflow: hidden;
    height: 2.4em;
    line-height: 1.2;
  }
  pre { margin: 0; padding: 10px; white-space: pre-wrap; overflow-wrap: anywhere; background: #f7f4ee; border-radius: 6px; font: .85rem/1.45 ui-monospace, SFMono-Regular, Menlo, monospace; }
  @media (max-width: 850px) { .lessons { grid-template-columns: 1fr; } }
</style>
