<script lang="ts">
  import { api, type Lesson, type SimilarItem, type SimilarMeta } from '../lib/api'
  import { stripFrontmatter } from '../lib/markdown'
  import { navigate } from '../lib/router'
  import SimilarPanel from '../components/SimilarPanel.svelte'

  interface Props {
    id?: string
  }

  let { id }: Props = $props()

  let topic = $state('python')
  let source = $state('note')
  let importance = $state(3)
  let date = $state(new Date().toISOString().slice(0, 10))
  let tags = $state('')
  let title = $state('')
  let body = $state('')
  let lessonId = $state('')

  let similar = $state<SimilarItem[]>([])
  let similarMeta = $state<SimilarMeta | null>(null)
  let similarLoading = $state(false)
  let similarError = $state('')
  let loadError = $state('')
  let saving = $state(false)
  let saveMsg = $state('')

  let topK = $state(5)
  let minScore = $state(0.1)

  let debounceTimer: ReturnType<typeof setTimeout> | undefined

  function composeText(): string {
    const tagList = tags
      .split(',')
      .map((t) => t.trim())
      .filter(Boolean)
    const fm = [
      '---',
      lessonId ? `id: ${lessonId}` : 'id: (auto)',
      `topic: ${topic}`,
      `source: ${source}`,
      `importance: ${importance}`,
      `date: ${date}`,
      tagList.length ? `tags: [${tagList.join(', ')}]` : 'tags: []',
      title ? `title: "${title.replace(/"/g, '\\"')}"` : '',
      '---',
      '',
      body,
    ]
      .filter((line) => line !== '')
      .join('\n')
    return fm
  }

  async function fetchSuggest() {
    const text = composeText().trim()
    if (text.length < 12) {
      similar = []
      return
    }
    similarLoading = true
    similarError = ''
    try {
      const resp = await api.editorSuggest(text, topK, minScore, true)
      similar = resp.results
      similarMeta = resp.meta ?? null
    } catch (e) {
      similar = []
      similarError = e instanceof Error ? e.message : String(e)
    } finally {
      similarLoading = false
    }
  }

  function scheduleSuggest() {
    clearTimeout(debounceTimer)
    debounceTimer = setTimeout(fetchSuggest, 500)
  }

  async function loadExisting(lessonIdValue: string) {
    loadError = ''
    try {
      const lesson: Lesson = await api.getLesson(lessonIdValue)
      lessonId = lesson.id
      topic = lesson.topic ?? ''
      source = lesson.source ?? ''
      importance = lesson.importance ?? 3
      date = lesson.date ?? date
      title = lesson.title ?? ''
      tags = (lesson.tags ?? []).join(', ')
      const parsed = stripFrontmatter(lesson.text ?? '')
      body = parsed.body || lesson.text || ''
      scheduleSuggest()
    } catch (e) {
      loadError = e instanceof Error ? e.message : String(e)
    }
  }

  function buildPayload() {
    const tagList = tags
      .split(',')
      .map((t) => t.trim())
      .filter(Boolean)
    return {
      text: body,
      topic: topic.trim(),
      source: source.trim() || 'note',
      importance: Number(importance) || 3,
      tags: tagList,
      date: date || null,
      title: title.trim() || null,
    }
  }

  async function save() {
    if (!body.trim()) {
      saveMsg = 'Il body non può essere vuoto.'
      return
    }
    if (!topic.trim()) {
      saveMsg = 'Topic obbligatorio.'
      return
    }

    saving = true
    saveMsg = ''
    try {
      const payload = buildPayload()
      const targetId = (id || lessonId || '').trim()
      let lesson: Lesson
      if (targetId) {
        lesson = await api.updateLesson(targetId, payload)
      } else {
        lesson = await api.createVaultLesson({
          ...payload,
          id: lessonId.trim() || null,
        })
      }
      saveMsg = `Salvato nel vault: ${lesson.id}`
      navigate({ view: 'detail', id: lesson.id })
    } catch (e) {
      saveMsg = e instanceof Error ? e.message : String(e)
    } finally {
      saving = false
    }
  }

  $effect(() => {
    if (id) {
      loadExisting(id)
    } else {
      scheduleSuggest()
    }
  })
</script>

<div class="editor-layout">
  <section class="card editor-pane">
    <div class="head">
      <h2>{id ? 'Modifica LeLe' : 'Nuova LeLe'}</h2>
      <button class="btn btn-primary" onclick={save} disabled={saving}>
        {saving ? 'Salvataggio…' : 'Salva nel vault'}
      </button>
    </div>

    {#if loadError}
      <p class="error">{loadError}</p>
    {/if}
    {#if saveMsg}
      <p class={saveMsg.startsWith('Salvato') ? 'ok' : 'error'}>{saveMsg}</p>
    {/if}

    <div class="meta-grid">
      <label>ID <input bind:value={lessonId} placeholder="auto (topic/data.slug)" readonly={!!id} /></label>
      <label>Topic <input bind:value={topic} oninput={scheduleSuggest} /></label>
      <label>Source <input bind:value={source} oninput={scheduleSuggest} /></label>
      <label>Importance <input type="number" min="1" max="5" bind:value={importance} oninput={scheduleSuggest} /></label>
      <label>Date <input bind:value={date} oninput={scheduleSuggest} /></label>
      <label>Tags <input bind:value={tags} placeholder="python, pytest" oninput={scheduleSuggest} /></label>
      <label class="wide">Title <input bind:value={title} oninput={scheduleSuggest} /></label>
    </div>

    <label class="body-label">
      Body (Markdown)
      <textarea
        rows="16"
        bind:value={body}
        oninput={scheduleSuggest}
        placeholder="Scrivi la lesson learned…"
      ></textarea>
    </label>

    <div class="suggest-controls">
      <label>top_k <input type="number" min="1" max="20" bind:value={topK} onchange={fetchSuggest} /></label>
      <label>min_score <input type="number" min="0" max="1" step="0.01" bind:value={minScore} onchange={fetchSuggest} /></label>
    </div>
  </section>

  <SimilarPanel
    title="Simili live"
    items={similar}
    meta={similarMeta}
    explain={true}
    loading={similarLoading}
    error={similarError}
  />
</div>

<style>
  .editor-layout {
    display: grid;
    grid-template-columns: 1.3fr 0.7fr;
    gap: 16px;
    align-items: start;
  }

  .head {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 12px;
  }

  h2 {
    margin: 0;
  }

  .meta-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
    gap: 10px;
    margin-bottom: 12px;
  }

  label {
    display: grid;
    gap: 4px;
    font-size: 0.85rem;
    color: var(--muted);
  }

  .wide {
    grid-column: 1 / -1;
  }

  input,
  textarea {
    padding: 8px 10px;
    border: 1px solid var(--border);
    border-radius: 8px;
    background: white;
    color: var(--text);
    width: 100%;
  }

  .body-label {
    margin-top: 8px;
  }

  .suggest-controls {
    display: flex;
    gap: 12px;
    margin-top: 10px;
  }

  @media (max-width: 900px) {
    .editor-layout {
      grid-template-columns: 1fr;
    }
  }
</style>
