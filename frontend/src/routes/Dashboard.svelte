<script lang="ts">
  import { onMount } from 'svelte'
  import { FormStatus } from 'giadaware-ui-components'
  import {
    Button,
    FormActions,
    Panel,
    Surface,
  } from 'giadaware-ui-components/studio'
  import {
    api,
    type DashboardSummaryResponse,
  } from '../lib/api'
  import { navigate } from '../lib/router'
  import { formatMessage, messages } from '../lib/i18n'

  let summary = $state<DashboardSummaryResponse | null>(null)
  let loading = $state(true)
  let error = $state('')

  type DashboardState =
    | 'fresh'
    | 'empty'
    | 'partial'
    | 'ready'

  function dashboardState(
    value: DashboardSummaryResponse,
  ): DashboardState {
    if (!value.vault_exists) {
      return 'fresh'
    }

    if ((value.vault_markdown_files ?? 0) === 0) {
      return 'empty'
    }

    if (
      !value.projection_exists ||
      !value.model_exists
    ) {
      return 'partial'
    }

    return 'ready'
  }

  function titleFor(state: DashboardState): string {
    switch (state) {
      case 'fresh':
        return $messages.dashboardFreshTitle
      case 'empty':
        return $messages.dashboardEmptyTitle
      case 'partial':
        return $messages.dashboardPartialTitle
      case 'ready':
        return $messages.dashboardReadyTitle
    }
  }

  function descriptionFor(state: DashboardState): string {
    switch (state) {
      case 'fresh':
        return $messages.dashboardFreshDescription
      case 'empty':
        return $messages.dashboardEmptyDescription
      case 'partial':
        return $messages.dashboardPartialDescription
      case 'ready':
        return $messages.dashboardReadyDescription
    }
  }

  async function load() {
    loading = true
    error = ''

    try {
      summary = await api.dashboardSummary()
    } catch (e) {
      summary = null
      error = e instanceof Error ? e.message : String(e)
    } finally {
      loading = false
    }
  }

  onMount(load)
</script>

