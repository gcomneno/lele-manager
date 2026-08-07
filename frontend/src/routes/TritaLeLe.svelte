<script lang="ts">
  import { onMount } from 'svelte'
  import {
    ApiError,
    api,
    type ApprovalResult,
    type Candidate,
    type CandidateFilters,
    type CandidateState,
    type CanonicalMetadata,
    type IngestionResult,
    type RawSourceInput,
    type SourceKind,
    type VaultTreeNode,
  } from '../lib/api'
  import { renderMarkdown } from '../lib/markdown'
  import { formatMessage, messages } from '../lib/i18n'
  import CandidateCard from '../components/CandidateCard.svelte'

  type ReadBackState = 'idle' | 'loading' | 'ok' | 'error'

  function candidateStateLabel(state: CandidateState): string {
    switch (state) {
      case 'staged':
        return $messages.tritaleleStateStaged
      case 'in_review':
        return $messages.tritaleleStateInReview
      case 'rejected':
        return $messages.tritaleleStateRejected
      case 'approved':
        return $messages.tritaleleStateApproved
      default:
        return state
    }
  }

  function sourceKindLabel(kind: SourceKind): string {
    switch (kind) {
      case 'plain_text':
        return $messages.tritaleleSourceKindPlainText
      case 'markdown':
        return $messages.tritaleleSourceKindMarkdown
      case 'stdin':
        return $messages.tritaleleSourceKindStdin
      case 'in_memory':
        return $messages.tritaleleSourceKindMemory
      default:
        return kind
    }
  }

  function reviewActionLabel(action: string): string {
    switch (action) {
      case 'revise':
        return $messages.tritaleleActionRevise
      case 'accept':
        return $messages.tritaleleActionAccept
      case 'reject':
        return $messages.tritaleleActionReject
      case 'approve':
        return $messages.tritaleleActionApprove
      default:
        return action
    }
  }

  function approvalOutcomeLabel(outcome: string): string {
    switch (outcome) {
      case 'created':
        return $messages.tritaleleOutcomeCreated
      case 'identical':
        return $messages.tritaleleOutcomeIdentical
      default:
        return outcome
    }
  }

  let sourceContent = $state('')
  let sourceKind = $state<SourceKind>('plain_text')
  let logicalName = $state('pasted-note.txt')
  let maxCharacters = $state(2000)
  let loadedFileName = $state('')
  let inputVersion = $state(0)
  let fileRequest = 0
  let previewRequest = 0
  let stageRequest = 0

  let preview = $state<IngestionResult | null>(null)
  let previewVersion = $state(-1)
  let previewLoading = $state(false)
  let staging = $state(false)
  let ingestionError = $state('')
  let stageResult = $state<IngestionResult | null>(null)

  let stateFilter = $state<CandidateState | ''>('')
  let kindFilter = $state<SourceKind | ''>('')
  let nameFilter = $state('')
  let fingerprintFilter = $state('')
  let chunkFilter = $state('')
  let candidates = $state<Candidate[]>([])
  let candidatesLoading = $state(true)
  let candidatesError = $state('')
  let listRequest = 0

  let selectedId = $state<string | null>(null)
  let candidate = $state<Candidate | null>(null)
  let detailLoading = $state(false)
  let detailError = $state('')
  let detailRequest = 0
  let actionRequest = 0
  let mutating = $state(false)
  let actionMessage = $state('')
  let actionError = $state('')
  let transitionReason = $state('')

  let proposedText = $state('')
  let metadataTopic = $state('')
  let metadataSource = $state('note')
  let metadataImportance = $state(3)
  let metadataTags = $state('')
  let metadataDate = $state(new Date().toISOString().slice(0, 10))
  let metadataTitle = $state('')
  let revisionReason = $state('')

  let approvalDialog = $state(false)
  let approving = $state(false)
  let approvalResult = $state<ApprovalResult | null>(null)
  let approvalWarning = $state('')
  let recoveryDetails = $state<Record<string, unknown> | null>(null)
  let readBackRequest = 0
  let lessonReadBack = $state<ReadBackState>('idle')
  let lessonReadBackMessage = $state('')
  let vaultReadBack = $state<ReadBackState>('idle')
  let vaultReadBackMessage = $state('')

  function sourcePayload(): RawSourceInput {
    return {
      content: sourceContent,
      source_kind: sourceKind,
      logical_name: logicalName.trim(),
      max_characters: Number(maxCharacters),
    }
  }

  function invalidatePreview() {
    inputVersion += 1
    previewRequest += 1
    stageRequest += 1
    preview = null
    previewVersion = -1
    previewLoading = false
    staging = false
    stageResult = null
    ingestionError = ''
  }

  function sourceChanged() {
    fileRequest += 1
    loadedFileName = ''
    invalidatePreview()
  }

  function sourceSettingsChanged() {
    fileRequest += 1
    invalidatePreview()
  }

  async function loadFile(event: Event) {
    const input = event.currentTarget as HTMLInputElement
    const file = input.files?.[0]
    const request = ++fileRequest
    invalidatePreview()
    if (!file) {
      loadedFileName = ''
      return
    }
    ingestionError = ''
    try {
      const content = await file.text()
      if (request !== fileRequest) return
      sourceContent = content
      logicalName = file.name
      sourceKind = /\.(md|markdown)$/i.test(file.name) ? 'markdown' : 'plain_text'
      loadedFileName = file.name
      invalidatePreview()
    } catch {
      if (request !== fileRequest) return
      ingestionError = $messages.tritaleleFileReadError
    }
  }

  function displayError(error: unknown, context: string): string {
    if (!(error instanceof ApiError)) {
      return formatMessage(
        $messages.tritaleleContextError,
        {
          context,
          error:
            error instanceof Error
              ? error.message
              : String(error),
        },
      )
    }

    if (error.status === 409) {
      return formatMessage(
        $messages.tritaleleConflict,
        {
          code: error.code ? ` · ${error.code}` : '',
        },
      )
    }

    if (error.status === 422) {
      return $messages.tritaleleInvalidData
    }

    if (error.status === 503) {
      return formatMessage(
        $messages.tritaleleOperationalError,
        {
          code: error.code ? ` · ${error.code}` : '',
        },
      )
    }

    if (error.status === 400) {
      return formatMessage(
        $messages.tritaleleInvalidRequest,
        {
          code: error.code ? ` (${error.code})` : '',
        },
      )
    }

    return formatMessage(
      $messages.tritaleleContextError,
      {
        context,
        error: error.message,
      },
    )
  }

  async function runPreview() {
    if (!sourceContent.trim() || !logicalName.trim()) {
      ingestionError = $messages.tritaleleSourceRequired
      return
    }
    const request = ++previewRequest
    const version = inputVersion
    previewLoading = true
    ingestionError = ''
    stageResult = null
    try {
      const result = await api.previewIngestion(sourcePayload())
      if (request !== previewRequest || version !== inputVersion) return
      preview = result
      previewVersion = version
    } catch (error) {
      if (request !== previewRequest || version !== inputVersion) return
      preview = null
      previewVersion = -1
      ingestionError = displayError(
        error,
        $messages.tritalelePreviewFailed,
      )
    } finally {
      if (request === previewRequest && version === inputVersion) previewLoading = false
    }
  }

  async function runStage() {
    if (!preview || previewVersion !== inputVersion) {
      ingestionError = $messages.tritalelePreviewRequired
      return
    }
    const request = ++stageRequest
    const version = inputVersion
    staging = true
    ingestionError = ''
    try {
      const result = await api.stageIngestion(sourcePayload())
      if (request !== stageRequest || version !== inputVersion) return
      stageResult = result
      await loadCandidates()
    } catch (error) {
      if (request !== stageRequest || version !== inputVersion) return
      ingestionError = displayError(
        error,
        $messages.tritaleleStageFailed,
      )
      if (error instanceof ApiError) recoveryDetails = error.recovery
    } finally {
      if (request === stageRequest && version === inputVersion) staging = false
    }
  }

  function filters(): CandidateFilters {
    const parsedChunk = chunkFilter.trim() === '' ? null : Number(chunkFilter)
    return {
      state: stateFilter,
      source_kind: kindFilter,
      source_logical_name: nameFilter,
      source_fingerprint: fingerprintFilter,
      chunk_index:
        parsedChunk !== null && Number.isInteger(parsedChunk) && parsedChunk >= 0
          ? parsedChunk
          : null,
    }
  }

  async function loadCandidates(showLoading = true) {
    const request = ++listRequest
    if (showLoading) candidatesLoading = true
    candidatesError = ''
    try {
      const result = await api.listCandidates(filters())
      if (request !== listRequest) return
      candidates = result.candidates
    } catch (error) {
      if (request !== listRequest) return
      candidates = []
      candidatesError = displayError(
        error,
        $messages.tritaleleCandidateListUnavailable,
      )
    } finally {
      if (request === listRequest) candidatesLoading = false
    }
  }

  function resetFilters() {
    stateFilter = ''
    kindFilter = ''
    nameFilter = ''
    fingerprintFilter = ''
    chunkFilter = ''
    loadCandidates()
  }

  function populateReviewForm(item: Candidate) {
    proposedText = item.effective_text
    const metadata = item.proposed_metadata
    metadataTopic = metadata?.topic ?? ''
    metadataSource = metadata?.source ?? 'note'
    metadataImportance = metadata?.importance ?? 3
    metadataTags = metadata?.tags.join(', ') ?? ''
    metadataDate = metadata?.date ?? new Date().toISOString().slice(0, 10)
    metadataTitle = metadata?.title ?? ''
    revisionReason = ''
    transitionReason = ''
  }

  function resetApprovalState() {
    approvalDialog = false
    approving = false
    approvalResult = null
    approvalWarning = ''
    recoveryDetails = null
    readBackRequest += 1
    lessonReadBack = 'idle'
    lessonReadBackMessage = ''
    vaultReadBack = 'idle'
    vaultReadBackMessage = ''
  }

  async function selectCandidate(item: Candidate) {
    selectedId = item.candidate_id
    candidate = null
    detailLoading = true
    detailError = ''
    actionMessage = ''
    actionError = ''
    resetApprovalState()
    const request = ++detailRequest
    try {
      const result = await api.getCandidate(item.candidate_id)
      if (request !== detailRequest || selectedId !== item.candidate_id) return
      candidate = result
      populateReviewForm(result)
    } catch (error) {
      if (request !== detailRequest || selectedId !== item.candidate_id) return
      detailError = displayError(
        error,
        $messages.tritaleleDetailUnavailable,
      )
    } finally {
      if (request === detailRequest && selectedId === item.candidate_id) detailLoading = false
    }
  }

  async function reloadSelected() {
    const listItem = candidates.find((item) => item.candidate_id === selectedId)
    if (listItem) {
      await selectCandidate(listItem)
      return
    }
    if (!selectedId) return
    const placeholder = candidate
    if (placeholder) await selectCandidate(placeholder)
  }

  function replaceCandidate(updated: Candidate) {
    candidate = updated
    candidates = candidates.map((item) =>
      item.candidate_id === updated.candidate_id ? updated : item,
    )
    populateReviewForm(updated)
  }

  function reviewMetadata(): CanonicalMetadata | null {
    const tags = metadataTags
      .split(',')
      .map((tag) => tag.trim())
      .filter(Boolean)
    if (
      !metadataTopic.trim() ||
      !metadataSource.trim() ||
      !metadataTitle.trim() ||
      !metadataDate.trim() ||
      tags.length === 0 ||
      !Number.isInteger(Number(metadataImportance)) ||
      Number(metadataImportance) < 1 ||
      Number(metadataImportance) > 5
    ) {
      return null
    }
    return {
      topic: metadataTopic,
      source: metadataSource,
      importance: Number(metadataImportance),
      tags,
      date: metadataDate,
      title: metadataTitle,
    }
  }

  async function saveRevision() {
    if (!candidate || candidate.state !== 'staged') return
    const metadata = reviewMetadata()
    if (!proposedText.trim() || !metadata) {
      actionError = $messages.tritaleleReviewFieldsRequired
      return
    }
    const textChanged = proposedText !== candidate.effective_text
    const metadataChanged = JSON.stringify(metadata) !== JSON.stringify(candidate.proposed_metadata)
    if (!textChanged && !metadataChanged) {
      actionError = $messages.tritaleleNoChanges
      return
    }
    const captured = candidate
    const request = ++actionRequest
    mutating = true
    actionError = ''
    actionMessage = ''
    try {
      const updated = await api.reviseCandidate(captured.candidate_id, {
        expected_revision: captured.revision,
        ...(textChanged ? { proposed_text: proposedText } : {}),
        ...(metadataChanged ? { proposed_metadata: metadata } : {}),
        ...(revisionReason.trim() ? { reason: revisionReason.trim() } : {}),
      })
      if (request !== actionRequest || selectedId !== captured.candidate_id) return
      replaceCandidate(updated)
      actionMessage = formatMessage(
        $messages.tritaleleRevisionSaved,
        { revision: updated.revision },
      )
    } catch (error) {
      if (request !== actionRequest || selectedId !== captured.candidate_id) return
      actionError = displayError(
        error,
        $messages.tritaleleRevisionFailed,
      )
      if (error instanceof ApiError) recoveryDetails = error.recovery
    } finally {
      if (request === actionRequest) mutating = false
    }
  }

  async function acceptCandidate() {
    if (!candidate || candidate.state !== 'staged') return
    if (!candidate.approval_destination) {
      actionError =
        $messages.tritaleleAcceptMetadataRequired
      return
    }
    const captured = candidate
    const request = ++actionRequest
    mutating = true
    actionError = ''
    actionMessage = ''
    try {
      const updated = await api.acceptCandidate(
        captured.candidate_id,
        captured.revision,
        transitionReason,
      )
      if (request !== actionRequest || selectedId !== captured.candidate_id) return
      replaceCandidate(updated)
      actionMessage = formatMessage(
        $messages.tritaleleAccepted,
        { revision: updated.revision },
      )
    } catch (error) {
      if (request !== actionRequest || selectedId !== captured.candidate_id) return
      actionError = displayError(
        error,
        $messages.tritaleleAcceptFailed,
      )
      if (error instanceof ApiError) recoveryDetails = error.recovery
    } finally {
      if (request === actionRequest) mutating = false
    }
  }

  async function rejectCandidate() {
    if (!candidate || !['staged', 'in_review'].includes(candidate.state)) return
    if (!transitionReason.trim()) {
      actionError =
        $messages.tritaleleRejectReasonRequired
      return
    }
    const captured = candidate
    const request = ++actionRequest
    mutating = true
    actionError = ''
    actionMessage = ''
    try {
      const updated = await api.rejectCandidate(
        captured.candidate_id,
        captured.revision,
        transitionReason,
      )
      if (request !== actionRequest || selectedId !== captured.candidate_id) return
      replaceCandidate(updated)
      actionMessage = formatMessage(
        $messages.tritaleleRejected,
        { revision: updated.revision },
      )
    } catch (error) {
      if (request !== actionRequest || selectedId !== captured.candidate_id) return
      actionError = displayError(
        error,
        $messages.tritaleleRejectFailed,
      )
      if (error instanceof ApiError) recoveryDetails = error.recovery
    } finally {
      if (request === actionRequest) mutating = false
    }
  }

  function treeContainsPath(node: VaultTreeNode, relativePath: string): boolean {
    if (node.type === 'file') return node.path === relativePath
    return node.children?.some((child) => treeContainsPath(child, relativePath)) ?? false
  }

  async function runReadBacks(lessonId: string, relativePath: string) {
    const request = ++readBackRequest
    lessonReadBack = 'loading'
    lessonReadBackMessage =
      $messages.tritaleleProjectionReadbackLoading
    vaultReadBack = 'loading'
    vaultReadBackMessage =
      $messages.tritaleleVaultReadbackLoading

    void api.getLesson(lessonId).then(
      (lesson) => {
        if (request !== readBackRequest) return
        lessonReadBack = 'ok'
        lessonReadBackMessage = formatMessage(
          $messages.tritaleleLessonReadback,
          { id: lesson.id },
        )
      },
      (error) => {
        if (request !== readBackRequest) return
        lessonReadBack = 'error'
        lessonReadBackMessage = displayError(
          error,
          $messages.tritaleleLessonReadbackFailed,
        )
      },
    )

    void api.vaultTree().then(
      (tree) => {
        if (request !== readBackRequest) return
        if (treeContainsPath(tree.tree, relativePath)) {
          vaultReadBack = 'ok'
          vaultReadBackMessage = formatMessage(
            $messages.tritaleleVaultReadback,
            { path: relativePath },
          )
        } else {
          vaultReadBack = 'error'
          vaultReadBackMessage = formatMessage(
            $messages.tritaleleVaultFileMissing,
            { path: relativePath },
          )
        }
      },
      (error) => {
        if (request !== readBackRequest) return
        vaultReadBack = 'error'
        vaultReadBackMessage = displayError(
          error,
          $messages.tritaleleVaultReadbackFailed,
        )
      },
    )
  }

  function recoveredApproval(error: ApiError): ApprovalResult | null {
    const raw = error.recovery?.partial_approval_result
    if (typeof raw !== 'object' || raw === null) return null
    const value = raw as Record<string, unknown>
    if (
      typeof value.candidate_id !== 'string' ||
      typeof value.candidate_revision !== 'number' ||
      typeof value.lesson_id !== 'string' ||
      typeof value.relative_vault_path !== 'string' ||
      (value.vault_write_outcome !== 'created' && value.vault_write_outcome !== 'identical')
    ) {
      return null
    }
    return value as unknown as ApprovalResult
  }

  async function refreshApprovedCandidate(candidateId: string, request: number) {
    try {
      const updated = await api.getCandidate(candidateId)
      if (request !== actionRequest || selectedId !== candidateId) return
      replaceCandidate(updated)
    } catch {
      // The publication outcome and the two explicit read-backs remain independently visible.
    }
  }

  async function confirmApproval() {
    if (approving || !candidate || candidate.state !== 'in_review') return
    const destination = candidate.approval_destination
    if (!destination) return
    const captured = candidate
    const request = ++actionRequest
    approving = true
    mutating = true
    actionError = ''
    actionMessage = ''
    approvalWarning = ''
    recoveryDetails = null
    try {
      const result = await api.approveCandidate(captured.candidate_id, captured.revision)
      if (request !== actionRequest || selectedId !== captured.candidate_id) return
      approvalResult = result
      approvalDialog = false
      actionMessage = formatMessage(
        result.vault_write_outcome === 'created'
          ? $messages.tritaleleApprovalCreated
          : $messages.tritaleleApprovalIdentical,
        { path: result.relative_vault_path },
      )
      await refreshApprovedCandidate(captured.candidate_id, request)
      void runReadBacks(result.lesson_id, result.relative_vault_path)
    } catch (error) {
      if (request !== actionRequest || selectedId !== captured.candidate_id) return
      if (error instanceof ApiError && error.code === 'partial_refresh') {
        const recovered = recoveredApproval(error)
        approvalDialog = false
        approvalResult = recovered
        approvalWarning =
          $messages.tritaleleApprovalPartialRefresh
        recoveryDetails = error.recovery
        await refreshApprovedCandidate(captured.candidate_id, request)
        if (recovered) void runReadBacks(recovered.lesson_id, recovered.relative_vault_path)
      } else {
        actionError = displayError(
          error,
          $messages.tritaleleApprovalFailed,
        )
        if (error instanceof ApiError) recoveryDetails = error.recovery
      }
    } finally {
      if (request === actionRequest) {
        approving = false
        mutating = false
      }
    }
  }

  onMount(() => {
    loadCandidates()
  })
