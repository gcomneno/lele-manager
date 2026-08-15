<script lang="ts">
  import { FormStatus } from 'giadaware-ui-components'
  import {
    Button,
    FieldLabel,
    Panel,
  } from 'giadaware-ui-components/studio'
  import {
    api,
    type EditorMetadataOptionsResponse,
    type Lesson,
    type LessonLifecycleState,
    type SimilarItem,
    type SimilarMeta,
  } from '../lib/api'
  import { stripFrontmatter } from '../lib/markdown'
  import { navigate } from '../lib/router'
  import { formatMessage, messages } from '../lib/i18n'
  import { deleteLessonWithOutcome } from '../lib/lessonDeletion'
  import { setLessonDeletionNotice } from '../lib/lessonDeletionNotice'
  import SimilarPanel from '../components/SimilarPanel.svelte'
  import DeleteLessonDialog from '../components/DeleteLessonDialog.svelte'

  interface Props {
    id?: string
  }

  let { id }: Props = $props()

  // New lessons start without a topic: topic is required, but never inferred.
  let topic = $state('')
  let source = $state('note')
  let importance = $state(3)
  let date = $state(new Date().toISOString().slice(0, 10))
  let tags = $state<string[]>([])
  let tagDraft = $state('')
  let title = $state('')
  let lifecycle = $state<LessonLifecycleState>('active')
  let supersededBy = $state('')
  let body = $state('')
  let lessonId = $state('')
  let loadedLesson = $state<Lesson | null>(null)

  let similar = $state<SimilarItem[]>([])
  let similarMeta = $state<SimilarMeta | null>(null)
  let similarLoading = $state(false)
  let similarError = $state('')
  let similarSearched = $state(false)
  let similarRequestVersion = $state(0)
  let loadError = $state('')
  let saving = $state(false)
  let saveMsg = $state('')
  let saveSucceeded = $state(false)
  let deleteError = $state('')
  let deleteTarget = $state<Lesson | null>(null)
  let metadataOptions = $state<EditorMetadataOptionsResponse>({
    topics: [], tags: [], sources: [],
  })
  let metadataOptionsError = $state('')

  let topK = $state(5)
  let minScore = $state(0.1)

  function composeText(): string {
    const frontmatter = [
      '---',
      lessonId ? `id: ${lessonId}` : 'id: (auto)',
      `topic: ${topic}`,
      `source: ${source}`,
      `importance: ${importance}`,
      `date: ${date}`,
      tags.length
        ? `tags: [${tags.join(', ')}]`
        : 'tags: []',
      title
        ? `title: "${title.replace(/"/g, '\\"')}"`
        : '',
      '---',
      '',
      body,
    ]
      .filter((line) => line !== '')
      .join('\n')

    return frontmatter
  }

  function suggestionSeed(): string {
    return [
      title.trim(),
      tags.join(' '),
      body.trim(),
    ]
      .filter(Boolean)
      .join(' ')
      .trim()
  }

  async function loadMetadataOptions() {
    metadataOptionsError = ''
    try {
      metadataOptions = await api.editorMetadataOptions()
    } catch (e) {
      metadataOptionsError = e instanceof Error ? e.message : String(e)
    }
  }

  function normalized(value: string): string {
    return value.trim().toLocaleLowerCase()
  }

  function addTag(value = tagDraft) {
    const tag = value.trim()
    if (!tag || tags.some((existing) => normalized(existing) === normalized(tag))) {
      tagDraft = ''
      return
    }
    tags = [...tags, tag]
    tagDraft = ''
    invalidateSimilarity()
  }

  function removeTag(index: number) {
    tags = tags.filter((_, tagIndex) => tagIndex !== index)
    invalidateSimilarity()
  }

  function onTagKeydown(event: KeyboardEvent) {
    if (event.key === 'Enter' || event.key === ',') {
      event.preventDefault()
      addTag()
    }
  }

  function suggestedTopic(): string | null {
    // Advisory only: require two matches and a strict majority for one topic.
    const values = similar.map((item) => item.topic?.trim()).filter((value): value is string => Boolean(value))
    if (values.length < 2) return null
    const counts = new Map<string, { value: string, count: number }>()
    for (const value of values) {
      const key = normalized(value)
      const current = counts.get(key) ?? { value, count: 0 }
      current.count += 1
      counts.set(key, current)
    }
    const dominant = [...counts.values()].sort((a, b) => b.count - a.count || a.value.localeCompare(b.value))[0]
    return dominant && dominant.count > values.length / 2 && normalized(dominant.value) !== normalized(topic)
      ? dominant.value : null
  }

  function invalidateSimilarity() {
    similarRequestVersion += 1
    similar = []
    similarMeta = null
    similarLoading = false
    similarError = ''
    similarSearched = false
  }

  async function checkSimilarity() {
    if (suggestionSeed().length < 12) {
      invalidateSimilarity()
      return
    }

    const requestVersion = similarRequestVersion + 1
    similarRequestVersion = requestVersion

    const text = composeText().trim()

    similarLoading = true
    similarError = ''
    similarSearched = true

    try {
      const resp = await api.editorSuggest(
        text,
        topK,
        minScore,
        true,
      )

      if (requestVersion !== similarRequestVersion) {
        return
      }

      similar = resp.results
      similarMeta = resp.meta ?? null
    } catch (e) {
      if (requestVersion !== similarRequestVersion) {
        return
      }

      similar = []
      similarMeta = null
      similarError = e instanceof Error
        ? e.message
        : String(e)
    } finally {
      if (requestVersion === similarRequestVersion) {
        similarLoading = false
      }
    }
  }

  async function loadExisting(lessonIdValue: string) {
    loadError = ''

    try {
      const lesson: Lesson = await api.getLesson(
        lessonIdValue,
      )
      lessonId = lesson.id
      loadedLesson = lesson
      topic = lesson.topic ?? ''
      source = lesson.source ?? ''
      importance = lesson.importance ?? 3
      date = lesson.date ?? date
      title = lesson.title ?? ''
      tags = [...(lesson.tags ?? [])]
      lifecycle = lesson.lifecycle ?? 'active'
      supersededBy = lesson.superseded_by ?? ''

      const parsed = stripFrontmatter(lesson.text ?? '')
      body = parsed.body || lesson.text || ''
      invalidateSimilarity()
    } catch (e) {
      loadedLesson = null
      loadError = e instanceof Error
        ? e.message
        : String(e)
    }
  }

  function buildPayload() {
    if (!Number.isInteger(importance) || importance < 1 || importance > 5) {
      throw new Error($messages.editorImportanceInvalid)
    }

    return {
      text: body,
      topic: topic.trim(),
      // "note" is the documented server default and remains visibly selected.
      source: source.trim() || 'note',
      importance,
      tags: [...tags],
      date: date || null,
      title: title.trim() || null,
      // The Editor is an explicit canonical authoring surface: always send
      // lifecycle fields so active/null can deliberately clear old metadata.
      lifecycle,
      superseded_by: supersededBy.trim() || null,
    }
  }

  async function save() {
    if (!body.trim()) {
      saveSucceeded = false
      saveMsg = $messages.editorBodyRequired
      return
    }

    if (!topic.trim()) {
      saveSucceeded = false
      saveMsg = $messages.editorTopicRequired
      return
    }

    saving = true
    saveSucceeded = false
    saveMsg = ''

    try {
      const payload = buildPayload()
      const targetId = (id || lessonId || '').trim()

      let lesson: Lesson

      if (targetId) {
        lesson = await api.updateLesson(
          targetId,
          payload,
        )
      } else {
        lesson = await api.createVaultLesson({
          ...payload,
          id: lessonId.trim() || null,
        })
      }

      saveSucceeded = true
      saveMsg = formatMessage(
        $messages.editorSaved,
        { id: lesson.id },
      )
      navigate({
        view: 'detail',
        id: lesson.id,
      })
    } catch (e) {
      saveSucceeded = false
      saveMsg = e instanceof Error
        ? e.message
        : String(e)
    } finally {
      saving = false
    }
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
    loadMetadataOptions()
    if (id) {
      loadExisting(id)
    }
  })
