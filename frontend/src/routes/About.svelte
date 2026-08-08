<script lang="ts">
  import { onMount } from 'svelte'
  import { api } from '../lib/api'
  import { FormStatus } from 'giadaware-ui-components'
  import {
    Panel,
    Surface,
  } from 'giadaware-ui-components/studio'
  import { formatMessage, messages } from '../lib/i18n'

  let about = $state<Awaited<ReturnType<typeof api.about>> | null>(null)
  let loading = $state(true)
  let error = $state('')

  async function load() {
    loading = true
    error = ''
    try {
      about = await api.about()
    } catch (err) {
      about = null
      error = err instanceof Error ? err.message : String(err)
    } finally {
      loading = false
    }
  }

  onMount(load)
</script>

<Panel title={$messages.aboutTitle} class="about">
  {#if loading}
    <p class="meta">{$messages.aboutLoading}</p>
  {:else if error}
    <FormStatus
      message={formatMessage($messages.aboutError, { error })}
      tone="error"
    />
  {:else if about}
    <div class="identity">
      <img src="/app/brand/lele-manager-mark.svg" alt="" aria-hidden="true" />
      <div>
        <h2>{about.product_name}</h2>
        <p>{about.tagline}</p>
        <p class="meta">{about.attribution}</p>
      </div>
    </div>

    <div class="about-grid">
      <Surface>
        <span class="label">{$messages.aboutVersion}</span>
        <strong>{about.version}</strong>
      </Surface>

      <Surface>
        <span class="label">{$messages.aboutLicense}</span>
        <strong>{about.license_id}</strong>
        <p>{about.license_summary}</p>
        <a href={about.license_url}>
          {$messages.aboutLicenseText}
        </a>
      </Surface>

      <Surface>
        <span class="label">{$messages.aboutRuntime}</span>
        <strong>{about.platform_system} {about.platform_release}</strong>
        <p>Python {about.python_version}</p>
      </Surface>
    </div>

    <div class="local-first">
      <Surface>
        <span class="label">{$messages.aboutLocalFirst}</span>
        <p>{about.local_first_statement}</p>
      </Surface>
    </div>

    <nav class="support-links" aria-label={$messages.aboutTitle}>
      <a href={about.repository_url} target="_blank" rel="noreferrer">
        {$messages.aboutRepository}
      </a>
      <a href={about.issue_tracker_url} target="_blank" rel="noreferrer">
        {$messages.aboutIssues}
      </a>
      <a href={about.releases_url} target="_blank" rel="noreferrer">
        {$messages.aboutReleases}
      </a>
      <a href={about.changelog_url} target="_blank" rel="noreferrer">
        {$messages.aboutChangelog}
      </a>
      <a href={about.documentation_url} target="_blank" rel="noreferrer">
        {$messages.aboutDocumentation}
      </a>
    </nav>
  {/if}
</Panel>

<style>
  .identity {
    display: flex;
    gap: var(--space-4);
    align-items: center;
    margin-bottom: var(--space-5);
  }

  .identity img {
    width: 64px;
    height: 64px;
  }

  .identity h2,
  .identity p {
    margin: 0;
  }

  .identity p + p {
    margin-top: var(--space-1);
  }

  .about-grid {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: var(--space-3);
  }

  .about-grid :global(.giu-surface),
  .local-first :global(.giu-surface) {
    display: grid;
    gap: var(--space-2);
  }

  .local-first {
    margin-top: var(--space-3);
  }

  .about-grid p,
  .local-first p {
    margin: 0;
  }

  .support-links {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-3);
    margin-top: var(--space-4);
  }

  @media (max-width: 800px) {
    .about-grid {
      grid-template-columns: 1fr;
    }
  }
</style>
