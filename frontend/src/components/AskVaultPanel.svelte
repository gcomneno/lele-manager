<script lang="ts">
  import { FormStatus } from 'giadaware-ui-components'
  import {
    Button,
    FieldLabel,
  } from 'giadaware-ui-components/studio'
  import {
    api,
    type AssistantContextRequest,
    type AskVaultResponse,
    type LessonLifecycleState,
  } from '../lib/api'
  import { formatMessage, messages } from '../lib/i18n'

  type Props = {
    request: AssistantContextRequest
    count: number
    testId?: string
  }

  let {
    request,
    count,
    testId = 'ask-vault-panel',
  }: Props = $props()

  let question = $state('')
  let busy = $state(false)
  let result = $state<AskVaultResponse | null>(null)
  let error = $state('')

  function lifecycleLabel(
    lifecycle: LessonLifecycleState,
  ): string {
    switch (lifecycle) {
      case 'review-needed':
        return $messages.lifecycleReviewNeeded
      case 'deprecated':
        return $messages.lifecycleDeprecated
      case 'archived':
        return $messages.lifecycleArchived
      case 'active':
      default:
        return $messages.lifecycleActive
    }
  }

  async function askVault(event: SubmitEvent) {
    event.preventDefault()

    const normalized = question.trim()
    if (!normalized || busy) return

    busy = true
    result = null
    error = ''

    try {
      result = await api.askVault({
        ...request,
        question: normalized,
      })
    } catch (e) {
      error = e instanceof Error ? e.message : String(e)
    } finally {
      busy = false
    }
  }
</script>

<section
  class="ask-vault-panel"
  data-testid={testId}
  aria-label={$messages.askVaultTitle}
>
  <div class="ask-vault-heading">
    <div>
      <h3>{$messages.askVaultTitle}</h3>
      <p class="meta">
        {formatMessage(
          $messages.askVaultScopeCount,
          { count },
        )}
      </p>
    </div>
  </div>

  <p class="meta">
    {$messages.askVaultDescription}
  </p>

  <form
    class="ask-vault-form"
    onsubmit={askVault}
  >
    <label>
      <FieldLabel label={$messages.askVaultQuestionLabel} />
      <textarea
        bind:value={question}
        rows="3"
        placeholder={$messages.askVaultQuestionPlaceholder}
        disabled={busy}
      ></textarea>
    </label>

    <Button
      type="submit"
      variant="secondary"
      size="compact"
      class="lele-secondary-button"
      disabled={busy || !question.trim()}
    >
      {busy
        ? $messages.askVaultAsking
        : $messages.askVaultAsk}
    </Button>
  </form>

  <p class="meta">
    {$messages.askVaultGeneratedNotice}
  </p>

  {#if error}
    <FormStatus
      message={error}
      tone="error"
      style="--giu-form-status-padding: var(--space-2) var(--space-3)"
    />
  {/if}

  {#if result}
    <div
      class="ask-vault-result"
      data-testid={`${testId}-result`}
    >
      <strong>
        {result.outcome === 'answered'
          ? $messages.askVaultGeneratedHeading
          : $messages.askVaultInsufficientHeading}
      </strong>

      <p>{result.answer}</p>

      {#if result.outcome === 'answered'}
        <div class="ask-vault-citations">
          <strong>{$messages.askVaultSourcesHeading}</strong>

          {#if result.citations.length === 0}
            <p class="meta">
              {$messages.askVaultNoSources}
            </p>
          {:else}
            <ul>
              {#each result.citations as citation (citation.lesson_id)}
                <li data-testid={`ask-vault-citation-${citation.lesson_id}`}>
                  <div>
                    <strong>
                      {citation.title?.trim() || citation.lesson_id}
                    </strong>
                    <code>{citation.lesson_id}</code>
                  </div>

                  <div class="citation-meta meta">
                    <span>
                      {lifecycleLabel(citation.lifecycle)}
                    </span>

                    {#if citation.superseded_by}
                      <span>
                        {formatMessage(
                          $messages.askVaultSupersededBy,
                          { id: citation.superseded_by },
                        )}
                      </span>
                    {/if}
                  </div>
                </li>
              {/each}
            </ul>
          {/if}
        </div>
      {/if}
    </div>
  {/if}
</section>

<style>
  .ask-vault-panel {
    display: grid;
    gap: var(--space-3);
  }

  .ask-vault-heading h3,
  .ask-vault-heading p,
  .ask-vault-result p {
    margin: 0;
  }

  .ask-vault-form {
    display: grid;
    gap: var(--space-2);
  }

  .ask-vault-form label {
    display: grid;
    gap: var(--space-1);
  }

  .ask-vault-form textarea {
    width: 100%;
    box-sizing: border-box;
    resize: vertical;
  }

  .ask-vault-result,
  .ask-vault-citations {
    display: grid;
    gap: var(--space-2);
  }

  .ask-vault-citations ul {
    display: grid;
    gap: var(--space-2);
    margin: 0;
    padding-left: var(--space-5);
  }

  .ask-vault-citations li > div {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-2);
  }

  .citation-meta {
    margin-top: var(--space-1);
  }
</style>
