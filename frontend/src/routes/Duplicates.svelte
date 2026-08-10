<script lang="ts">
  import { tick } from 'svelte'
  import { FormStatus } from 'giadaware-ui-components'
  import {
    Button,
    FieldLabel,
    FormActions,
    Panel,
  } from 'giadaware-ui-components/studio'
  import { ApiError, api, type DuplicateLessonSnapshot, type DuplicatePair, type DuplicateReportResponse } from '../lib/api'
  import { formatMessage, messages } from '../lib/i18n'
  import { navigate } from '../lib/router'
  import { deleteLessonWithOutcome } from '../lib/lessonDeletion'

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
  let notice = $state('')
  let staleReview = $state(false)
  let selectedPair = $state<DuplicatePair | null>(null)
  let dialog = $state<'delete-left' | 'delete-right' | 'not-duplicates' | 'merge' | null>(null)
  let submitting = $state(false)
  let mergeConfirm = $state(false)
  let mergeSurvivor = $state<'left' | 'right' | null>(null)
  let mergeDraftDirty = $state(false)
  let mergeText = $state('')
  let mergeTitle = $state('')
  let mergeTopic = $state('')
  let mergeSource = $state('note')
  let mergeImportance = $state(3)
  let mergeTags = $state('')
  let mergeDate = $state('')
  let deleteDialog = $state<HTMLDialogElement>()
  let notDuplicatesDialog = $state<HTMLDialogElement>()
  let mergeDialog = $state<HTMLDialogElement>()
  let cancelButton = $state<HTMLButtonElement>()

  $effect(() => {
    const active = dialog === 'merge'
      ? mergeDialog
      : dialog === 'not-duplicates'
        ? notDuplicatesDialog
        : dialog === 'delete-left' || dialog === 'delete-right'
          ? deleteDialog
          : undefined
    if (active && !active.open) {
      void (async () => {
        await tick()
        active.showModal()
        // Destructive paths deliberately begin at Cancel. Merge begins at the
        // unselected survivor choice, so the user must make that choice.
        if (dialog === 'merge') active.querySelector<HTMLInputElement>('input[name="merge-survivor"]')?.focus()
        else cancelButton?.focus()
      })()
    } else if (!active) {
      for (const candidate of [deleteDialog, notDuplicatesDialog, mergeDialog]) {
        if (candidate?.open) candidate.close()
      }
    }
  })

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
    notice = ''
    staleReview = false

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

  async function rerunApplied() {
    if (!appliedQuery) return
    loading = true
    error = ''
    staleReview = false
    try {
      report = await api.duplicates({
        min_score: appliedQuery.minScore,
        exact_only: appliedQuery.exactOnly,
        limit: appliedQuery.limit,
      })
    } catch (e) {
      error = e instanceof Error ? e.message : String(e)
    } finally {
      loading = false
    }
  }

  function closeDialog(force = false) {
    if (submitting && !force) return
    selectedPair = null
    dialog = null
    mergeConfirm = false
  }

  function handleDialogClose() {
    if (!submitting) closeDialog()
  }

  function handleDialogCancel(event: Event) {
    if (submitting) event.preventDefault()
  }

  function selectedSide(side: 'left' | 'right') {
    if (!selectedPair) return null
    return side === 'left'
      ? { id: selectedPair.left_id, lesson: selectedPair.left_lesson, fingerprint: selectedPair.left_fingerprint }
      : { id: selectedPair.right_id, lesson: selectedPair.right_lesson, fingerprint: selectedPair.right_fingerprint }
  }

  function openResolution(pair: DuplicatePair, next: NonNullable<typeof dialog>) {
    if (!pair.resolution_available) return
    selectedPair = pair
    dialog = next
    notice = ''
    if (next === 'merge') {
      mergeSurvivor = null
      mergeDraftDirty = false
      mergeText = ''
      mergeTitle = ''
      mergeTopic = ''
      mergeSource = 'note'
      mergeImportance = 3
      mergeTags = ''
      mergeDate = ''
      mergeConfirm = false
    }
  }

  function initialiseMergeDraft(side: 'left' | 'right') {
    const lesson = selectedSide(side)?.lesson
    if (!lesson) return
    mergeText = lesson.text ?? ''
    mergeTitle = lesson.title ?? ''
    mergeTopic = lesson.topic ?? ''
    mergeSource = lesson.source ?? 'note'
    mergeImportance = lesson.importance ?? 3
    mergeTags = (lesson.tags ?? []).join(', ')
    mergeDate = lesson.date ?? ''
  }

  function chooseMergeSurvivor(side: 'left' | 'right') {
    if (mergeSurvivor === null || !mergeDraftDirty) initialiseMergeDraft(side)
    mergeSurvivor = side
  }

  function markMergeDraftDirty() {
    mergeDraftDirty = true
    mergeConfirm = false
  }

  function pruneDeleted(lessonId: string) {
    if (!report) return
    report = { ...report, pairs: report.pairs.filter((pair) => pair.left_id !== lessonId && pair.right_id !== lessonId) }
  }

  async function confirmDelete() {
    if (!selectedPair || !dialog || (dialog !== 'delete-left' && dialog !== 'delete-right')) return
    const deleting = dialog === 'delete-left' ? selectedPair.left_id : selectedPair.right_id
    submitting = true
    try {
      const outcome = await deleteLessonWithOutcome(deleting)
      closeDialog(true)
      if (outcome.kind === 'refresh-failed') {
        pruneDeleted(deleting)
        staleReview = true
        notice = $messages.duplicatesCanonicalDeletedStale
      } else {
        notice = formatMessage($messages.lessonDeleted, {})
        await rerunApplied()
      }
    } catch {
      notice = $messages.duplicatesDeleteFailed
      closeDialog(true)
    } finally {
      submitting = false
    }
  }

  async function confirmNotDuplicates() {
    if (!selectedPair) return
    submitting = true
    try {
      await api.markNotDuplicates(selectedPair)
      closeDialog(true)
      await rerunApplied()
    } catch (e) {
      closeDialog(true)
      if (e instanceof ApiError && e.code === 'duplicate_pair_stale') {
        notice = $messages.duplicatesStale
        await rerunApplied()
      } else {
        notice = e instanceof Error ? e.message : String(e)
      }
    } finally {
      submitting = false
    }
  }

  async function confirmMerge() {
    if (!selectedPair || !mergeSurvivor) return
    const survivor = selectedSide(mergeSurvivor)
    const superseded = selectedSide(mergeSurvivor === 'left' ? 'right' : 'left')
    if (!survivor || !superseded) return
    submitting = true
    try {
      const result = await api.mergeDuplicates({
        survivor_id: survivor.id,
        superseded_id: superseded.id,
        expected_survivor_fingerprint: survivor.fingerprint,
        expected_superseded_fingerprint: superseded.fingerprint,
        result: {
          text: mergeText,
          title: mergeTitle || null,
          topic: mergeTopic,
          source: mergeSource || 'note',
          importance: Number(mergeImportance),
          tags: mergeTags.split(',').map((tag) => tag.trim()).filter(Boolean),
          date: mergeDate || null,
        },
      })
      closeDialog(true)
      if (result.completed) {
        notice = formatMessage($messages.duplicatesMerged, { survivor: result.survivor_id, superseded: result.superseded_id })
      } else {
        notice = `${$messages.duplicatesMergeIncomplete} ${$messages.duplicatesMergePartial}`
      }
      await rerunApplied()
    } catch (e) {
      closeDialog(true)
      if (e instanceof ApiError && e.code === 'duplicate_merge_refresh_failed') {
        const recovery = mergeRefreshRecovery(e.recovery)
        if (recovery?.survivorWritten && recovery.supersededDeleted) {
          pruneDeleted(recovery.supersededId)
          staleReview = true
          notice = $messages.duplicatesMergeRefreshFailed
        } else if (recovery?.survivorWritten && !recovery.supersededDeleted) {
          staleReview = true
          notice = $messages.duplicatesMergePartialRefreshFailed
        } else {
          notice = $messages.duplicatesMergeFailed
        }
      } else if (e instanceof ApiError && e.code === 'duplicate_pair_stale') {
        notice = $messages.duplicatesStale
        await rerunApplied()
      } else {
        notice = e instanceof Error ? e.message : String(e)
      }
    } finally {
      submitting = false
    }
  }

  function mergeRefreshRecovery(value: Record<string, unknown> | null): {
    survivorId: string
    survivorWritten: boolean
    supersededId: string
    supersededDeleted: boolean
    refreshFailed: boolean
  } | null {
    if (!value || typeof value.survivor_id !== 'string' || typeof value.superseded_id !== 'string'
      || typeof value.survivor_written !== 'boolean' || typeof value.superseded_deleted !== 'boolean'
      || !value.refresh_outcome || typeof value.refresh_outcome !== 'object') return null
    const refresh = value.refresh_outcome as Record<string, unknown>
    if (refresh.attempted !== true || refresh.refreshed !== false) return null
    if (!value.superseded_deleted && (!value.failure || typeof value.failure !== 'object'
      || (value.failure as Record<string, unknown>).code !== 'duplicate_merge_superseded_delete_failed')) return null
    return {
      survivorId: value.survivor_id,
      survivorWritten: value.survivor_written,
      supersededId: value.superseded_id,
      supersededDeleted: value.superseded_deleted,
      refreshFailed: true,
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
        <div><dt>{$messages.duplicatesSuppressedPairs}</dt><dd>{report.suppressed_pairs}</dd></div>
      </dl>
    </Panel>

    {#if notice}
      <FormStatus message={notice} tone={staleReview ? 'warning' : 'success'} style="--giu-form-status-padding: var(--space-2) var(--space-3)" />
    {/if}

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
            {#if pair.resolution_available}
              <div class="resolution-actions" aria-label="Duplicate resolution actions">
                <button type="button" onclick={() => navigate({ view: 'editor', id: pair.left_id })}>{$messages.duplicatesEditLeft}</button>
                <button type="button" onclick={() => navigate({ view: 'editor', id: pair.right_id })}>{$messages.duplicatesEditRight}</button>
                <button type="button" onclick={() => openResolution(pair, 'delete-right')}>{$messages.duplicatesKeepLeftDeleteRight}</button>
                <button type="button" onclick={() => openResolution(pair, 'delete-left')}>{$messages.duplicatesKeepRightDeleteLeft}</button>
                <button type="button" onclick={() => openResolution(pair, 'not-duplicates')}>{$messages.duplicatesNotDuplicates}</button>
                <button type="button" onclick={() => openResolution(pair, 'merge')}>{$messages.duplicatesMerge}</button>
              </div>
            {:else}
              <FormStatus message={pair.resolution_problem || $messages.duplicatesUnsafeIdentity} tone="warning" style="--giu-form-status-padding: var(--space-2) var(--space-3)" />
            {/if}
          </article>
        {/each}
      </section>
    {/if}
  {:else}
    <p class="meta">{$messages.duplicatesInitialHelp}</p>
  {/if}
</section>

<dialog bind:this={notDuplicatesDialog} aria-labelledby="not-duplicates-title" oncancel={handleDialogCancel} onclose={handleDialogClose}>
  {#if selectedPair && dialog === 'not-duplicates'}
    <div class="dialog-card"><h2 id="not-duplicates-title">{$messages.duplicatesNotDuplicatesTitle}</h2>
      <p>{selectedPair.left_lesson.title || '—'} <code>{selectedPair.left_id}</code></p>
      <p>{selectedPair.right_lesson.title || '—'} <code>{selectedPair.right_id}</code></p>
      <p>{$messages.duplicatesNotDuplicatesHelp}</p>
      <div class="dialog-actions"><button bind:this={cancelButton} type="button" disabled={submitting} onclick={() => notDuplicatesDialog?.close()}>{$messages.duplicatesCancel}</button><button type="button" disabled={submitting} onclick={() => void confirmNotDuplicates()}>{$messages.duplicatesMark}</button></div>
    </div>
  {/if}
</dialog>

<dialog bind:this={deleteDialog} aria-labelledby="delete-resolution-title" oncancel={handleDialogCancel} onclose={handleDialogClose}>
  {#if selectedPair && (dialog === 'delete-left' || dialog === 'delete-right')}
    {@const kept = selectedSide(dialog === 'delete-left' ? 'right' : 'left')}
    {@const deleted = selectedSide(dialog === 'delete-left' ? 'left' : 'right')}
    <div class="dialog-card"><h2 id="delete-resolution-title">{$messages.duplicatesConfirmDeleteTitle}</h2>
      <h3>{$messages.duplicatesKeep}</h3><p>{kept?.lesson.title || '—'} <code>{kept?.id}</code></p>
      <h3>{$messages.duplicatesDeletePermanently}</h3><p>{deleted?.lesson.title || '—'} <code>{deleted?.id}</code></p>
      <div class="dialog-actions"><button bind:this={cancelButton} type="button" disabled={submitting} onclick={() => deleteDialog?.close()}>{$messages.duplicatesCancel}</button><button class="danger" type="button" disabled={submitting} onclick={() => void confirmDelete()}>{submitting ? $messages.duplicatesDeleting : $messages.duplicatesDeletePermanently}</button></div>
    </div>
  {/if}
</dialog>

<dialog bind:this={mergeDialog} aria-labelledby="merge-title" oncancel={handleDialogCancel} onclose={handleDialogClose}>
  {#if selectedPair && dialog === 'merge'}
    {@const survivor = mergeSurvivor ? selectedSide(mergeSurvivor) : null}
    {@const superseded = mergeSurvivor ? selectedSide(mergeSurvivor === 'left' ? 'right' : 'left') : null}
    <div class="dialog-card merge-card"><h2 id="merge-title">{$messages.duplicatesMergeTitle}</h2>
      <div class="merge-sources"><section><h3>{$messages.duplicatesSourceLeft}</h3><p>{selectedPair.left_lesson.title || '—'} <code>{selectedPair.left_id}</code></p><pre>{selectedPair.left_lesson.text}</pre></section><section><h3>{$messages.duplicatesSourceRight}</h3><p>{selectedPair.right_lesson.title || '—'} <code>{selectedPair.right_id}</code></p><pre>{selectedPair.right_lesson.text}</pre></section></div>
      <fieldset><legend>{$messages.duplicatesResult}</legend><label><input type="radio" name="merge-survivor" checked={mergeSurvivor === 'left'} onchange={() => chooseMergeSurvivor('left')} /> {$messages.duplicatesUseLeft} <code>{selectedPair.left_id}</code></label><label><input type="radio" name="merge-survivor" checked={mergeSurvivor === 'right'} onchange={() => chooseMergeSurvivor('right')} /> {$messages.duplicatesUseRight} <code>{selectedPair.right_id}</code></label></fieldset>
      <div class="merge-fields"><label>{$messages.fieldTitle}<input bind:value={mergeTitle} oninput={markMergeDraftDirty} /></label><label>{$messages.fieldTopic}<input bind:value={mergeTopic} required oninput={markMergeDraftDirty} /></label><label>{$messages.fieldSource}<input bind:value={mergeSource} oninput={markMergeDraftDirty} /></label><label>{$messages.fieldImportance}<select bind:value={mergeImportance} onchange={markMergeDraftDirty}>{#each [1, 2, 3, 4, 5] as value}<option value={value}>{value}</option>{/each}</select></label><label>{$messages.fieldTags}<input bind:value={mergeTags} oninput={markMergeDraftDirty} /></label><label>{$messages.fieldDate}<input bind:value={mergeDate} oninput={markMergeDraftDirty} /></label><label class="wide">{$messages.duplicatesResult}<textarea rows="8" bind:value={mergeText} oninput={markMergeDraftDirty}></textarea></label></div>
      {#if mergeConfirm}<section class="merge-confirm"><h3>{$messages.duplicatesConfirmMergeTitle}</h3><p>{$messages.duplicatesSurviving}: <code>{survivor?.id}</code></p><p>{$messages.duplicatesSuperseded}: <code>{superseded?.id}</code></p><button type="button" disabled={submitting} onclick={() => void confirmMerge()}>{submitting ? $messages.duplicatesDeleting : $messages.duplicatesSaveMerge}</button></section>{:else}<div class="dialog-actions"><button bind:this={cancelButton} type="button" onclick={() => mergeDialog?.close()}>{$messages.duplicatesCancel}</button><button type="button" onclick={() => { mergeConfirm = true }} disabled={!mergeSurvivor || !mergeText.trim() || !mergeTopic.trim()}>{$messages.duplicatesSaveMerge}</button></div>{/if}
    </div>
  {/if}
</dialog>

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
  .resolution-actions { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 14px; }
  .resolution-actions button, .dialog-actions button, .merge-confirm button { border: 1px solid var(--border); border-radius: 6px; background: var(--color-surface); color: var(--text); padding: 7px 10px; }
  .resolution-actions button:focus-visible, .dialog-actions button:focus-visible, .merge-confirm button:focus-visible { outline: 3px solid var(--accent); outline-offset: 2px; }
  dialog { width: min(650px, calc(100vw - 32px)); max-height: calc(100vh - 32px); padding: 0; border: 1px solid var(--border); border-radius: 10px; color: var(--color-text); background: var(--color-surface); box-shadow: 0 18px 48px rgb(36 28 22 / 28%); }
  dialog::backdrop { background: rgb(36 28 22 / 42%); }
  .dialog-card { width: min(650px, 100%); max-height: calc(100vh - 32px); overflow: auto; padding: 20px; border-radius: 10px; background: var(--color-surface); box-shadow: 0 18px 48px rgb(36 28 22 / 28%); }
  .dialog-card h2, .dialog-card h3 { margin-top: 0; } .dialog-card code { overflow-wrap: anywhere; }
  .dialog-actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 18px; }.danger { background: #a22 !important; color: white !important; border-color: #a22 !important; }
  .merge-card { width: min(1000px, 100%); }.merge-sources { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }.merge-sources section { min-width: 0; border: 1px solid var(--border); padding: 10px; border-radius: 7px; }.merge-sources pre { max-height: 220px; overflow: auto; }
  fieldset { margin: 14px 0; display: flex; flex-wrap: wrap; gap: 12px; }.merge-fields { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 9px; }.merge-fields label { display: grid; gap: 4px; }.merge-fields input, .merge-fields select, .merge-fields textarea { width: 100%; box-sizing: border-box; padding: 7px; }.merge-fields .wide { grid-column: 1 / -1; }.merge-confirm { margin-top: 16px; border: 1px solid #a22; padding: 12px; border-radius: 7px; }
  @media (max-width: 850px) { .lessons, .merge-sources { grid-template-columns: 1fr; } .merge-fields { grid-template-columns: 1fr; } }
</style>
