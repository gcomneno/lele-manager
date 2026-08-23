<script lang="ts">
  import {
    ApiError,
    api,
    type ContradictionCandidate,
    type ContradictionCanonicalRequest,
    type ContradictionReportResponse,
  } from '../lib/api'
  import { locale, messages } from '../lib/i18n'

  type CanonicalAction = 'superseded-by' | 'corrects' | 'contradicts'
  type Direction = 'left-right' | 'right-left' | ''

  let loading = $state(false)
  let error = $state<string | null>(null)
  let report = $state<ContradictionReportResponse | null>(null)
  let selected = $state<ContradictionCandidate | null>(null)
  let action = $state<CanonicalAction | null>(null)
  let direction = $state<Direction>('')
  let submitting = $state(false)
  let notice = $state<string | null>(null)

  function reasonLabel(reason: string): string {
    if (reason === 'same-topic') return $messages.contradictionsSameTopic
    if (reason === 'opposing-modal-cue') {
      return $messages.contradictionsOpposingModalCue
    }
    return reason
  }

  function relationLabel(
    selectedAction: CanonicalAction,
    sourceId: string,
    targetId: string,
  ): string {
    if ($locale === 'it') {
      if (selectedAction === 'superseded-by') {
        return `${sourceId} è sostituita da ${targetId}`
      }
      if (selectedAction === 'corrects') {
        return `${sourceId} corregge ${targetId}`
      }
      return `${sourceId} contraddice ${targetId}`
    }

    if (selectedAction === 'superseded-by') {
      return `${sourceId} is superseded by ${targetId}`
    }
    if (selectedAction === 'corrects') {
      return `${sourceId} corrects ${targetId}`
    }
    return `${sourceId} contradicts ${targetId}`
  }

  function actionTitle(selectedAction: CanonicalAction): string {
    if (selectedAction === 'superseded-by') {
      return $messages.contradictionsSupersededBy
    }
    if (selectedAction === 'corrects') {
      return $messages.contradictionsCorrects
    }
    return $messages.contradictionsContradicts
  }

  function saveLabel(selectedAction: CanonicalAction): string {
    if (selectedAction === 'superseded-by') {
      return $messages.contradictionsSaveSupersession
    }
    if (selectedAction === 'corrects') {
      return $messages.contradictionsSaveCorrection
    }
    return $messages.contradictionsSaveContradiction
  }

  function controlledError(err: unknown): string {
    if (err instanceof ApiError) {
      if (
        err.code === 'contradiction_stale'
        || err.code === 'contradiction_conflict'
      ) {
        return $messages.contradictionsStale
      }

      if (err.code === 'contradiction_recovery_indeterminate') {
        return $messages.contradictionsRecoveryIndeterminate
      }

      if (err.code === 'contradiction_store_failed') {
        return $messages.contradictionsStoreFailed
      }
    }

    return err instanceof Error ? err.message : String(err)
  }

  async function runReview() {
    loading = true
    error = null
    notice = null

    try {
      report = await api.contradictions({ limit: 20 })
    } catch (err) {
      error = controlledError(err)
    } finally {
      loading = false
    }
  }

  async function saveAuxiliary(
    candidate: ContradictionCandidate,
    decision: 'different-context' | 'dismissed',
  ) {
    submitting = true
    error = null
    notice = null

    try {
      await api.dismissContradiction({
        decision,
        left_id: candidate.left_id,
        right_id: candidate.right_id,
        left_fingerprint: candidate.left_fingerprint,
        right_fingerprint: candidate.right_fingerprint,
        note: null,
      })
      notice = $messages.contradictionsAuxiliarySaved
    } catch (err) {
      error = controlledError(err)
    } finally {
      submitting = false
    }
  }

  function openCanonical(
    candidate: ContradictionCandidate,
    selectedAction: CanonicalAction,
  ) {
    selected = candidate
    action = selectedAction
    direction = ''
    error = null
    notice = null
  }

  function closeAction() {
    selected = null
    action = null
    direction = ''
  }

  function canonicalRequest(
    candidate: ContradictionCandidate,
    selectedAction: CanonicalAction,
    selectedDirection: Exclude<Direction, ''>,
  ): ContradictionCanonicalRequest {
    const sourceIsLeft = selectedDirection === 'left-right'
    const sourceId = sourceIsLeft ? candidate.left_id : candidate.right_id
    const targetId = sourceIsLeft ? candidate.right_id : candidate.left_id
    const expectedSourceRevision = sourceIsLeft
      ? candidate.left_canonical_revision
      : candidate.right_canonical_revision

    if (selectedAction === 'superseded-by') {
      return {
        decision: 'superseded-by',
        superseded_id: sourceId,
        replacement_id: targetId,
        expected_superseded_revision: expectedSourceRevision,
      }
    }

    if (selectedAction === 'corrects') {
      return {
        decision: 'corrects',
        correcting_id: sourceId,
        corrected_id: targetId,
        expected_correcting_revision: expectedSourceRevision,
      }
    }

    return {
      decision: 'contradicts',
      source_id: sourceId,
      target_id: targetId,
      expected_source_revision: expectedSourceRevision,
    }
  }

  async function saveCanonical() {
    if (!selected || !action || !direction) return

    const candidate = selected
    const selectedAction = action
    const selectedDirection = direction

    submitting = true
    error = null
    notice = null

    try {
      const result = await api.resolveContradiction(
        canonicalRequest(candidate, selectedAction, selectedDirection),
      )

      notice = result.partial_success
        ? $messages.contradictionsPartialSuccess
        : $messages.contradictionsDirectionalSaved

      closeAction()
    } catch (err) {
      error = controlledError(err)
    } finally {
      submitting = false
    }
  }
