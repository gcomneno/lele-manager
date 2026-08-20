<script lang="ts">
  import { onMount } from 'svelte'
  import {
    api,
    type ExportSearchRequest,
    type Lesson,
    type LessonLifecycleState,
  } from '../lib/api'
  import { navigate } from '../lib/router'
  import { formatMessage, messages } from '../lib/i18n'
  import { deleteLessonWithOutcome } from '../lib/lessonDeletion'
  import { bulkDeleteLessonsWithOutcome } from '../lib/bulkLessonDeletion'
  import { consumeLessonDeletionNotice } from '../lib/lessonDeletionNotice'
  import LessonCard from '../components/LessonCard.svelte'
  import DeleteLessonDialog from '../components/DeleteLessonDialog.svelte'
  import BulkDeleteLessonsDialog from '../components/BulkDeleteLessonsDialog.svelte'
  import { FormStatus } from 'giadaware-ui-components'
  import {
    Button,
    FieldLabel,
    FormActions,
    Panel,
  } from 'giadaware-ui-components/studio'

  let q = $state('')
  let topic = $state('')
  let source = $state('')
  let importanceGte = $state('')
  let importanceLte = $state('')
  let lifecycle = $state<'all' | LessonLifecycleState>('active')
  let freshness = $state<'all' | 'needed' | 'clear'>('all')
  let limit = $state(20)

  const allLifecycleStates: LessonLifecycleState[] = [
    'active',
    'review-needed',
    'deprecated',
    'archived',
  ]

  function lifecycleScope(): LessonLifecycleState[] {
    return lifecycle === 'all' ? allLifecycleStates : [lifecycle]
  }

  function freshnessFilter(): boolean | null {
    if (freshness === 'needed') return true
    if (freshness === 'clear') return false
    return null
  }

  let lessons = $state<Lesson[]>([])
  let selectedIds = $state<Set<string>>(new Set())
  let loading = $state(false)
  let exporting = $state(false)
  let error = $state('')
  let status = $state('')
  let deleteTarget = $state<Lesson | null>(null)
  let deleteNotice = $state('')
  let deleteNoticeTone = $state<'success' | 'warning'>('success')
  let bulkDeleteTargets = $state<Lesson[]>([])
  let bulkNotice = $state('')
  let bulkNoticeTone = $state<'success' | 'warning' | 'error'>('success')
  let bulkFailedIds = $state<string[]>([])

  function clearSelection() {
    selectedIds = new Set()
  }

  function replaceResults(nextLessons: Lesson[]) {
    lessons = nextLessons
    // A result set is a destructive-selection snapshot boundary. Even IDs in
    // both snapshots must be explicitly selected again after a new query.
    clearSelection()
    bulkNotice = ''
    bulkFailedIds = []
  }

  function toggleSelection(lessonId: string, checked: boolean) {
    const next = new Set(selectedIds)
    if (checked) next.add(lessonId)
    else next.delete(lessonId)
    selectedIds = next
  }

  function selectAllVisible() {
    selectedIds = new Set(lessons.map((lesson) => lesson.id))
  }

  function selectedVisibleLessons() {
    return lessons.filter((lesson) => selectedIds.has(lesson.id))
  }

  function buildSearchBody(): ExportSearchRequest {
    return {
      q: q.trim() || null,
      topic_in: topic.trim() ? [topic.trim()] : null,
      source_in: source.trim() ? [source.trim()] : null,
      importance_gte: importanceGte ? Number(importanceGte) : null,
      importance_lte: importanceLte ? Number(importanceLte) : null,
      lifecycle_in: lifecycleScope(),
      freshness_review_needed: freshnessFilter(),
      limit: Number(limit) || 20,
      include_frontmatter: true,
    }
  }

  function downloadMarkdown(content: string, filename: string) {
    const blob = new Blob([content], { type: 'text/markdown;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = filename
    anchor.click()
    URL.revokeObjectURL(url)
  }

  async function exportResults() {
    exporting = true
    error = ''
    try {
      const markdown = (await api.exportSearch(buildSearchBody(), 'markdown')) as string
      const slug = q.trim().replace(/\s+/g, '-').slice(0, 40) || 'browse'
      downloadMarkdown(markdown, `lele-export-${slug}.md`)
      status = formatMessage(
        $messages.browseExported,
        { count: lessons.length },
      )
    } catch (e) {
      error = e instanceof Error ? e.message : String(e)
    } finally {
      exporting = false
    }
  }

  async function runSearch() {
    loading = true
    error = ''
    status = $messages.browseSearching
    try {
      replaceResults(await api.searchLessons(buildSearchBody()))
      status = formatMessage(
        $messages.browseResults,
        { count: lessons.length },
      )
    } catch (e) {
      replaceResults([])
      status = ''
      error = e instanceof Error ? e.message : String(e)
    } finally {
      loading = false
    }
  }

  async function listAll() {
    loading = true
    error = ''
    status = $messages.commonLoading
    try {
      replaceResults(
        await api.listLessons(Number(limit) || 50, lifecycleScope()),
      )
      status = formatMessage(
        $messages.browseLessons,
        { count: lessons.length },
      )
    } catch (e) {
      replaceResults([])
      status = ''
      error = e instanceof Error ? e.message : String(e)
    } finally {
      loading = false
    }
  }

  function reset() {
    q = ''
    topic = ''
    source = ''
    importanceGte = ''
    importanceLte = ''
    lifecycle = 'active'
    freshness = 'all'
  }

  function submitSearch(event: SubmitEvent) {
    event.preventDefault()
    runSearch()
  }

  async function deleteLesson(lesson: Lesson) {
    error = ''
    try {
      const outcome = await deleteLessonWithOutcome(lesson.id)
      lessons = lessons.filter((item) => item.id !== lesson.id)
      toggleSelection(lesson.id, false)
      if (outcome.kind === 'refreshed') {
        deleteNotice = $messages.lessonDeleted
        deleteNoticeTone = 'success'
      } else {
        deleteNotice = $messages.lessonDeletedRefreshFailed
        deleteNoticeTone = 'warning'
      }
      deleteTarget = null
    } catch {
      error = $messages.lessonDeleteFailed
      deleteTarget = null
    }
  }

  function openBulkDeleteDialog() {
    bulkDeleteTargets = selectedVisibleLessons()
  }

  function selectedTitle(lessonId: string) {
    const lesson = lessons.find((item) => item.id === lessonId)
    return lesson?.title?.trim() || $messages.deleteLessonUntitled
  }

  async function deleteSelected(targets: Lesson[]) {
    error = ''
    bulkNotice = ''
    bulkFailedIds = []
    try {
      const outcome = await bulkDeleteLessonsWithOutcome(targets.map((lesson) => lesson.id))
      const response = outcome.response
      const deletedIds = new Set(response.deleted.map((item) => item.lesson_id))
      const failedIds = new Set(response.failed.map((item) => item.lesson_id))
      lessons = lessons.filter((lesson) => !deletedIds.has(lesson.id))
      selectedIds = new Set(
        [...selectedIds].filter((id) => failedIds.has(id) && lessons.some((lesson) => lesson.id === id)),
      )
      bulkFailedIds = response.failed.map((item) => item.lesson_id)

      if (outcome.kind === 'refresh-failed') {
        bulkNoticeTone = 'warning'
        bulkNotice = [
          $messages.bulkRefreshFailed,
          response.failed.length
            ? formatMessage($messages.bulkDeletedMixed, { deleted: response.deleted.length, failed: response.failed.length })
            : formatMessage($messages.bulkDeleted, { count: response.deleted.length }),
          $messages.bulkRefreshStale,
        ].join(' ')
      } else if (response.deleted.length && response.failed.length) {
        bulkNoticeTone = 'warning'
        bulkNotice = formatMessage($messages.bulkDeletedMixed, {
          deleted: response.deleted.length,
          failed: response.failed.length,
        })
      } else if (response.deleted.length) {
        bulkNoticeTone = 'success'
        bulkNotice = formatMessage($messages.bulkDeleted, { count: response.deleted.length })
      } else {
        bulkNoticeTone = 'error'
        bulkNotice = $messages.bulkNothingDeleted
      }
      bulkDeleteTargets = []
    } catch {
      error = $messages.lessonDeleteFailed
      bulkDeleteTargets = []
    }
  }

  onMount(() => {
    const notice = consumeLessonDeletionNotice()
    if (notice === 'deleted') {
      deleteNotice = $messages.lessonDeleted
      deleteNoticeTone = 'success'
    } else if (notice === 'refresh-failed') {
      deleteNotice = $messages.lessonDeletedRefreshFailed
      deleteNoticeTone = 'warning'
    }
    runSearch()
  })
</script>

<div class="browse">
  <Panel title={$messages.routeBrowseTitle} class="filters">
    <form onsubmit={submitSearch}>
      <div class="grid browse-filter-grid" data-testid="browse-filter-grid">
        <label>
          <FieldLabel label={$messages.fieldQuery} />
          <input bind:value={q} placeholder="pytest, git, pandas…" />
        </label>
        <label>
          <FieldLabel label={$messages.fieldTopic} />
          <input bind:value={topic} placeholder="python" />
        </label>
        <label>
          <FieldLabel label={$messages.fieldSource} />
          <input bind:value={source} placeholder="note" />
        </label>
        <label>
          <FieldLabel label={$messages.browseImportanceMin} />
          <input type="number" min="1" max="5" bind:value={importanceGte} />
        </label>
        <label>
          <FieldLabel label={$messages.browseImportanceMax} />
          <input type="number" min="1" max="5" bind:value={importanceLte} />
        </label>
        <label>
          <FieldLabel label={$messages.browseLifecycle} />
          <select bind:value={lifecycle}>
            <option value="active">{$messages.lifecycleActive}</option>
            <option value="review-needed">{$messages.lifecycleReviewNeeded}</option>
            <option value="deprecated">{$messages.lifecycleDeprecated}</option>
            <option value="archived">{$messages.lifecycleArchived}</option>
            <option value="all">{$messages.lifecycleAllStates}</option>
          </select>
        </label>
        <label>
          <FieldLabel label={$messages.browseFreshness} />
          <select bind:value={freshness}>
            <option value="all">{$messages.browseFreshnessAll}</option>
            <option value="needed">{$messages.browseFreshnessNeeded}</option>
            <option value="clear">{$messages.browseFreshnessClear}</option>
          </select>
        </label>
        <label>
          <FieldLabel label={$messages.browseLimit} />
          <input type="number" min="1" max="500" bind:value={limit} />
        </label>
      </div>
      <FormActions
        class="browse-actions"
        style="--giu-form-actions-gap: var(--space-2); margin-top: var(--space-3)"
      >
        <Button
          type="submit"
          size="compact"
          disabled={loading}
        >
          {$messages.browseSearch}
        </Button>
        <Button
          type="button"
          variant="secondary"
          size="compact"
          onclick={listAll}
          disabled={loading}
          class="lele-secondary-button"
        >
          {$messages.browseListAll}
        </Button>
        <Button
          type="button"
          variant="secondary"
          size="compact"
          onclick={exportResults}
          disabled={loading || exporting || lessons.length === 0}
          class="lele-secondary-button"
        >
          {exporting
            ? $messages.browseExporting
            : $messages.browseExportMarkdown}
        </Button>
        <Button
          type="button"
          variant="secondary"
          size="compact"
          onclick={reset}
          class="lele-secondary-button"
        >
          {$messages.browseReset}
        </Button>
      </FormActions>
    </form>

    {#if status}
      <FormStatus
        message={status}
        tone="info"
        class="browse-result-status"
        style="--giu-form-status-padding: var(--space-2) 0 0; --giu-form-status-border-width: 0; --giu-form-status-info-background: transparent; --giu-form-status-info-color: var(--color-success)"
      />
    {/if}

    {#if deleteNotice}
      <FormStatus
        message={deleteNotice}
        tone={deleteNoticeTone}
        style="--giu-form-status-padding: var(--space-2) var(--space-3)"
      />
    {/if}

    {#if error}
      <FormStatus
        message={error}
        tone="error"
        style="--giu-form-status-padding: var(--space-2) var(--space-3)"
      />
    {/if}

    {#if bulkNotice}
      <FormStatus
        message={bulkNotice}
        tone={bulkNoticeTone}
        style="--giu-form-status-padding: var(--space-2) var(--space-3)"
      />
      {#if bulkFailedIds.length}
        <div class="bulk-failed-targets" role="status">
          <strong>{$messages.bulkFailedTargets}</strong>
          <ul>
            {#each bulkFailedIds as lessonId (lessonId)}
              <li>{selectedTitle(lessonId)} <span>{lessonId}</span></li>
            {/each}
          </ul>
        </div>
      {/if}
    {/if}
  </Panel>

  <section class="results">
    {#if loading}
      <p class="meta">{$messages.commonLoading}</p>
    {:else if lessons.length === 0}
      <p class="meta">{$messages.browseEmpty}</p>
    {:else}
      <div class="selection-controls">
        <Button type="button" variant="secondary" size="compact" class="lele-secondary-button" onclick={selectAllVisible}>
          {$messages.browseSelectAllVisible}
        </Button>
        {#if selectedIds.size > 0}
          <Button type="button" variant="secondary" size="compact" class="lele-secondary-button" onclick={clearSelection}>
            {$messages.browseClearSelection}
          </Button>
          <div class="bulk-action-bar" aria-live="polite">
            <strong>{selectedIds.size === 1 ? $messages.browseSelectedOne : formatMessage($messages.browseSelectedMany, { count: selectedIds.size })}</strong>
            <button type="button" class="delete-action" onclick={openBulkDeleteDialog}>
              {$messages.bulkDeleteSelected}
            </button>
          </div>
        {/if}
      </div>
      {#each lessons as lesson}
        <div class:selected={selectedIds.has(lesson.id)} class="lesson-result" data-testid={`lesson-result-${lesson.id}`}>
          <label class="lesson-selection">
            <input
              type="checkbox"
              checked={selectedIds.has(lesson.id)}
              onchange={(event) => toggleSelection(lesson.id, event.currentTarget.checked)}
            />
            <span>{formatMessage($messages.browseSelectLesson, { title: lesson.title?.trim() || $messages.deleteLessonUntitled, id: lesson.id })}</span>
          </label>
          <LessonCard
            {lesson}
            lifecycleLabels={{
              active: $messages.lifecycleActive,
              'review-needed': $messages.lifecycleReviewNeeded,
              deprecated: $messages.lifecycleDeprecated,
              archived: $messages.lifecycleArchived,
            }}
            onclick={() => navigate({ view: 'detail', id: lesson.id })}
          />
          <div class="lesson-actions" aria-label={`${lesson.id} actions`}>
            <Button
              type="button"
              variant="secondary"
              size="compact"
              class="lele-secondary-button"
              onclick={() => navigate({ view: 'editor', id: lesson.id })}
            >
              {$messages.lessonModify}
            </Button>
            <Button
              type="button"
              variant="secondary"
              size="compact"
              class="lele-secondary-button"
              onclick={() => navigate({ view: 'detail', id: lesson.id })}
            >
              {$messages.lessonInspect}
            </Button>
            <button
              type="button"
              class="delete-action"
              onclick={() => { deleteTarget = lesson }}
            >
              {$messages.deleteLessonDelete}
            </button>
          </div>
        </div>
      {/each}
    {/if}
  </section>
</div>

<DeleteLessonDialog
  lesson={deleteTarget}
  oncancel={() => { deleteTarget = null }}
  onconfirm={deleteLesson}
/>

<BulkDeleteLessonsDialog
  lessons={bulkDeleteTargets}
  oncancel={() => { bulkDeleteTargets = [] }}
  onconfirm={deleteSelected}
/>

<style>
  .browse {
    display: grid;
    gap: 16px;
  }

  .grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
    gap: 12px;
  }

  label {
    display: grid;
    gap: 4px;
    font-size: 0.85rem;
    color: var(--muted);
  }

  input,
  select {
    padding: 8px 10px;
    border: 1px solid var(--border);
    border-radius: 8px;
    background: white;
    color: var(--text);
  }

  .results {
    display: grid;
    gap: 10px;
  }

  .lesson-result {
    display: grid;
    gap: var(--space-2);
    border-radius: var(--radius-sm);
  }

  .lesson-result.selected { outline: 2px solid var(--accent); outline-offset: 3px; }

  .lesson-selection { display: flex; align-items: center; gap: var(--space-2); padding-inline: var(--space-2); color: var(--color-text); cursor: pointer; }
  .lesson-selection input { width: 1rem; height: 1rem; accent-color: var(--accent); }
  .selection-controls { display: flex; flex-wrap: wrap; align-items: center; gap: var(--space-2); }
  .bulk-action-bar { display: flex; flex-wrap: wrap; align-items: center; gap: var(--space-2); padding: var(--space-2); border: 1px solid var(--border); border-radius: var(--radius-sm); }
  .bulk-failed-targets { padding: var(--space-2) var(--space-3); }
  .bulk-failed-targets ul { margin: var(--space-1) 0 0; padding-left: var(--space-4); }
  .bulk-failed-targets span { font-family: ui-monospace, monospace; overflow-wrap: anywhere; }

  .lesson-actions {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-2);
    padding-inline: var(--space-2);
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
  /* Browse filter grid breathing room */
  .browse-filter-grid {
    box-sizing: border-box;
    width: calc(100% - 18px);
  }

  .browse-filter-grid > * {
    min-width: 0;
  }

  .browse-filter-grid input {
    box-sizing: border-box;
    min-width: 0;
    max-width: 100%;
  }

  @media (max-width: 800px) {
    .browse-filter-grid {
      width: 100%;
    }
  }

</style>
