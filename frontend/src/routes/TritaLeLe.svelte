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
  import CandidateCard from '../components/CandidateCard.svelte'

  type ReadBackState = 'idle' | 'loading' | 'ok' | 'error'

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
      ingestionError = 'Impossibile leggere il file selezionato.'
    }
  }

  function displayError(error: unknown, context: string): string {
    if (!(error instanceof ApiError)) {
      return `${context}: ${error instanceof Error ? error.message : String(error)}`
    }
    if (error.status === 409) {
      return `Conflitto (409${error.code ? ` · ${error.code}` : ''}). Ricarica il candidato e riprova.`
    }
    if (error.status === 422) {
      return 'Dati non validi (422). Controlla i campi della richiesta.'
    }
    if (error.status === 503) {
      return `Errore operativo (503${error.code ? ` · ${error.code}` : ''}). I dati già persistiti non vengono nascosti.`
    }
    if (error.status === 400) {
      return `Richiesta non valida${error.code ? ` (${error.code})` : ''}.`
    }
    return `${context}: ${error.message}`
  }

  async function runPreview() {
    if (!sourceContent.trim() || !logicalName.trim()) {
      ingestionError = 'Testo sorgente e nome logico sono obbligatori.'
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
      ingestionError = displayError(error, 'Anteprima non riuscita')
    } finally {
      if (request === previewRequest && version === inputVersion) previewLoading = false
    }
  }

  async function runStage() {
    if (!preview || previewVersion !== inputVersion) {
      ingestionError = 'Genera una nuova anteprima prima di creare lo staging.'
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
      ingestionError = displayError(error, 'Staging non riuscito')
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
      candidatesError = displayError(error, 'Lista candidati non disponibile')
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
      detailError = displayError(error, 'Dettaglio non disponibile')
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
      actionError = 'Testo e metadati completi sono obbligatori; inserisci almeno un tag.'
      return
    }
    const textChanged = proposedText !== candidate.effective_text
    const metadataChanged = JSON.stringify(metadata) !== JSON.stringify(candidate.proposed_metadata)
    if (!textChanged && !metadataChanged) {
      actionError = 'Nessuna modifica da salvare.'
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
      actionMessage = `Revisione ${updated.revision} salvata.`
    } catch (error) {
      if (request !== actionRequest || selectedId !== captured.candidate_id) return
      actionError = displayError(error, 'Revisione non riuscita')
      if (error instanceof ApiError) recoveryDetails = error.recovery
    } finally {
      if (request === actionRequest) mutating = false
    }
  }

  async function acceptCandidate() {
    if (!candidate || candidate.state !== 'staged') return
    if (!candidate.approval_destination) {
      actionError = 'Completa e salva i metadati canonici prima di accettare.'
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
      actionMessage = `Candidato accettato per la revisione ${updated.revision}; non è ancora pubblicato.`
    } catch (error) {
      if (request !== actionRequest || selectedId !== captured.candidate_id) return
      actionError = displayError(error, 'Accettazione non riuscita')
      if (error instanceof ApiError) recoveryDetails = error.recovery
    } finally {
      if (request === actionRequest) mutating = false
    }
  }

  async function rejectCandidate() {
    if (!candidate || !['staged', 'in_review'].includes(candidate.state)) return
    if (!transitionReason.trim()) {
      actionError = 'Inserisci un motivo per rendere il rifiuto tracciabile.'
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
      actionMessage = `Candidato rifiutato alla revisione ${updated.revision}; resta nello staging.`
    } catch (error) {
      if (request !== actionRequest || selectedId !== captured.candidate_id) return
      actionError = displayError(error, 'Rifiuto non riuscito')
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
    lessonReadBackMessage = 'Lettura proiezione in corso…'
    vaultReadBack = 'loading'
    vaultReadBackMessage = 'Lettura vault in corso…'

    void api.getLesson(lessonId).then(
      (lesson) => {
        if (request !== readBackRequest) return
        lessonReadBack = 'ok'
        lessonReadBackMessage = `Lesson riletta: ${lesson.id}`
      },
      (error) => {
        if (request !== readBackRequest) return
        lessonReadBack = 'error'
        lessonReadBackMessage = displayError(error, 'Read-back lesson fallito')
      },
    )

    void api.vaultTree().then(
      (tree) => {
        if (request !== readBackRequest) return
        if (treeContainsPath(tree.tree, relativePath)) {
          vaultReadBack = 'ok'
          vaultReadBackMessage = `File vault riletto: ${relativePath}`
        } else {
          vaultReadBack = 'error'
          vaultReadBackMessage = `File non trovato nel read-back vault: ${relativePath}`
        }
      },
      (error) => {
        if (request !== readBackRequest) return
        vaultReadBack = 'error'
        vaultReadBackMessage = displayError(error, 'Read-back vault fallito')
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
      actionMessage =
        result.vault_write_outcome === 'created'
          ? `Approvazione completata: creato ${result.relative_vault_path}.`
          : `Approvazione verificata: file canonico identico ${result.relative_vault_path}.`
      await refreshApprovedCandidate(captured.candidate_id, request)
      void runReadBacks(result.lesson_id, result.relative_vault_path)
    } catch (error) {
      if (request !== actionRequest || selectedId !== captured.candidate_id) return
      if (error instanceof ApiError && error.code === 'partial_refresh') {
        const recovered = recoveredApproval(error)
        approvalDialog = false
        approvalResult = recovered
        approvalWarning =
          'Approvazione persistita, ma refresh della proiezione fallito (partial_refresh). Verifica i read-back separati.'
        recoveryDetails = error.recovery
        await refreshApprovedCandidate(captured.candidate_id, request)
        if (recovered) void runReadBacks(recovered.lesson_id, recovered.relative_vault_path)
      } else {
        actionError = displayError(error, 'Approvazione non riuscita')
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
        <h2 id="ingestion-title">Raccogli nuove LeLe</h2>
        <p class="meta">Trasforma appunti e documenti in nuove LeLe da revisionare.</p>
      </div>
      {#if loadedFileName}<span class="tag">file: {loadedFileName}</span>{/if}
    </div>

    <div class="source-grid">
      <label>
        File Markdown o testo
        <input type="file" accept=".md,.markdown,.txt,text/markdown,text/plain" onchange={loadFile} />
      </label>
      <label>
        Formato del contenuto
        <select bind:value={sourceKind} onchange={sourceSettingsChanged}>
          <option value="plain_text">plain_text</option>
          <option value="markdown">markdown</option>
        </select>
      </label>
      <label>
        Nome della fonte
        <input bind:value={logicalName} oninput={sourceSettingsChanged} />
      </label>
      <label>
        Dimensione massima delle sezioni
        <input type="number" min="1" bind:value={maxCharacters} oninput={sourceSettingsChanged} />
      </label>
    </div>
    <label class="source-text">
      Testo sorgente
      <textarea
        rows="8"
        bind:value={sourceContent}
        oninput={sourceChanged}
        placeholder="Incolla qui testo plain text o Markdown…"
      ></textarea>
    </label>
    <div class="actions">
      <button class="btn" onclick={runPreview} disabled={previewLoading || staging}>
        {previewLoading ? 'Anteprima…' : 'Crea anteprima'}
      </button>
      <button
        class="btn btn-primary"
        onclick={runStage}
        disabled={!preview || previewVersion !== inputVersion || previewLoading || staging}
      >
        {staging ? 'Aggiunta alla raccolta…' : 'Aggiungi alla raccolta'}
      </button>
    </div>
    {#if ingestionError}<p class="error" role="alert">{ingestionError}</p>{/if}

    {#if preview}
      <div class="preview-block" data-testid="ingestion-preview">
        <h3>Anteprima (nessuna scrittura)</h3>
        <p class="meta">
          {preview.counts.planned} pianificati · {preview.counts.pending} nuovi · {preview.counts.skipped} già presenti
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
        Staging completato: {stageResult.counts.created} created, {stageResult.counts.skipped} identical/skipped.
      </div>
    {/if}
  </section>

  <section class="review-layout">
    <div class="candidate-column">
      <section class="card filters" aria-labelledby="candidate-list-title">
        <div class="section-head">
          <h2 id="candidate-list-title">LeLe da revisionare</h2>
          <button class="btn" onclick={() => loadCandidates()} disabled={candidatesLoading}>Aggiorna</button>
        </div>
        <div class="filter-grid">
          <label>
            Stato
            <select bind:value={stateFilter}>
              <option value="">tutti</option>
              <option value="staged">staged</option>
              <option value="in_review">in_review</option>
              <option value="rejected">rejected</option>
              <option value="approved">approved</option>
            </select>
          </label>
          <label>
            Tipo
            <select bind:value={kindFilter}>
              <option value="">tutti</option>
              <option value="markdown">markdown</option>
              <option value="plain_text">plain_text</option>
              <option value="stdin">stdin</option>
              <option value="in_memory">in_memory</option>
            </select>
          </label>
          <label>Nome sorgente <input bind:value={nameFilter} /></label>
          <label>Chunk <input type="number" min="0" bind:value={chunkFilter} /></label>
          <label class="wide-filter">Fingerprint <input bind:value={fingerprintFilter} /></label>
        </div>
        <div class="actions compact">
          <button class="btn btn-primary" onclick={() => loadCandidates()}>Applica filtri</button>
          <button class="btn" onclick={resetFilters}>Reset filtri</button>
        </div>
        {#if candidatesError}<p class="error" role="alert">{candidatesError}</p>{/if}
      </section>

      <div class="candidate-list" aria-live="polite">
        {#if candidatesLoading}
          <p class="meta">Caricamento candidati…</p>
        {:else if candidates.length === 0}
          <p class="card meta empty">Nessun candidato corrisponde ai filtri.</p>
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
          <h2>Dettaglio della LeLe</h2>
          <p class="meta">Nessuna selezione. Scegli esplicitamente un candidato dalla lista.</p>
        </section>
      {:else if detailLoading}
        <section class="card"><p class="meta">Caricamento dettaglio…</p></section>
      {:else if detailError}
        <section class="card">
          <p class="error" role="alert">{detailError}</p>
          <button class="btn" onclick={reloadSelected}>Riprova</button>
        </section>
      {:else if candidate}
        <section class="card candidate-detail" aria-labelledby="candidate-detail-title">
          <div class="section-head">
            <div>
              <h2 id="candidate-detail-title">Dettaglio della LeLe</h2>
              <code>{candidate.candidate_id}</code>
            </div>
            <span class={`state state-${candidate.state}`}>{candidate.state} · rev {candidate.revision}</span>
          </div>

          <details open>
            <summary>Provenienza</summary>
            <dl>
              <dt>Sorgente</dt><dd>{candidate.provenance.source_logical_name}</dd>
              <dt>Tipo</dt><dd>{candidate.provenance.source_kind}</dd>
              <dt>Fingerprint</dt><dd><code>{candidate.provenance.source_fingerprint}</code></dd>
              <dt>Chunk</dt><dd>{candidate.provenance.chunk_index ?? '—'}</dd>
              <dt>Span</dt><dd>{candidate.provenance.source_span ? `${candidate.provenance.source_span.start}–${candidate.provenance.source_span.end}` : '—'}</dd>
              <dt>Ingested at</dt><dd>{candidate.provenance.ingested_at}</dd>
            </dl>
            {#if Object.keys(candidate.provenance.run_metadata).length || candidate.provenance.transformations.length}
              <pre>{JSON.stringify({ run_metadata: candidate.provenance.run_metadata, transformations: candidate.provenance.transformations }, null, 2)}</pre>
            {/if}
          </details>

          <div class="review-form">
            <label>
              Testo proposto
              <textarea rows="11" bind:value={proposedText} disabled={candidate.state !== 'staged'}></textarea>
            </label>
            <div class="metadata-grid">
              <label>Topic <input bind:value={metadataTopic} disabled={candidate.state !== 'staged'} /></label>
              <label>Source <input bind:value={metadataSource} disabled={candidate.state !== 'staged'} /></label>
              <label>Importance <input type="number" min="1" max="5" bind:value={metadataImportance} disabled={candidate.state !== 'staged'} /></label>
              <label>Date <input type="date" bind:value={metadataDate} disabled={candidate.state !== 'staged'} /></label>
              <label class="wide">Tags <input bind:value={metadataTags} placeholder="python, pytest" disabled={candidate.state !== 'staged'} /></label>
              <label class="wide">Title <input bind:value={metadataTitle} disabled={candidate.state !== 'staged'} /></label>
            </div>
            {#if candidate.state === 'staged'}
              <label>Motivo revisione (opzionale) <input bind:value={revisionReason} /></label>
              <button class="btn" onclick={saveRevision} disabled={mutating}>Salva revisione</button>
            {/if}
          </div>

          <div class="markdown-preview">
            <h3>Preview testo effettivo</h3>
            <article class="markdown-body">{@html renderMarkdown(proposedText)}</article>
          </div>

          {#if candidate.approval_destination}
            <div class="destination" data-testid="approval-destination">
              <strong>Destinazione canonica calcolata dal backend</strong>
              <code>{candidate.approval_destination.lesson_id}</code>
              <code>{candidate.approval_destination.relative_vault_path}</code>
            </div>
          {:else}
            <p class="meta">Destinazione non calcolabile: completa e salva i metadati.</p>
          {/if}

          {#if candidate.state === 'staged' || candidate.state === 'in_review'}
            <label>
              Motivo transizione {candidate.state === 'staged' ? '(obbligatorio per rifiutare)' : '(obbligatorio per rifiutare)'}
              <input bind:value={transitionReason} />
            </label>
            <div class="actions">
              {#if candidate.state === 'staged'}
                <button
                  class="btn btn-primary"
                  onclick={acceptCandidate}
                  disabled={mutating || !candidate.approval_destination}
                >
                  Accetta per revisione
                </button>
              {/if}
              <button class="btn danger" onclick={rejectCandidate} disabled={mutating || !transitionReason.trim()}>
                Rifiuta candidato
              </button>
              {#if candidate.state === 'in_review'}
                <button
                  class="btn btn-primary"
                  onclick={() => (approvalDialog = true)}
                  disabled={mutating || !candidate.approval_destination}
                >
                  Approva nel vault
                </button>
              {/if}
            </div>
          {/if}

          {#if actionMessage}<p class="ok" role="status">{actionMessage}</p>{/if}
          {#if actionError}
            <div class="action-error" role="alert">
              <p class="error">{actionError}</p>
              {#if actionError.includes('409')}
                <button class="btn" onclick={reloadSelected}>Ricarica candidato</button>
              {/if}
            </div>
          {/if}
          {#if approvalWarning}<p class="warning" role="status">{approvalWarning}</p>{/if}
          {#if recoveryDetails}
            <details class="recovery">
              <summary>Dettagli di recupero</summary>
              <pre>{JSON.stringify(recoveryDetails, null, 2)}</pre>
            </details>
          {/if}
          {#if approvalResult}
            <div class="approval-result" data-testid="approval-result">
              <h3>Esito approvazione: {approvalResult.vault_write_outcome}</h3>
              <p><code>{approvalResult.lesson_id}</code></p>
              <p><code>{approvalResult.relative_vault_path}</code></p>
            </div>
          {/if}
          {#if lessonReadBack !== 'idle' || vaultReadBack !== 'idle'}
            <div class="readbacks" aria-label="Read-back approvazione">
              <p class:ok={lessonReadBack === 'ok'} class:error={lessonReadBack === 'error'}>{lessonReadBackMessage}</p>
              <p class:ok={vaultReadBack === 'ok'} class:error={vaultReadBack === 'error'}>{vaultReadBackMessage}</p>
            </div>
          {/if}

          <details class="history" open>
            <summary>History ({candidate.review_history.length})</summary>
            {#if candidate.review_history.length === 0}
              <p class="meta">Nessuna revisione registrata.</p>
            {:else}
              <ol>
                {#each candidate.review_history as event}
                  <li>
                    <strong>rev {event.revision} · {event.action}</strong>
                    <span>{event.previous_state} → {event.resulting_state}</span>
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
      <h2 id="approval-title">Conferma approvazione canonica</h2>
      <p>Questa è l’unica azione che pubblica nel vault.</p>
      <dl>
        <dt>Candidato</dt><dd><code>{candidate.candidate_id}</code></dd>
        <dt>Revisione</dt><dd>{candidate.revision}</dd>
        <dt>Lesson ID</dt><dd><code>{candidate.approval_destination.lesson_id}</code></dd>
        <dt>Path canonico</dt><dd><code>{candidate.approval_destination.relative_vault_path}</code></dd>
      </dl>
      {#if actionError}<p class="error" role="alert">{actionError}</p>{/if}
      {#if recoveryDetails}
        <details class="recovery">
          <summary>Dettagli di recupero</summary>
          <pre>{JSON.stringify(recoveryDetails, null, 2)}</pre>
        </details>
      {/if}
      <div class="actions">
        <button class="btn" onclick={() => (approvalDialog = false)} disabled={approving}>Annulla</button>
        <button class="btn btn-primary" onclick={confirmApproval} disabled={approving}>
          {approving ? 'Approvazione…' : 'Conferma approvazione'}
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