<Panel title={$messages.dashboardTitle} class="dashboard">
  <p class="dashboard-intro">
    {$messages.dashboardIntro}
  </p>

  {#if loading}
    <p class="meta" aria-live="polite">
      {$messages.dashboardLoading}
    </p>
  {:else if error}
    <FormStatus
      message={formatMessage(
        $messages.dashboardError,
        { error },
      )}
      tone="error"
      style="--giu-form-status-padding: var(--space-2) var(--space-3)"
    />

    <div class="dashboard-actions">
      <FormActions>
      <Button
        variant="secondary"
        size="compact"
        class="lele-secondary-button"
        onclick={load}
      >
        {$messages.dashboardRetry}
      </Button>

      <Button
        variant="secondary"
        size="compact"
        class="lele-secondary-button"
        onclick={() => navigate({ view: 'ops' })}
      >
        {$messages.dashboardOpenSystem}
      </Button>
    </FormActions>
    </div>
  {:else if summary}
    {@const state = dashboardState(summary)}

    <section
      class="readiness"
      aria-label={$messages.dashboardReadiness}
    >
      <Surface>
      <span
        class="readiness-state"
        class:is-ready={state === 'ready'}
        class:is-warning={state !== 'ready'}
      >
        {titleFor(state)}
      </span>

      <p>{descriptionFor(state)}</p>

      {#if state === 'fresh'}
        <p class="ownership-note">
          {$messages.dashboardOwnership}
        </p>

        <div class="dashboard-actions">
      <FormActions>
          <Button
            size="compact"
            onclick={() => navigate({ view: 'vault' })}
          >
            {$messages.dashboardOpenVault}
          </Button>

          <Button
            variant="secondary"
            size="compact"
            class="lele-secondary-button"
            onclick={() => navigate({ view: 'ops' })}
          >
            {$messages.dashboardOpenSystem}
          </Button>
        </FormActions>
    </div>
      {:else if state === 'empty'}
        <p class="ownership-note">
          {$messages.dashboardOwnership}
        </p>

        <div class="dashboard-actions">
      <FormActions>
          <Button
            size="compact"
            onclick={() => navigate({ view: 'editor' })}
          >
            {$messages.navNewLele}
          </Button>

          <Button
            variant="secondary"
            size="compact"
            class="lele-secondary-button"
            onclick={() => navigate({ view: 'tritalele' })}
          >
            {$messages.navCollection}
          </Button>
        </FormActions>
    </div>
      {:else if state === 'partial'}
        <div class="dashboard-actions">
      <FormActions>
          <Button
            size="compact"
            onclick={() => navigate({ view: 'ops' })}
          >
            {$messages.dashboardOpenSystem}
          </Button>

          <Button
            variant="secondary"
            size="compact"
            class="lele-secondary-button"
            onclick={() => navigate({ view: 'browse' })}
          >
            {$messages.navBrowse}
          </Button>
        </FormActions>
    </div>
      {:else}
        <div class="dashboard-actions">
      <FormActions>
          <Button
            size="compact"
            onclick={() => navigate({ view: 'editor' })}
          >
            {$messages.navNewLele}
          </Button>

          <Button
            variant="secondary"
            size="compact"
            class="lele-secondary-button"
            onclick={() => navigate({ view: 'browse' })}
          >
            {$messages.navBrowse}
          </Button>

          <Button
            variant="secondary"
            size="compact"
            class="lele-secondary-button"
            onclick={() => navigate({ view: 'tritalele' })}
          >
            {$messages.navCollection}
          </Button>
        </FormActions>
    </div>
      {/if}
      </Surface>
    </section>

    <section
      class="summary-grid"
      aria-label={$messages.dashboardSummary}
    >
      <div class="summary-card">
        <Surface>
        <span class="label">
          {$messages.dashboardVault}
        </span>
        <strong>
          {summary.vault_exists
            ? $messages.dashboardAvailable
            : $messages.dashboardMissing}
        </strong>
        {#if summary.vault_markdown_files !== null}
          <span class="meta">
            {formatMessage(
              $messages.dashboardMarkdownFiles,
              { count: summary.vault_markdown_files },
            )}
          </span>
        {/if}
      </Surface>
      </div>

      <div class="summary-card">

        <Surface>
        <span class="label">
          {$messages.dashboardProjection}
        </span>
        <strong>
          {summary.projection_exists
            ? $messages.dashboardAvailable
            : $messages.dashboardMissing}
        </strong>
      </Surface>

      </div>

      <div class="summary-card">

        <Surface>
        <span class="label">
          {$messages.dashboardModel}
        </span>
        <strong>
          {summary.model_exists
            ? $messages.dashboardAvailable
            : $messages.dashboardMissing}
        </strong>
      </Surface>

      </div>

      <div class="summary-card">

        <Surface>
        <span class="label">
          {$messages.dashboardApi}
        </span>
        <strong>{summary.health_status}</strong>
      </Surface>

      </div>
    </section>

    {#if summary.stats}
      <section
        class="knowledge-summary"
        aria-labelledby="dashboard-knowledge-title"
      >
        <div class="section-heading">
          <div>
            <h2 id="dashboard-knowledge-title">
              {$messages.dashboardKnowledgeTitle}
            </h2>
            <p class="meta">
              {$messages.dashboardKnowledgeDescription}
            </p>
          </div>

          <Button
            variant="secondary"
            size="compact"
            class="lele-secondary-button"
            onclick={() => navigate({ view: 'stats' })}
          >
            {$messages.dashboardOpenStatistics}
          </Button>
        </div>

        <div class="knowledge-grid">
          <div class="summary-card">
            <Surface>
            <span class="label">LeLe</span>
            <strong>{summary.stats.n_lessons}</strong>
          </Surface>
          </div>

          <div class="summary-card">

            <Surface>
            <span class="label">Topic</span>
            <strong>{summary.stats.n_topics}</strong>
          </Surface>

          </div>

          <div class="summary-card">

            <Surface>
            <span class="label">
              {$messages.statsUniqueTags}
            </span>
            <strong>{summary.stats.n_unique_tags}</strong>
          </Surface>

          </div>
        </div>
      </section>
    {/if}

    {#if summary.candidates}
      <section
        class="candidate-summary"
        aria-labelledby="dashboard-candidates-title"
      >
        <div class="section-heading">
          <div>
            <h2 id="dashboard-candidates-title">
              {$messages.dashboardCandidatesTitle}
            </h2>
            <p class="meta">
              {$messages.dashboardCandidatesDescription}
            </p>
          </div>

          <Button
            variant="secondary"
            size="compact"
            class="lele-secondary-button"
            onclick={() => navigate({ view: 'tritalele' })}
          >
            {$messages.dashboardOpenCollection}
          </Button>
        </div>

        <div class="candidate-grid">
          <div class="summary-card">
            <Surface>
            <span class="label">
              {$messages.dashboardCandidateStaged}
            </span>
            <strong>{summary.candidates.staged}</strong>
          </Surface>
          </div>

          <div class="summary-card">

            <Surface>
            <span class="label">
              {$messages.dashboardCandidateReview}
            </span>
            <strong>{summary.candidates.in_review}</strong>
          </Surface>

          </div>
        </div>
      </section>
    {/if}
  {/if}
</Panel>

<style>
  .dashboard-intro,
  .ownership-note,
  .readiness p {
    max-width: 760px;
  }

  .dashboard-intro {
    margin: 0 0 16px;
    color: var(--muted);
  }

  .readiness {
    display: grid;
    gap: 10px;
    margin-bottom: 16px;
  }

  .readiness p {
    margin: 0;
  }

  .readiness-state {
    width: fit-content;
    font-weight: 700;
  }

  .readiness-state::before {
    content: '';
    display: inline-block;
    width: 8px;
    height: 8px;
    margin-right: 7px;
    border-radius: 999px;
    background: currentColor;
    vertical-align: 1px;
  }

  .is-ready {
    color: var(--ok);
  }

  .is-warning {
    color: var(--warn);
  }

  .ownership-note {
    color: var(--muted);
    font-size: 0.9rem;
  }

  .dashboard-actions {
    margin-top: 2px;
  }

  .summary-grid,
  .knowledge-grid,
  .candidate-grid {
    display: grid;
    gap: 12px;
  }

  .summary-grid {
    grid-template-columns: repeat(
      4,
      minmax(0, 1fr)
    );
    margin-bottom: 22px;
  }

  .knowledge-grid {
    grid-template-columns: repeat(
      3,
      minmax(0, 1fr)
    );
  }

  .candidate-grid {
    grid-template-columns: repeat(
      2,
      minmax(0, 1fr)
    );
  }

  .summary-card {
    display: grid;
    gap: 4px;
    min-width: 0;
  }

  .summary-card strong {
    font-size: 1.05rem;
  }

  .label {
    color: var(--muted);
    font-size: 0.8rem;
  }

  .knowledge-summary,
  .candidate-summary {
    display: grid;
    gap: 12px;
    margin-top: 22px;
  }

  .section-heading {
    display: flex;
    align-items: end;
    justify-content: space-between;
    gap: 12px;
  }

  .section-heading h2,
  .section-heading p {
    margin: 0;
  }

  .section-heading h2 {
    margin-bottom: 3px;
    font-size: 1rem;
  }

  @media (max-width: 900px) {
    .summary-grid {
      grid-template-columns: repeat(
        2,
        minmax(0, 1fr)
      );
    }
  }

  @media (max-width: 620px) {
    .summary-grid,
    .knowledge-grid,
    .candidate-grid {
      grid-template-columns: 1fr;
    }

    .section-heading {
      align-items: start;
      flex-direction: column;
    }
  }
</style>
