<script lang="ts">
  import { onMount } from 'svelte'
  import { messages } from '../lib/i18n'
  import { navigate, type Route } from '../lib/router'

  const DOCUMENTATION_URL =
    'https://github.com/gcomneno/lele-manager/blob/main/docs/gui-user-guide.md'
  const SUPPORT_URL =
    'https://github.com/gcomneno/lele-manager/issues/new?template=bug_report.yml'

  let open = $state(false)
  let trigger = $state<HTMLButtonElement>()

  function close() {
    open = false
    trigger?.focus()
  }

  function navigateAndClose(route: Route) {
    navigate(route)
    close()
  }

  onMount(() => {
    const onKeydown = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && open) {
        event.preventDefault()
        close()
      }
    }

    window.addEventListener('keydown', onKeydown)
    return () => window.removeEventListener('keydown', onKeydown)
  })
</script>

<div class="help" role="group" aria-label={$messages.help}>
  <button
    bind:this={trigger}
    class="help-trigger"
    type="button"
    aria-expanded={open}
    aria-controls="header-help-menu"
    data-testid="header-help-trigger"
    onclick={() => { open = !open }}
  >
    <span aria-hidden="true">?</span>
    <span>{$messages.help}</span>
  </button>
  {#if open}
    <div id="header-help-menu" class="help-menu" role="region" aria-label={$messages.help}>
      <a href={DOCUMENTATION_URL} target="_blank" rel="noreferrer">
        {$messages.helpUserGuide}
      </a>
      <button type="button" onclick={() => navigateAndClose({ view: 'settings' })}>
        {$messages.navSettings}
      </button>
      <a href={SUPPORT_URL} target="_blank" rel="noreferrer">
        {$messages.helpReportProblem}
      </a>
      <button type="button" onclick={() => navigateAndClose({ view: 'about' })}>
        {$messages.navAbout}
      </button>
      <p>{$messages.helpShortcut}</p>
    </div>
  {/if}
</div>

<style>
  .help { position: relative; }
  .help-trigger,
  .help-menu button,
  .help-menu a {
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
    background: var(--color-surface);
    color: var(--color-text);
  }

  .help-trigger {
    display: inline-flex;
    min-height: 36px;
    align-items: center;
    gap: 6px;
    padding: 6px 9px;
  }

  .help-trigger > span:first-child {
    display: inline-flex;
    width: 16px;
    height: 16px;
    align-items: center;
    justify-content: center;
    border-radius: 50%;
    background: var(--color-brand-700);
    color: var(--color-text-inverse);
    font-weight: 700;
  }

  .help-menu {
    position: absolute;
    right: 0;
    z-index: 4;
    display: grid;
    width: max-content;
    min-width: 210px;
    gap: 4px;
    margin-top: 6px;
    padding: 8px;
    border: 1px solid var(--border);
    border-radius: var(--radius-md);
    background: var(--color-surface);
    box-shadow: var(--elevation-2);
  }

  .help-menu button,
  .help-menu a {
    min-height: 34px;
    padding: 6px 8px;
    text-align: left;
    text-decoration: none;
  }

  .help-menu button:hover,
  .help-menu a:hover { background: var(--color-surface-subtle); }
  .help-menu p { margin: 4px 4px 0; color: var(--color-text-muted); font-size: var(--font-size-xs); }

  @media (max-width: 800px) {
    .help-trigger > span:last-child { display: none; }
    .help-trigger { padding: 6px 8px; }
  }
</style>