</script>

<section class="contradictions-page">
  <header class="page-header">
    <div>
      <h1>{$messages.contradictionsTitle}</h1>
      <p>{$messages.contradictionsDescription}</p>
    </div>

    <button type="button" onclick={runReview} disabled={loading}>
      {$messages.contradictionsStartReview}
    </button>
  </header>

  {#if loading}
    <p role="status">{$messages.contradictionsLoading}</p>
  {/if}

  {#if error}
    <p class="error" role="alert">{error}</p>
  {/if}

  {#if notice}
    <p class="notice" role="status">{notice}</p>
  {/if}

  {#if report && report.candidates.length === 0}
    <p>{$messages.contradictionsNoCandidates}</p>
  {/if}

  {#if report}
    <div class="candidate-list">
      {#each report.candidates as candidate}
        <article class="candidate-card">
          <h2>{$messages.contradictionsCandidate}</h2>

          <section aria-label={$messages.contradictionsWhySurfaced}>
            <h3>{$messages.contradictionsWhySurfaced}</h3>

            <ul>
              {#each candidate.same_subject_reasons as reason}
                <li>{reasonLabel(reason)}</li>
              {/each}

              {#each candidate.tension_reasons as reason}
                <li>{reasonLabel(reason)}</li>
              {/each}
            </ul>

            {#if candidate.similarity_score != null}
              <p>
                <strong>{$messages.contradictionsRetrievalScore}</strong>:
                {candidate.similarity_score.toFixed(2)}
              </p>
              <p>{$messages.contradictionsRetrievalMetadata}</p>
            {/if}

            <p>{$messages.contradictionsAdvisoryCue}</p>
          </section>

          <div class="snapshots">
            <section>
              <h3>{candidate.left_lesson.title ?? candidate.left_id}</h3>
              <code>{candidate.left_id}</code>
              <p>{candidate.left_lesson.text}</p>
            </section>

            <section>
              <h3>{candidate.right_lesson.title ?? candidate.right_id}</h3>
              <code>{candidate.right_id}</code>
              <p>{candidate.right_lesson.text}</p>
            </section>
          </div>

          <section aria-label={$messages.contradictionsAuxiliary}>
            <h3>{$messages.contradictionsAuxiliary}</h3>

            <button
              type="button"
              disabled={submitting}
              onclick={() => saveAuxiliary(candidate, 'different-context')}
            >
              {$messages.contradictionsDifferentContext}
            </button>

            <button
              type="button"
              disabled={submitting}
              onclick={() => saveAuxiliary(candidate, 'dismissed')}
            >
              {$messages.contradictionsDismiss}
            </button>
          </section>

          <section aria-label={$messages.contradictionsCanonical}>
            <h3>{$messages.contradictionsCanonical}</h3>

            <button
              type="button"
              disabled={!candidate.resolution_available || submitting}
              onclick={() => openCanonical(candidate, 'superseded-by')}
            >
              {$messages.contradictionsSupersededBy}
            </button>

            <button
              type="button"
              disabled={!candidate.resolution_available || submitting}
              onclick={() => openCanonical(candidate, 'corrects')}
            >
              {$messages.contradictionsCorrects}
            </button>

            <button
              type="button"
              disabled={!candidate.resolution_available || submitting}
              onclick={() => openCanonical(candidate, 'contradicts')}
            >
              {$messages.contradictionsContradicts}
            </button>
          </section>
        </article>
      {/each}
    </div>
  {/if}

  {#if selected && action}
    <section
      class="direction-panel"
      aria-label={actionTitle(action)}
    >
      <h2>{actionTitle(action)}</h2>
      <p>{$messages.contradictionsDirectionHelp}</p>

      <label>
        <input
          type="radio"
          name="contradiction-direction"
          value="left-right"
          bind:group={direction}
        />
        {relationLabel(action, selected.left_id, selected.right_id)}
      </label>

      <label>
        <input
          type="radio"
          name="contradiction-direction"
          value="right-left"
          bind:group={direction}
        />
        {relationLabel(action, selected.right_id, selected.left_id)}
      </label>

      <div class="actions">
        <button type="button" onclick={closeAction}>
          {$messages.commonCancel}
        </button>

        <button
          type="button"
          disabled={!direction || submitting}
          onclick={saveCanonical}
        >
          {saveLabel(action)}
        </button>
      </div>
    </section>
  {/if}
</section>