</script>

<div class="tritalele">
  <section class="card ingestion" aria-labelledby="ingestion-title">
    <div class="section-head">
      <div>
        <h2 id="ingestion-title">{$messages.tritaleleCollectTitle}</h2>
        <p class="meta">{$messages.tritaleleCollectDescription}</p>
      </div>
      {#if loadedFileName}<span class="tag">{$messages.tritaleleFileTag}: {loadedFileName}</span>{/if}
    </div>

    <div class="source-grid">
      <label>
        {$messages.tritaleleFileInput}
        <input type="file" accept=".md,.markdown,.txt,text/markdown,text/plain" onchange={loadFile} />
      </label>
      <label>
        {$messages.tritaleleContentFormat}
        <select bind:value={sourceKind} onchange={sourceSettingsChanged}>
          <option value="plain_text">{$messages.tritaleleSourceKindPlainText}</option>
          <option value="markdown">{$messages.tritaleleSourceKindMarkdown}</option>
        </select>
      </label>
      <label>
        {$messages.tritaleleSourceName}
        <input bind:value={logicalName} oninput={sourceSettingsChanged} />
      </label>
      <label>
        {$messages.tritaleleMaxSectionSize}
        <input type="number" min="1" bind:value={maxCharacters} oninput={sourceSettingsChanged} />
      </label>
    </div>
    <label class="source-text">
      {$messages.tritaleleSourceText}
      <textarea
        rows="8"
        bind:value={sourceContent}
        oninput={sourceChanged}
        placeholder={$messages.tritaleleSourcePlaceholder}
      ></textarea>
    </label>
    <div class="actions">
      <button class="btn" onclick={runPreview} disabled={previewLoading || staging}>
        {previewLoading
          ? $messages.tritalelePreviewing
          : $messages.tritaleleCreatePreview}
      </button>
      <button
        class="btn btn-primary"
        onclick={runStage}
        disabled={!preview || previewVersion !== inputVersion || previewLoading || staging}
      >
        {staging
          ? $messages.tritaleleStaging
          : $messages.tritaleleAddCollection}
      </button>
    </div>
    {#if ingestionError}<p class="error" role="alert">{ingestionError}</p>{/if}

    {#if preview}
      <div class="preview-block" data-testid="ingestion-preview">
        <h3>{$messages.tritalelePreviewTitle}</h3>
        <p class="meta">
          {$messages.tritalelePlanned}: {preview.counts.planned}
          · {$messages.tritaleleNew}: {preview.counts.pending}
          · {$messages.tritaleleAlreadyPresent}: {preview.counts.skipped}
        </p>
        <ol>
          {#each preview.candidates as item}
            <li>
              <code>{item.candidate_id.slice(7, 19)}</code>
              <span>{item.effective_text.slice(0, 180)}</span>
            </li>
          {/each}
        </ol>
      </div>
    {/if}

    {#if stageResult}
      <div class="stage-result ok" role="status">
        {$messages.tritaleleStageCompleted}
        · {$messages.tritaleleCreated}: {stageResult.counts.created}
        · {$messages.tritaleleIdenticalSkipped}: {stageResult.counts.skipped}
      </div>
    {/if}
  </section>

  <section class="review-layout">
    <div class="candidate-column">
      <section class="card filters" aria-labelledby="candidate-list-title">
        <div class="section-head">
          <h2 id="candidate-list-title">{$messages.tritaleleReviewListTitle}</h2>
          <button class="btn" onclick={() => loadCandidates()} disabled={candidatesLoading}>{$messages.tritaleleRefresh}</button>
        </div>
        <div class="filter-grid">
          <label>
            {$messages.tritaleleStateLabel}
            <select bind:value={stateFilter}>
              <option value="">{$messages.tritaleleAll}</option>
              <option value="staged">{$messages.tritaleleStateStaged}</option>
              <option value="in_review">{$messages.tritaleleStateInReview}</option>
              <option value="rejected">{$messages.tritaleleStateRejected}</option>
              <option value="approved">{$messages.tritaleleStateApproved}</option>
            </select>
          </label>
          <label>
            {$messages.tritaleleType}
            <select bind:value={kindFilter}>
              <option value="">{$messages.tritaleleAll}</option>
              <option value="markdown">{$messages.tritaleleSourceKindMarkdown}</option>
              <option value="plain_text">{$messages.tritaleleSourceKindPlainText}</option>
              <option value="stdin">{$messages.tritaleleSourceKindStdin}</option>
              <option value="in_memory">{$messages.tritaleleSourceKindMemory}</option>
            </select>
          </label>
          <label>{$messages.tritaleleSourceName} <input bind:value={nameFilter} /></label>
          <label>{$messages.tritaleleChunk} <input type="number" min="0" bind:value={chunkFilter} /></label>
          <label class="wide-filter">{$messages.tritaleleFingerprint} <input bind:value={fingerprintFilter} /></label>
        </div>
        <div class="actions compact">
          <button class="btn btn-primary" onclick={() => loadCandidates()}>{$messages.tritaleleApplyFilters}</button>
          <button class="btn" onclick={resetFilters}>{$messages.tritaleleResetFilters}</button>
        </div>
        {#if candidatesError}<p class="error" role="alert">{candidatesError}</p>{/if}
      </section>

      <div class="candidate-list" aria-live="polite">
        {#if candidatesLoading}
          <p class="meta">{$messages.tritaleleCandidatesLoading}</p>
        {:else if candidates.length === 0}
          <p class="card meta empty">{$messages.tritaleleCandidatesEmpty}</p>
        {:else}
          {#each candidates as item (item.candidate_id)}
            <CandidateCard
              candidate={item}
              selected={selectedId === item.candidate_id}
              onclick={() => selectCandidate(item)}
            />
          {/each}
        {/if}
      </div>
    </div>

    <div class="detail-column">
      {#if !selectedId}
        <section class="card empty detail-empty">
          <h2>{$messages.tritaleleDetailTitle}</h2>
          <p class="meta">{$messages.tritaleleNoSelection}</p>
        </section>
      {:else if detailLoading}
        <section class="card"><p class="meta">{$messages.tritaleleDetailLoading}</p></section>
      {:else if detailError}
        <section class="card">
          <p class="error" role="alert">{detailError}</p>
          <button class="btn" onclick={reloadSelected}>{$messages.tritaleleRetry}</button>
        </section>
      {:else if candidate}
        <section class="card candidate-detail" aria-labelledby="candidate-detail-title">
          <div class="section-head">
            <div>
              <h2 id="candidate-detail-title">{$messages.tritaleleDetailTitle}</h2>
              <code>{candidate.candidate_id}</code>
            </div>
            <span class={`state state-${candidate.state}`}>{candidateStateLabel(candidate.state)} · {$messages.tritaleleRevisionShort} {candidate.revision}</span>
          </div>

          <details open>
            <summary>{$messages.tritaleleProvenance}</summary>
            <dl>
              <dt>{$messages.fieldSource}</dt><dd>{candidate.provenance.source_logical_name}</dd>
              <dt>{$messages.tritaleleType}</dt><dd>{sourceKindLabel(candidate.provenance.source_kind)}</dd>
              <dt>{$messages.tritaleleFingerprint}</dt><dd><code>{candidate.provenance.source_fingerprint}</code></dd>
              <dt>{$messages.tritaleleChunk}</dt><dd>{candidate.provenance.chunk_index ?? '—'}</dd>
              <dt>Span</dt><dd>{candidate.provenance.source_span ? `${candidate.provenance.source_span.start}–${candidate.provenance.source_span.end}` : '—'}</dd>
              <dt>{$messages.tritaleleIngestedAt}</dt><dd>{candidate.provenance.ingested_at}</dd>
            </dl>
            {#if Object.keys(candidate.provenance.run_metadata).length || candidate.provenance.transformations.length}
              <pre>{JSON.stringify({ run_metadata: candidate.provenance.run_metadata, transformations: candidate.provenance.transformations }, null, 2)}</pre>
            {/if}
          </details>

          <div class="review-form">
            <label>
              {$messages.tritaleleProposedText}
              <textarea rows="11" bind:value={proposedText} disabled={candidate.state !== 'staged'}></textarea>
            </label>
            <div class="metadata-grid">
              <label>{$messages.fieldTopic} <input bind:value={metadataTopic} disabled={candidate.state !== 'staged'} /></label>
              <label>{$messages.fieldSource} <input bind:value={metadataSource} disabled={candidate.state !== 'staged'} /></label>
              <label>{$messages.fieldImportance} <input type="number" min="1" max="5" bind:value={metadataImportance} disabled={candidate.state !== 'staged'} /></label>
              <label>{$messages.fieldDate} <input type="date" bind:value={metadataDate} disabled={candidate.state !== 'staged'} /></label>
              <label class="wide">{$messages.fieldTags} <input bind:value={metadataTags} placeholder="python, pytest" disabled={candidate.state !== 'staged'} /></label>
              <label class="wide">{$messages.fieldTitle} <input bind:value={metadataTitle} disabled={candidate.state !== 'staged'} /></label>
            </div>
            {#if candidate.state === 'staged'}
              <label>{$messages.tritaleleRevisionReasonOptional} <input bind:value={revisionReason} /></label>
              <button class="btn" onclick={saveRevision} disabled={mutating}>{$messages.tritaleleSaveRevision}</button>
            {/if}
          </div>

          <div class="markdown-preview">
            <h3>{$messages.tritaleleEffectivePreview}</h3>
            <article class="markdown-body">{@html renderMarkdown(proposedText)}</article>
          </div>

          {#if candidate.approval_destination}
            <div class="destination" data-testid="approval-destination">
              <strong>{$messages.tritaleleCanonicalDestination}</strong>
              <code>{candidate.approval_destination.lesson_id}</code>
              <code>{candidate.approval_destination.relative_vault_path}</code>
            </div>
          {:else}
            <p class="meta">{$messages.tritaleleDestinationUnavailable}</p>
          {/if}

          {#if candidate.state === 'staged' || candidate.state === 'in_review'}
            <label>
              {$messages.tritaleleTransitionReason}
              {$messages.tritaleleRejectRequired}
              <input bind:value={transitionReason} />
            </label>
            <div class="actions">
              {#if candidate.state === 'staged'}
                <button
                  class="btn btn-primary"
                  onclick={acceptCandidate}
                  disabled={mutating || !candidate.approval_destination}
                >
                  {$messages.tritaleleAcceptReview}
                </button>
              {/if}
              <button class="btn danger" onclick={rejectCandidate} disabled={mutating || !transitionReason.trim()}>
                {$messages.tritaleleRejectCandidate}
              </button>
              {#if candidate.state === 'in_review'}
                <button
                  class="btn btn-primary"
                  onclick={() => (approvalDialog = true)}
                  disabled={mutating || !candidate.approval_destination}
                >
                  {$messages.tritaleleApproveVault}
                </button>
              {/if}
            </div>
          {/if}

          {#if actionMessage}<p class="ok" role="status">{actionMessage}</p>{/if}
          {#if actionError}
            <div class="action-error" role="alert">
              <p class="error">{actionError}</p>
              {#if actionError.includes('409')}
                <button class="btn" onclick={reloadSelected}>{$messages.tritaleleReloadCandidate}</button>
              {/if}
            </div>
          {/if}
          {#if approvalWarning}<p class="warning" role="status">{approvalWarning}</p>{/if}
          {#if recoveryDetails}
            <details class="recovery">
              <summary>{$messages.tritaleleRecoveryDetails}</summary>
              <pre>{JSON.stringify(recoveryDetails, null, 2)}</pre>
            </details>
          {/if}
          {#if approvalResult}
            <div class="approval-result" data-testid="approval-result">
              <h3>{$messages.tritaleleApprovalOutcome}: {approvalOutcomeLabel(approvalResult.vault_write_outcome)}</h3>
              <p><code>{approvalResult.lesson_id}</code></p>
              <p><code>{approvalResult.relative_vault_path}</code></p>
            </div>
          {/if}
          {#if lessonReadBack !== 'idle' || vaultReadBack !== 'idle'}
            <div class="readbacks" aria-label={$messages.tritaleleApprovalReadback}>
              <p class:ok={lessonReadBack === 'ok'} class:error={lessonReadBack === 'error'}>{lessonReadBackMessage}</p>
              <p class:ok={vaultReadBack === 'ok'} class:error={vaultReadBack === 'error'}>{vaultReadBackMessage}</p>
            </div>
          {/if}

          <details class="history" open>
            <summary>{$messages.tritaleleHistory} ({candidate.review_history.length})</summary>
            {#if candidate.review_history.length === 0}
              <p class="meta">{$messages.tritaleleNoHistory}</p>
            {:else}
              <ol>
                {#each candidate.review_history as event}
                  <li>
                    <strong>{$messages.tritaleleRevisionShort} {event.revision} · {reviewActionLabel(event.action)}</strong>
                    <span>{candidateStateLabel(event.previous_state)} → {candidateStateLabel(event.resulting_state)}</span>
                    <time>{event.occurred_at}</time>
                    {#if event.reason}<q>{event.reason}</q>{/if}
                  </li>
                {/each}
              </ol>
            {/if}
          </details>
        </section>
      {/if}
    </div>
  </section>
</div>

{#if approvalDialog && candidate?.approval_destination}
  <div class="dialog-backdrop" role="presentation">
    <div class="approval-dialog card" role="dialog" aria-modal="true" aria-labelledby="approval-title">
      <h2 id="approval-title">{$messages.tritaleleApprovalTitle}</h2>
      <p>{$messages.tritaleleApprovalOnlyPublishes}</p>
      <dl>
        <dt>{$messages.tritaleleCandidate}</dt><dd><code>{candidate.candidate_id}</code></dd>
        <dt>{$messages.tritaleleRevision}</dt><dd>{candidate.revision}</dd>
        <dt>{$messages.tritaleleLessonId}</dt><dd><code>{candidate.approval_destination.lesson_id}</code></dd>
        <dt>{$messages.tritaleleCanonicalPath}</dt><dd><code>{candidate.approval_destination.relative_vault_path}</code></dd>
      </dl>
      {#if actionError}<p class="error" role="alert">{actionError}</p>{/if}
      {#if recoveryDetails}
        <details class="recovery">
          <summary>{$messages.tritaleleRecoveryDetails}</summary>
          <pre>{JSON.stringify(recoveryDetails, null, 2)}</pre>
        </details>
      {/if}
      <div class="actions">
        <button class="btn" onclick={() => (approvalDialog = false)} disabled={approving}>{$messages.tritaleleCancel}</button>
        <button class="btn btn-primary" onclick={confirmApproval} disabled={approving}>
          {approving
            ? $messages.tritaleleApproving
            : $messages.tritaleleConfirmApproval}
        </button>
      </div>
    </div>
  </div>
{/if}

<style>
  .tritalele,
  .candidate-column,
  .detail-column,
  .candidate-list {
    display: grid;
    gap: 14px;
  }

  .section-head,
  .actions {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
    flex-wrap: wrap;
  }

  h2,
  h3,
  p {
    margin-top: 0;
  }

  .source-grid,
  .filter-grid,
  .metadata-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 10px;
  }

  .source-text,
  .review-form,
  .review-form > label,
  .candidate-detail > label {
    margin-top: 12px;
  }

  label {
    display: grid;
    gap: 5px;
    color: var(--muted);
    font-size: 0.85rem;
  }

  input,
  select,
  textarea {
    width: 100%;
    padding: 8px 10px;
    border: 1px solid var(--border);
    border-radius: 8px;
    color: var(--text);
    background: white;
  }

  textarea {
    resize: vertical;
  }

  input:disabled,
  textarea:disabled {
    background: #f3efe8;
  }

  .ingestion > .actions,
  .compact {
    justify-content: flex-start;
    margin-top: 12px;
  }

  .preview-block,
  .destination,
  .approval-result,
  .readbacks {
    margin-top: 14px;
    padding: 12px;
    border: 1px solid var(--border);
    border-radius: 8px;
    background: #fffdf9;
  }

  .preview-block ol,
  .history ol {
    display: grid;
    gap: 8px;
    margin-bottom: 0;
    padding-left: 22px;
  }

  .preview-block li,
  .history li,
  .destination {
    display: grid;
    gap: 4px;
  }

  .stage-result {
    margin-top: 12px;
  }

  .review-layout {
    display: grid;
    grid-template-columns: minmax(280px, 0.75fr) minmax(420px, 1.25fr);
    gap: 16px;
    align-items: start;
  }

  .candidate-column,
  .detail-column {
    min-width: 0;
  }

  .candidate-list {
    max-height: 76vh;
    overflow-y: auto;
  }

  .empty {
    text-align: center;
  }

  .detail-empty {
    min-height: 180px;
    align-content: center;
  }

  code,
  dd {
    overflow-wrap: anywhere;
  }

  .state {
    border-radius: 999px;
    padding: 4px 9px;
    font-size: 0.75rem;
    font-weight: 700;
    color: white;
    background: var(--muted);
  }

  .state-in_review { background: var(--warn); }
  .state-approved { background: var(--ok); }
  .state-rejected { background: var(--err); }

  details {
    margin-top: 14px;
  }

  summary {
    cursor: pointer;
    font-weight: 700;
    margin-bottom: 9px;
  }

  dl {
    display: grid;
    grid-template-columns: max-content minmax(0, 1fr);
    gap: 6px 12px;
    margin: 10px 0;
  }

  dt {
    color: var(--muted);
    font-size: 0.82rem;
  }

  dd {
    margin: 0;
  }

  pre {
    overflow-x: auto;
    padding: 10px;
    border-radius: 8px;
    background: #f3efe8;
    white-space: pre-wrap;
  }

  .review-form,
  .markdown-preview {
    margin-top: 16px;
    padding-top: 14px;
    border-top: 1px solid var(--border);
  }

  .review-form > .btn {
    margin-top: 10px;
  }

  .wide,
  .wide-filter {
    grid-column: 1 / -1;
  }

  .danger {
    border-color: var(--err);
    color: var(--err);
  }

  .warning {
    color: var(--warn);
    font-weight: 600;
  }

  .history li span,
  .history li time,
  .history li q {
    display: block;
    font-size: 0.82rem;
    color: var(--muted);
  }

  .dialog-backdrop {
    position: fixed;
    inset: 0;
    z-index: 10;
    display: grid;
    place-items: center;
    padding: 20px;
    background: rgba(31, 27, 22, 0.55);
  }

  .approval-dialog {
    width: min(680px, 100%);
    max-height: 90vh;
    overflow-y: auto;
  }

  .approval-dialog .actions {
    justify-content: flex-end;
    margin-top: 18px;
  }

  @media (max-width: 1000px) {
    .review-layout {
      grid-template-columns: 1fr;
    }

    .candidate-list {
      max-height: none;
    }
  }

  @media (max-width: 650px) {
    .source-grid,
    .filter-grid,
    .metadata-grid {
      grid-template-columns: 1fr;
    }

    .wide,
    .wide-filter {
      grid-column: auto;
    }
  }
</style>
