<script lang="ts">
  import { navigate, type Route } from '../lib/router'
  import HealthBar from './HealthBar.svelte'

  interface Props {
    route: Route
    children: import('svelte').Snippet
  }

  let { route, children }: Props = $props()

  const links = [
    { view: 'browse' as const, label: 'Esplora', hash: '#/' },
    { view: 'timeline' as const, label: 'Cronologia', hash: '#/timeline' },
    { view: 'stats' as const, label: 'Statistiche', hash: '#/stats' },
    { view: 'editor' as const, label: 'Nuova LeLe', hash: '#/editor' },
    { view: 'tritalele' as const, label: 'Raccolta', hash: '#/tritalele' },
    { view: 'vault' as const, label: 'Vault', hash: '#/vault' },
    { view: 'duplicates' as const, label: 'Duplicati', hash: '#/duplicates' },
    { view: 'ops' as const, label: 'Sistema', hash: '#/ops' },
  ]

  function isActive(view: Route['view']) {
    return route.view === view || (view === 'editor' && route.view === 'editor')
  }
</script>

<div class="shell">
  <aside class="sidebar">
    <a class="brand" href="#/" aria-label="LeLe Manager, browse" onclick={(e) => { e.preventDefault(); navigate({ view: 'browse' }) }}>
      <img src="/app/brand/lele-manager-mark.svg" alt="" aria-hidden="true" />
      <span>
        <strong>LeLe Manager</strong>
        <small class="brand-tagline" data-testid="brand-tagline">Lo spazio locale per le tue 'Lessons Learned'</small>
      </span>
    </a>
    <nav>
      {#each links as link}
        <a
          href={link.hash}
          class:active={isActive(link.view)}
          onclick={(e) => {
            e.preventDefault()
            navigate({ view: link.view })
          }}
        >
          {link.label}
        </a>
      {/each}
    </nav>
    <footer class="product-signature" data-testid="giadaware-signature">
      <img
        class="signature-mark"
        src="/app/brand/giadaware-monkey.svg"
        alt=""
        aria-hidden="true"
      />
      <span class="signature-copy">
        <strong>GiadaWare™</strong>
        <small>Software open source</small>
      </span>
    </footer>
  </aside>

  <div class="main">
    <header>
      <HealthBar />
      <a
        class="btn btn-primary"
        href="#/editor"
        aria-label="Nuova LeLe"
        data-testid="new-lesson-cta"
        onclick={(e) => {
          e.preventDefault()
          navigate({ view: 'editor' })
        }}
      >
        <span class="new-lesson-visible" aria-hidden="true">
          <span class="new-lesson-prefix">+ Nuova</span>
          <span class="lele-mascot-badge">
            <img
              src="/app/brand/giadaware-monkey.svg"
              alt=""
            />
            <span class="lele-balloon">LeLe</span>
          </span>
        </span>
      </a>
    </header>
    <div class="content">
      {@render children()}
    </div>
  </div>
</div>

<style>
  .shell {
    display: grid;
    grid-template-columns: 220px 1fr;
    min-height: 100vh;
  }

  .sidebar {
    background: var(--sidebar);
    color: var(--sidebar-text);
    padding: 20px 16px;
    display: flex;
    flex-direction: column;
    gap: 16px;
  }

  .brand {
    display: flex;
    align-items: center;
    gap: 10px;
    color: var(--sidebar-text);
    text-decoration: none;
    padding: 4px;
    border-radius: var(--radius-md);
  }

  .brand img {
    width: 34px;
    height: 34px;
    color: var(--color-brand-500);
    flex: 0 0 auto;
  }

  .brand span {
    display: grid;
    gap: 1px;
    min-width: 0;
  }

  .brand strong {
    font-size: 1.05rem;
    line-height: var(--line-height-tight);
  }

  .brand small {
    color: #e9dacc;
    font-size: 0.67rem;
    line-height: 1.25;
  }

  nav {
    display: grid;
    gap: 6px;
  }

  nav a {
    color: var(--sidebar-text);
    text-decoration: none;
    padding: 10px 12px;
    border-radius: 8px;
    opacity: 0.85;
  }

  nav a:hover,
  nav a.active {
    background: rgba(255, 255, 255, 0.1);
    opacity: 1;
  }

  .product-signature {
    display: grid;
    gap: 2px;
    margin-top: auto;
    padding: var(--space-4) 4px 2px;
    border-top: 1px solid rgb(255 255 255 / 14%);
    color: var(--color-text-inverse-muted);
    font-size: var(--font-size-xs);
    line-height: var(--line-height-tight);
  }

  .product-signature strong {
    color: var(--sidebar-text);
    font-size: var(--font-size-sm);
    letter-spacing: 0.02em;
  }

  .main {
    display: flex;
    flex-direction: column;
    min-width: 0;
  }

  header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 12px;
    padding: 14px 20px;
    border-bottom: 1px solid var(--border);
    background: rgb(255 255 255 / 94%);
    position: sticky;
    top: 0;
    z-index: 1;
  }

  .content {
    width: min(100%, var(--content-width));
    padding: var(--space-5);
  }

  /* Viewport-pinned desktop sidebar */
  @media (min-width: 801px) {
    .sidebar {
      position: sticky;
      top: 0;
      align-self: start;
      box-sizing: border-box;
      height: 100vh;
      height: 100dvh;
      max-height: 100vh;
      max-height: 100dvh;
      overflow-y: auto;
    }
  }

  @media (max-width: 800px) {
    .shell {
      grid-template-columns: 1fr;
    }

    .sidebar {
      flex-direction: row;
      flex-wrap: wrap;
      align-items: center;
    }

    .brand small {
      display: none;
    }

    .sidebar {
      position: static;
      height: auto;
      max-height: none;
      overflow-y: visible;
      align-self: stretch;
    }

    .product-signature {
      display: none;
    }

    nav {
      grid-auto-flow: column;
      grid-auto-columns: max-content;
    }

  }
  /* Brand and maker-signature refinement */
  .brand {
    grid-template-columns: 32px minmax(0, 1fr);
    align-items: start;
    column-gap: 12px;
  }

  .brand > img {
    width: 32px;
    height: 32px;
    margin-top: 2px;
  }

  .brand > span {
    display: grid;
    min-width: 0;
    gap: 4px;
  }

  .brand strong {
    line-height: 1.2;
  }

  .brand-tagline {
    display: block;
    max-width: 136px;
    font-size: 12px;
    font-weight: 500;
    line-height: 1.35;
    overflow-wrap: normal;
  }

  .product-signature {
    grid-template-columns: 32px minmax(0, 1fr);
    align-items: center;
    column-gap: 10px;
  }

  .signature-mark {
    display: block;
    width: 32px;
    height: 32px;
  }

  .signature-copy {
    display: grid;
    min-width: 0;
    gap: 2px;
  }

  .signature-copy strong {
    line-height: 1.2;
  }

  .signature-copy small {
    color: var(--color-text-inverse-muted);
    font-size: 11px;
    line-height: 1.25;
  }

  /* New lesson mascot call to action */
  .new-lesson-visible {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    white-space: nowrap;
  }

  .new-lesson-prefix {
    line-height: 1;
  }

  .lele-mascot-badge {
    position: relative;
    display: inline-flex;
    align-items: center;
    min-width: 58px;
    height: 28px;
  }

  .lele-mascot-badge img {
    display: block;
    width: 25px;
    height: 25px;
    flex: 0 0 auto;
  }

  .lele-balloon {
    position: relative;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-width: 32px;
    height: 21px;
    margin-left: 3px;
    padding: 0 6px;
    border: 1px solid rgb(255 255 255 / 58%);
    border-radius: 999px;
    background: var(--color-surface);
    color: var(--color-text);
    font-size: 11px;
    font-weight: 800;
    line-height: 1;
    letter-spacing: 0.01em;
  }

  .lele-balloon::before {
    position: absolute;
    left: -5px;
    bottom: 2px;
    width: 7px;
    height: 7px;
    border-left: 1px solid rgb(255 255 255 / 58%);
    border-bottom: 1px solid rgb(255 255 255 / 58%);
    background: var(--color-surface);
    content: '';
    transform: rotate(45deg);
  }

</style>
