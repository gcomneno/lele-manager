<script lang="ts">
  import { api, type DuplicateLessonSnapshot, type DuplicatePair, type DuplicateReportResponse } from '../lib/api'

  const reasonLabels: Record<string, string> = {
    duplicate_id: 'Same lesson ID',
    exact_text: 'Exact normalized text',
    equivalent_metadata: 'Equivalent metadata',
    same_title: 'Same title',
    same_topic: 'Same topic',
    same_source: 'Same source',
    same_date: 'Same date',
    shared_tags: 'Shared tags',
  }

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
    return reasonLabels[reason] ?? 'Reported duplicate signal'
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
      ['Title', lesson.title ?? '—'],
      ['Topic', lesson.topic ?? '—'],
      ['Source', lesson.source ?? '—'],
      ['Importance', lesson.importance ?? '—'],
      ['Date', lesson.date ?? '—'],
      ['Created', lesson.created_at ?? '—'],
    ]
  }

  function lessonSides(pair: DuplicatePair): LessonSide[] {
    return [
      {
        heading: 'Left lesson',
        position: pair.left_position,
        id: pair.left_id,
        lesson: pair.left_lesson,
        path: displayPath(pair, 'left'),
      },
      {
        heading: 'Right lesson',
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
      error = 'Limit must be a whole number of at least 1.'
      return
    }
    const parsedMinScore = requestMinScore()
    if (parsedMinScore == null) {
      error = 'Minimum score must be a finite number between 0 and 1.'
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
  <section class="card controls">
    <h2>Duplicate review</h2>
    <p class="meta">Read-only review of exact and near duplicate candidates. No records are changed.</p>
    <div class="control-grid">
      <label>
        Minimum score
        <input aria-label="Minimum score" type="number" min="0" max="1" step="0.01" bind:value={minScore} />
      </label>
      <label class="checkbox-label">
        <input aria-label="Exact only" type="checkbox" bind:checked={exactOnly} />
        Exact only (does not require the similarity model)
      </label>
      <label>
        Display limit
        <input aria-label="Display limit" type="number" min="1" step="1" bind:value={limit} />
      </label>
    </div>
    <div class="actions">
      <button class="btn btn-primary" onclick={runReview} disabled={loading}>
        {loading ? 'Running…' : report ? 'Refresh review' : 'Run review'}
      </button>
    </div>
  </section>

  {#if loading}
    <p class="meta" role="status">Running duplicate review…</p>
  {:else if error}
    <section class="card error-state" role="alert">
      <h3>{isModelError(error) ? 'Similarity model unavailable' : 'Duplicate review failed'}</h3>
      <p class="error">{error}</p>
      {#if isModelError(error)}
        <p class="meta">Run an exact-only review, or train and make the topic model available before reviewing near duplicates.</p>
      {/if}
    </section>
  {:else if report && appliedQuery}
    <section class="card summary" aria-label="Duplicate review summary">
      <h3>Review summary</h3>
      <dl>
        <div><dt>Lessons analyzed</dt><dd>{report.lessons_analyzed}</dd></div>
        <div><dt>Total pairs before limit</dt><dd>{report.total_pairs}</dd></div>
        <div><dt>Exact pairs before limit</dt><dd>{report.exact_pairs}</dd></div>
        <div><dt>Near pairs before limit</dt><dd>{report.near_pairs}</dd></div>
        <div><dt>Configured minimum score</dt><dd>{appliedQuery.minScore}</dd></div>
        <div><dt>Configured display limit</dt><dd>{appliedQuery.limit}</dd></div>
        <div><dt>Exact only</dt><dd>{appliedQuery.exactOnly ? 'Yes' : 'No'}</dd></div>
        <div><dt>Displayed pairs</dt><dd>{report.pairs.length}</dd></div>
      </dl>
    </section>

    {#if report.pairs.length === 0}
      <section class="card empty-state">
        <h3>No duplicate pairs found</h3>
        <p class="meta">Try a lower minimum score or review a dataset with more lessons.</p>
      </section>
    {:else}
      <section class="pair-list" aria-label="Duplicate pairs">
        {#each report.pairs as pair, index (`${pair.left_position}-${pair.right_position}-${index}`)}
          <article class="card duplicate-pair">
            <header class="pair-header">
              <h3>Pair {index + 1}</h3>
              <div class="signals">
                <span class:exact={pair.kind === 'exact'} class:near={pair.kind === 'near'} class="kind">{pair.kind} duplicate</span>
                <span class="score">Score {pair.score.toFixed(3)}</span>
              </div>
            </header>
            <div class="reasons" aria-label="Duplicate signals">
              {#if pair.reasons.length}
                {#each pair.reasons as reason}
                  <span class="reason" title={reason}>{describeReason(reason)} <code>{reason}</code></span>
                {/each}
              {:else}
                <span class="meta">Reasons: —</span>
              {/if}
              <span class="meta">Shared tags: {pair.shared_tags.length ? pair.shared_tags.join(', ') : '—'}</span>
            </div>

            <div class="lessons">
              {#each lessonSides(pair) as item}
                <section class="lesson" aria-label={item.heading}>
                  <h4>{item.heading}</h4>
                  <dl class="identity">
                    <div><dt>Position (zero-based)</dt><dd>{item.position}</dd></div>
                    <div><dt>ID</dt><dd>{item.id || '—'}</dd></div>
                    <div><dt>Path</dt><dd>{item.path}</dd></div>
                  </dl>
                  <h5>Text</h5>
                  <pre>{item.lesson.text}</pre>
                  <h5>Metadata</h5>
                  <dl class="metadata">
                    {#each metadata(item.lesson) as field}
                      <div><dt>{field[0]}</dt><dd>{field[1]}</dd></div>
                    {/each}
                    <div>
                      <dt>Tags</dt>
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
    <p class="meta">Choose the review settings and run the read-only check.</p>
  {/if}
</section>

<style>
  .duplicates, .pair-list { display: grid; gap: 16px; }
  h2, h3, h4, h5 { margin: 0; }
  .controls > .meta { margin: 8px 0 16px; }
  .control-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; }
  label { display: grid; gap: 5px; color: var(--muted); font-size: .85rem; }
  input[type='number'] { padding: 8px 10px; border: 1px solid var(--border); border-radius: 8px; background: white; color: var(--text); }
  .checkbox-label { display: flex; align-items: center; gap: 8px; padding-top: 25px; }
  .actions { margin-top: 14px; }
  .summary h3 { margin-bottom: 12px; }
  .summary dl { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 10px; margin: 0; }
  .summary dl div, .identity div, .metadata div { border: 1px solid var(--border); border-radius: 7px; padding: 8px; }
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
  pre { margin: 0; padding: 10px; white-space: pre-wrap; overflow-wrap: anywhere; background: #f7f4ee; border-radius: 6px; font: .85rem/1.45 ui-monospace, SFMono-Regular, Menlo, monospace; }
  @media (max-width: 850px) { .lessons { grid-template-columns: 1fr; } }
</style>
