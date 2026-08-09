<script lang="ts">
  import { onMount } from 'svelte'
  import { api, type ExportSearchRequest, type Lesson } from '../lib/api'
  import { navigate } from '../lib/router'
  import { formatMessage, messages } from '../lib/i18n'
  import LessonCard from '../components/LessonCard.svelte'
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
  let limit = $state(20)

  let lessons = $state<Lesson[]>([])
  let loading = $state(false)
  let exporting = $state(false)
  let error = $state('')
  let status = $state('')

  function buildSearchBody(): ExportSearchRequest {
    return {
      q: q.trim() || null,
      topic_in: topic.trim() ? [topic.trim()] : null,
      source_in: source.trim() ? [source.trim()] : null,
      importance_gte: importanceGte ? Number(importanceGte) : null,
      importance_lte: importanceLte ? Number(importanceLte) : null,
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
      lessons = await api.searchLessons(buildSearchBody())
      status = formatMessage(
        $messages.browseResults,
        { count: lessons.length },
      )
    } catch (e) {
      lessons = []
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
      lessons = await api.listLessons(Number(limit) || 50)
      status = formatMessage(
        $messages.browseLessons,
        { count: lessons.length },
      )
    } catch (e) {
      lessons = []
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
  }

  function submitSearch(event: SubmitEvent) {
    event.preventDefault()
    runSearch()
  }

  onMount(() => {
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

    {#if error}
      <FormStatus
        message={error}
        tone="error"
        style="--giu-form-status-padding: var(--space-2) var(--space-3)"
      />
    {/if}
  </Panel>

  <section class="results">
    {#if loading}
      <p class="meta">{$messages.commonLoading}</p>
    {:else if lessons.length === 0}
      <p class="meta">{$messages.browseEmpty}</p>
    {:else}
      {#each lessons as lesson}
        <LessonCard
          {lesson}
          onclick={() => navigate({ view: 'detail', id: lesson.id })}
        />
      {/each}
    {/if}
  </section>
</div>

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

  input {
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
