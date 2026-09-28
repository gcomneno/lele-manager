<script lang="ts">
  import { onMount } from 'svelte'
  import { FormStatus } from 'giadaware-ui-components'
  import { Button } from 'giadaware-ui-components/studio'
  import {
    api,
    type FactualVerificationAssessment,
    type FactualVerificationOutcome,
  } from '../lib/api'
  import { messages } from '../lib/i18n'

  type Props = {
    lessonId: string
  }

  let { lessonId }: Props = $props()

  let assessments = $state<FactualVerificationAssessment[]>([])
  let approved = $state(false)
  let loading = $state(true)
  let verifying = $state(false)
  let error = $state('')

  function outcomeLabel(outcome: FactualVerificationOutcome): string {
    switch (outcome) {
      case 'supported':
        return $messages.factualVerificationSupported
      case 'contradicted':
        return $messages.factualVerificationContradicted
      case 'outdated':
        return $messages.factualVerificationOutdated
      case 'insufficient-evidence':
        return $messages.factualVerificationInsufficient
      case 'not-verifiable':
        return $messages.factualVerificationNotVerifiable
    }
  }

  async function loadVerification() {
    loading = true
    error = ''

    try {
      const result = await api.factualVerification(lessonId)
      assessments = result.assessments
    } catch (e) {
      error = e instanceof Error ? e.message : String(e)
    } finally {
      loading = false
    }
  }

  async function verify() {
    if (!approved || verifying) return

    verifying = true
    error = ''

    try {
      const result = await api.verifyFactualClaims(lessonId)
      assessments = result.assessments
      approved = false
    } catch (e) {
      error = e instanceof Error ? e.message : String(e)
    } finally {
      verifying = false
    }
  }

  onMount(loadVerification)
</script>

<section
  class="factual-verification"
  data-testid="factual-verification"
  aria-labelledby="factual-verification-title"
>
  <div class="verification-heading">
    <div>
      <strong id="factual-verification-title">
        {$messages.factualVerificationTitle}
      </strong>
      <p class="meta">
        {$messages.factualVerificationAdvisory}
      </p>
    </div>
  </div>

  <p class="meta verification-local">
    {$messages.factualVerificationLocalRead}
  </p>

  <label class="verification-consent">
    <input
      type="checkbox"
      bind:checked={approved}
      disabled={verifying}
    />
    <span>{$messages.factualVerificationConsent}</span>
  </label>

  <div>
    <Button
      type="button"
      variant="secondary"
      size="compact"
      class="lele-secondary-button"
      disabled={!approved || verifying}
      onclick={verify}
    >
      {verifying
        ? $messages.factualVerificationVerifying
        : $messages.factualVerificationVerify}
    </Button>
  </div>

  {#if error}
    <FormStatus
      message={error}
      tone="error"
      style="--giu-form-status-padding: var(--space-2) var(--space-3)"
    />
  {/if}

  {#if loading}
    <p class="meta">{$messages.commonLoading}</p>
  {:else if assessments.length === 0}
    <p class="meta">
      {$messages.factualVerificationEmpty}
    </p>
  {:else}
    <div class="verification-results">
      {#each assessments as assessment (assessment.claim.claim_id)}
        <article class="verification-result">
          <div class="verification-result-heading">
            <strong>{outcomeLabel(assessment.outcome)}</strong>

            {#if assessment.stale}
              <span class="verification-stale">
                {$messages.factualVerificationStale}
              </span>
            {/if}
          </div>

          <p>{assessment.claim.text}</p>

          <p class="meta">
            {assessment.explanation}
          </p>

          <p class="meta">
            {$messages.factualVerificationCheckedAt}:
            {assessment.checked_at}
          </p>

          {#if assessment.evidence.length}
            <div class="verification-evidence">
              <strong>
                {$messages.factualVerificationEvidence}
              </strong>

              <ul>
                {#each assessment.evidence as evidence (evidence.source_id)}
                  <li>
                    <a
                      href={evidence.source_uri}
                      target="_blank"
                      rel="noreferrer"
                    >
                      {evidence.source_title}
                    </a>
                    <div class="meta">
                      {evidence.excerpt}
                    </div>
                  </li>
                {/each}
              </ul>
            </div>
          {/if}
        </article>
      {/each}
    </div>
  {/if}
</section>

<style>
  .factual-verification {
    display: grid;
    gap: var(--space-3);
    margin-block: var(--space-4);
    padding: var(--space-3);
    border: 1px solid var(--border);
    border-radius: var(--radius-md);
  }

  .verification-heading,
  .verification-result-heading {
    display: flex;
    align-items: start;
    justify-content: space-between;
    gap: var(--space-2);
  }

  .verification-heading p,
  .verification-local,
  .verification-result p {
    margin: 0;
  }

  .verification-consent {
    display: flex;
    align-items: start;
    gap: var(--space-2);
    max-width: 70ch;
  }

  .verification-consent input {
    margin-top: 0.2rem;
  }

  .verification-results {
    display: grid;
    gap: var(--space-3);
  }

  .verification-result {
    display: grid;
    gap: var(--space-2);
    padding-top: var(--space-3);
    border-top: 1px solid var(--border);
  }

  .verification-stale {
    font-size: var(--font-size-sm);
    font-weight: 600;
  }

  .verification-evidence ul {
    margin-bottom: 0;
  }
</style>
