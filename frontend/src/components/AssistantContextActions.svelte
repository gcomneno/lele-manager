<script lang="ts">
  import { FormStatus } from 'giadaware-ui-components'
  import { Button } from 'giadaware-ui-components/studio'
  import {
    api,
    type AssistantContextRequest,
  } from '../lib/api'
  import { formatMessage, messages } from '../lib/i18n'

  type Props = {
    request: AssistantContextRequest
    count: number
    filename: string
    testId?: string
  }

  let {
    request,
    count,
    filename,
    testId = 'assistant-context-actions',
  }: Props = $props()

  let busy = $state(false)
  let notice = $state('')
  let error = $state('')

  function downloadMarkdown(content: string) {
    const blob = new Blob(
      [content],
      { type: 'text/markdown;charset=utf-8' },
    )
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = filename
    anchor.click()
    URL.revokeObjectURL(url)
  }

  async function copyForAssistant() {
    busy = true
    notice = ''
    error = ''

    try {
      const result = await api.assistantContext(request)
      await navigator.clipboard.writeText(result.markdown)
      notice = formatMessage(
        $messages.assistantCopied,
        { count: result.n_lessons },
      )
    } catch (e) {
      error = e instanceof Error ? e.message : String(e)
    } finally {
      busy = false
    }
  }

  async function exportForAssistant() {
    busy = true
    notice = ''
    error = ''

    try {
      const result = await api.assistantContext(request)
      downloadMarkdown(result.markdown)
      notice = formatMessage(
        $messages.assistantExported,
        { count: result.n_lessons },
      )
    } catch (e) {
      error = e instanceof Error ? e.message : String(e)
    } finally {
      busy = false
    }
  }
</script>

<section
  class="assistant-context-actions"
  data-testid={testId}
  aria-label={$messages.assistantActionsLabel}
>
  <p class="assistant-scope meta">
    {formatMessage(
      $messages.assistantScopeCount,
      { count },
    )}
  </p>

  <div class="assistant-buttons">
    <Button
      type="button"
      variant="secondary"
      size="compact"
      class="lele-secondary-button"
      disabled={busy || count === 0}
      onclick={copyForAssistant}
    >
      {busy
        ? $messages.assistantPreparing
        : $messages.assistantCopy}
    </Button>

    <Button
      type="button"
      variant="secondary"
      size="compact"
      class="lele-secondary-button"
      disabled={busy || count === 0}
      onclick={exportForAssistant}
    >
      {$messages.assistantExport}
    </Button>
  </div>

  <p class="assistant-local-only meta">
    {$messages.assistantLocalOnly}
  </p>

  {#if notice}
    <FormStatus
      message={notice}
      tone="success"
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
</section>

<style>
  .assistant-context-actions {
    display: grid;
    gap: var(--space-2);
  }

  .assistant-scope,
  .assistant-local-only {
    margin: 0;
  }

  .assistant-buttons {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-2);
  }
</style>