</script>

<div class="editor-layout">
  <Panel
    title={id
      ? $messages.editorEditTitle
      : $messages.editorNewTitle}
    class="editor-pane"
  >
    {#snippet actions()}
      <Button
        variant="secondary"
        size="compact"
        onclick={checkSimilarity}
        disabled={
          saving ||
          similarLoading ||
          suggestionSeed().length < 12
        }
      >
        {similarLoading
          ? $messages.editorCheckingSimilarity
          : $messages.editorCheckSimilarity}
      </Button>

      <Button
        size="compact"
        onclick={save}
        disabled={saving}
      >
        {saving
          ? $messages.editorSaving
          : $messages.editorSaveVault}
      </Button>

      {#if id && loadedLesson}
        <button
          type="button"
          class="delete-action"
          onclick={() => { deleteTarget = loadedLesson }}
        >{$messages.deleteLessonDelete}</button>
      {/if}
    {/snippet}

    {#if loadError}
      <FormStatus
        message={loadError}
        tone="error"
        style="--giu-form-status-padding: var(--space-2) var(--space-3)"
      />
    {/if}

    {#if saveMsg}
      <FormStatus
        message={saveMsg}
        tone={saveSucceeded ? 'success' : 'error'}
        style="--giu-form-status-padding: var(--space-2) var(--space-3)"
      />
    {/if}

    {#if deleteError}
      <FormStatus
        message={deleteError}
        tone="error"
        style="--giu-form-status-padding: var(--space-2) var(--space-3)"
      />
    {/if}

    {#if metadataOptionsError}
      <FormStatus
        message={$messages.editorMetadataSuggestionsUnavailable}
        tone="warning"
        style="--giu-form-status-padding: var(--space-2) var(--space-3)"
      />
    {/if}

    <div class="meta-grid">
      {#if id}
        <label>
          <FieldLabel label="ID" />
          <input
            value={lessonId}
            readonly
          />
        </label>
      {/if}

      <label>
        <FieldLabel label={$messages.fieldTopic} />
        <input
          bind:value={topic}
          list="known-topics"
          placeholder={$messages.editorTopicPlaceholder}
          oninput={invalidateSimilarity}
        />
        <datalist id="known-topics">
          {#each metadataOptions.topics as option}
            <option value={option.value}>{option.value} ({option.count})</option>
          {/each}
        </datalist>
        {#if topic.trim() && !metadataOptions.topics.some((option) => normalized(option.value) === normalized(topic))}
          <span class="new-value">{$messages.editorUseNewTopic}: {topic.trim()}</span>
        {/if}
      </label>

      <label>
        <FieldLabel label={$messages.fieldSource} />
        <input
          bind:value={source}
          list="known-sources"
          placeholder={$messages.editorSourcePlaceholder}
          oninput={invalidateSimilarity}
        />
        <datalist id="known-sources">
          {#each metadataOptions.sources as option}
            <option value={option.value}>{option.value} ({option.count})</option>
          {/each}
        </datalist>
      </label>

      <label>
        <FieldLabel label={$messages.fieldImportance} />
        <select bind:value={importance} onchange={invalidateSimilarity} aria-label={$messages.fieldImportance}>
          <option value={1}>1 {$messages.editorImportanceLow}</option>
          <option value={2}>2</option>
          <option value={3}>3 {$messages.editorImportanceNormal}</option>
          <option value={4}>4</option>
          <option value={5}>5 {$messages.editorImportanceHigh}</option>
        </select>
      </label>

      <label>
        <FieldLabel label={$messages.editorLifecycle} />
        <select
          bind:value={lifecycle}
          aria-label={$messages.editorLifecycle}
        >
          <option value="active">{$messages.lifecycleActive}</option>
          <option value="review-needed">{$messages.lifecycleReviewNeeded}</option>
          <option value="deprecated">{$messages.lifecycleDeprecated}</option>
          <option value="archived">{$messages.lifecycleArchived}</option>
        </select>
      </label>

      <label>
        <FieldLabel label={$messages.fieldDate} />
        <input
          bind:value={date}
          oninput={invalidateSimilarity}
        />
      </label>

      <label class="wide">
        <FieldLabel label={$messages.editorSupersededBy} />
        <input
          bind:value={supersededBy}
          placeholder={$messages.editorSupersededByPlaceholder}
          autocomplete="off"
        />
        <span class="field-help">
          {$messages.editorSupersededByHelp}
        </span>
      </label>

      <label>
        <FieldLabel label={$messages.fieldTags} />
        <div class="tag-input">
          {#each tags as tag, index}
            <span class="tag-chip">{tag}<button type="button" aria-label={`${$messages.editorRemoveTag}: ${tag}`} onclick={() => removeTag(index)}>×</button></span>
          {/each}
          <input
            bind:value={tagDraft}
            list="known-tags"
            placeholder={$messages.editorTagsPlaceholder}
            onkeydown={onTagKeydown}
          />
          <button type="button" class="add-tag" onclick={() => addTag()}>{$messages.editorAddTag}</button>
        </div>
        <datalist id="known-tags">
          {#each metadataOptions.tags.filter((option) => normalized(option.value) !== normalized(topic)) as option}
            <option value={option.value}>{option.value} ({option.count})</option>
          {/each}
        </datalist>
      </label>

      <label class="wide">
        <FieldLabel label={$messages.fieldTitle} />
        <input
          bind:value={title}
          oninput={invalidateSimilarity}
        />
      </label>
    </div>

    <label class="body-label">
      <FieldLabel label={$messages.editorBodyLabel} />
      <textarea
        rows="16"
        bind:value={body}
        oninput={invalidateSimilarity}
        placeholder={$messages.editorBodyPlaceholder}
      ></textarea>
    </label>

    <details class="advanced-options">
      <summary>{$messages.editorAdvancedOptions}</summary>

      <div class="suggest-controls">
        <label>
          <FieldLabel label={$messages.editorMaximumResults} />
          <input
            type="number"
            min="1"
            max="20"
            bind:value={topK}
            onchange={invalidateSimilarity}
          />
        </label>

        <label>
          <FieldLabel label={$messages.editorMinimumSimilarity} />
          <input
            type="number"
            min="0"
            max="1"
            step="0.01"
            bind:value={minScore}
            onchange={invalidateSimilarity}
          />
        </label>
      </div>
    </details>
  </Panel>

  {#if similarSearched}
    <SimilarPanel
      title={$messages.editorLiveSimilar}
      items={similar}
      meta={similarMeta}
      explain={true}
      loading={similarLoading}
      error={similarError}
      searched={true}
    />
  {/if}

  {#if suggestedTopic()}
    <aside class="topic-suggestion">
      {$messages.editorSuggestedTopic}: <strong>{suggestedTopic()}</strong>
      <button type="button" onclick={() => { topic = suggestedTopic() ?? topic; invalidateSimilarity() }}>
        {$messages.editorApplySuggestion}
      </button>
    </aside>
  {/if}
</div>

<DeleteLessonDialog
  lesson={deleteTarget}
  oncancel={() => { deleteTarget = null }}
  onconfirm={deleteLesson}
/>

<style>
  .editor-layout {
    display: grid;
    grid-template-columns: 1fr;
    gap: 16px;
    align-items: start;
  }

  .meta-grid {
    display: grid;
    grid-template-columns: repeat(
      auto-fit,
      minmax(140px, 1fr)
    );
    gap: 10px;
    margin-bottom: 12px;
  }

  label {
    display: grid;
    gap: 4px;
    color: var(--muted);
    font-size: 0.85rem;
  }

  .wide {
    grid-column: 1 / -1;
  }

  input,
  select,
  textarea {
    box-sizing: border-box;
    width: 100%;
    padding: 8px 10px;
    border: 1px solid var(--border);
    border-radius: 8px;
    color: var(--text);
    background: white;
  }

  .new-value { font-size: 0.75rem; color: var(--muted); }
  .field-help { font-size: 0.75rem; color: var(--muted); }
  .delete-action { border: 1px solid #a22; border-radius: var(--radius-sm); background: var(--color-surface); color: #8b1717; font-weight: 700; padding: 6px 10px; }
  .delete-action:focus-visible { outline: 3px solid var(--accent); outline-offset: 2px; }
  .tag-input { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; }
  .tag-input input { flex: 1 1 120px; width: auto; }
  .tag-chip { display: inline-flex; align-items: center; gap: 4px; border-radius: 999px; background: #f0ebe3; padding: 3px 7px; color: var(--text); }
  .tag-chip button, .add-tag, .topic-suggestion button { border: 0; border-radius: 6px; background: var(--accent); color: white; cursor: pointer; padding: 3px 7px; }
  .tag-chip button { padding: 0 4px; }
  .topic-suggestion { padding: 10px; border: 1px solid var(--border); border-radius: 8px; background: #fffdf9; }

  .body-label {
    margin-top: 8px;
  }

  .advanced-options {
    margin-top: 12px;
  }

  summary {
    cursor: pointer;
    color: var(--muted);
    font-size: 0.85rem;
  }

  .suggest-controls {
    display: flex;
    gap: 12px;
    margin-top: 8px;
  }

  .suggest-controls label {
    min-width: 0;
  }

  @media (max-width: 900px) {
    .editor-layout {
      grid-template-columns: 1fr;
    }

    .suggest-controls {
      flex-wrap: wrap;
    }
  }
</style>
