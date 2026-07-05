<script lang="ts">
  import { navigate, type Route } from '../lib/router'
  import HealthBar from './HealthBar.svelte'

  interface Props {
    route: Route
    children: import('svelte').Snippet
  }

  let { route, children }: Props = $props()

  const links = [
    { view: 'browse' as const, label: 'Browse', hash: '#/' },
    { view: 'editor' as const, label: 'Editor', hash: '#/editor' },
    { view: 'vault' as const, label: 'Vault', hash: '#/vault' },
    { view: 'ops' as const, label: 'Ops', hash: '#/ops' },
  ]

  function isActive(view: Route['view']) {
    return route.view === view || (view === 'editor' && route.view === 'editor')
  }
</script>

<div class="shell">
  <aside class="sidebar">
    <div class="brand">🐒 LeLe Manager</div>
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
    <p class="legacy">
      <a href="/ui" target="_blank" rel="noreferrer">PoC legacy /ui</a>
    </p>
  </aside>

  <div class="main">
    <header>
      <HealthBar />
      <a class="btn btn-primary" href="#/editor" onclick={(e) => { e.preventDefault(); navigate({ view: 'editor' }) }}>
        + Nuova LeLe
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
    font-weight: 700;
    font-size: 1.05rem;
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

  .legacy {
    margin-top: auto;
    font-size: 0.75rem;
    opacity: 0.7;
  }

  .legacy a {
    color: var(--sidebar-text);
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
    background: rgba(255, 255, 255, 0.7);
    backdrop-filter: blur(6px);
    position: sticky;
    top: 0;
    z-index: 1;
  }

  .content {
    padding: 20px;
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

    nav {
      grid-auto-flow: column;
      grid-auto-columns: max-content;
    }

    .legacy {
      margin-top: 0;
    }
  }
</style>
