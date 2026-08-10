<script lang="ts">
  import { onMount } from 'svelte'
  import { api } from '../lib/api'
  import { navigate, type Route } from '../lib/router'
  import {
    locale,
    messages,
    setLocale,
  } from '../lib/i18n'
  import HealthBar from './HealthBar.svelte'
  import CommandPalette from './CommandPalette.svelte'
  import HeaderHelp from './HeaderHelp.svelte'
  import NavIcon from './NavIcon.svelte'

  interface Props {
    route: Route
    children: import('svelte').Snippet
  }

  let { route, children }: Props = $props()

  type NavigationGroupId = 'knowledge' | 'capture' | 'manage'

  type NavigationGroupState = Record<NavigationGroupId, boolean>

  const NAVIGATION_GROUPS_STORAGE_KEY =
    'lele-manager.navigation-groups.v1'
  const SIDEBAR_VISIBILITY_STORAGE_KEY =
    'lele-manager.sidebar-visible.v1'

  const navigationGroupIds: NavigationGroupId[] = [
    'knowledge',
    'capture',
    'manage',
  ]

  const defaultNavigationGroupState: NavigationGroupState = {
    knowledge: true,
    capture: true,
    manage: true,
  }

  const navigationGroups = [
    {
      id: 'knowledge' as const,
      labelKey: 'navGroupKnowledge' as const,
      links: [
        { view: 'dashboard' as const, labelKey: 'navDashboard' as const, hash: '#/', icon: 'dashboard' as const },
        { view: 'browse' as const, labelKey: 'navBrowse' as const, hash: '#/browse', icon: 'browse' as const },
        { view: 'timeline' as const, labelKey: 'navTimeline' as const, hash: '#/timeline', icon: 'timeline' as const },
        { view: 'stats' as const, labelKey: 'navStatistics' as const, hash: '#/stats', icon: 'stats' as const },
      ],
    },
    {
      id: 'capture' as const,
      labelKey: 'navGroupCapture' as const,
      links: [
        { view: 'editor' as const, labelKey: 'navNewLele' as const, hash: '#/editor', icon: 'new' as const },
        { view: 'tritalele' as const, labelKey: 'navCollection' as const, hash: '#/tritalele', icon: 'collection' as const },
      ],
    },
    {
      id: 'manage' as const,
      labelKey: 'navGroupManage' as const,
      links: [
        { view: 'vault' as const, labelKey: 'navVault' as const, hash: '#/vault', icon: 'vault' as const },
        { view: 'duplicates' as const, labelKey: 'navDuplicates' as const, hash: '#/duplicates', icon: 'duplicates' as const },
        { view: 'ops' as const, labelKey: 'navSystem' as const, hash: '#/ops', icon: 'system' as const },
        { view: 'settings' as const, labelKey: 'navSettings' as const, hash: '#/settings', icon: 'diagnostics' as const },
        { view: 'about' as const, labelKey: 'navAbout' as const, hash: '#/about', icon: 'about' as const },
      ],
    },
  ]

  let workspaceName = $state<string | null>(null)
  let sidebarVisible = $state(loadSidebarVisibility())
  let navigationGroupState = $state<NavigationGroupState>(
    loadNavigationGroupState(),
  )

  function basename(path: string): string {
    const parts = path.split(/[\\/]+/).filter(Boolean)
    return parts.at(-1) ?? path
  }

  onMount(() => {
    let active = true

    void api.vaultStatus().then((vault) => {
      if (!active) return

      workspaceName = basename(vault.vault_dir)
    }).catch(() => {
      // Workspace context is best-effort and must never block the shell.
    })

    return () => {
      active = false
    }
  })

  function isActive(view: Route['view']) {
    return route.view === view || (view === 'editor' && route.view === 'editor')
  }

  function activeNavigationGroup(): NavigationGroupId | undefined {
    return navigationGroups.find((group) =>
      group.links.some((link) => isActive(link.view)),
    )?.id
  }

  function loadNavigationGroupState(): NavigationGroupState {
    if (typeof window === 'undefined') {
      return { ...defaultNavigationGroupState }
    }

    try {
      const persisted = JSON.parse(
        window.localStorage.getItem(NAVIGATION_GROUPS_STORAGE_KEY) ?? 'null',
      )

      if (!persisted || typeof persisted !== 'object' || Array.isArray(persisted)) {
        return { ...defaultNavigationGroupState }
      }

      if (Object.keys(persisted).some((key) => !navigationGroupIds.includes(
        key as NavigationGroupId,
      ))) {
        return { ...defaultNavigationGroupState }
      }

      return {
        knowledge: typeof persisted.knowledge === 'boolean'
          ? persisted.knowledge
          : defaultNavigationGroupState.knowledge,
        capture: typeof persisted.capture === 'boolean'
          ? persisted.capture
          : defaultNavigationGroupState.capture,
        manage: typeof persisted.manage === 'boolean'
          ? persisted.manage
          : defaultNavigationGroupState.manage,
      }
    } catch {
      return { ...defaultNavigationGroupState }
    }
  }

  function persistNavigationGroupState() {
    if (typeof window === 'undefined') return

    try {
      window.localStorage.setItem(
        NAVIGATION_GROUPS_STORAGE_KEY,
        JSON.stringify(navigationGroupState),
      )
    } catch {
      // Persistence is best-effort; disclosure still works in this session.
    }
  }

  function loadSidebarVisibility(): boolean {
    if (typeof window === 'undefined') return true

    try {
      const persisted = window.localStorage.getItem(
        SIDEBAR_VISIBILITY_STORAGE_KEY,
      )
      return persisted === 'false' ? false : true
    } catch {
      return true
    }
  }

  function toggleSidebar() {
    sidebarVisible = !sidebarVisible

    if (typeof window === 'undefined') return
    try {
      window.localStorage.setItem(
        SIDEBAR_VISIBILITY_STORAGE_KEY,
        String(sidebarVisible),
      )
    } catch {
      // Persistence is best-effort; the sidebar still works in this session.
    }
  }

  function expandActiveNavigationGroup() {
    const groupId = activeNavigationGroup()

    if (groupId && !navigationGroupState[groupId]) {
      navigationGroupState[groupId] = true
      persistNavigationGroupState()
    }
  }

  function toggleNavigationGroup(groupId: NavigationGroupId) {
    if (groupId === activeNavigationGroup()) {
      expandActiveNavigationGroup()
      return
    }

    navigationGroupState[groupId] = !navigationGroupState[groupId]
    persistNavigationGroupState()
  }

  $effect(() => {
    route.view
    expandActiveNavigationGroup()
  })

</script>

<div class:sidebar-hidden={!sidebarVisible} class="shell">
  <header class="global-header">
    <button
      class="sidebar-toggle"
      type="button"
      aria-label={sidebarVisible ? $messages.hideNavigation : $messages.showNavigation}
      aria-expanded={sidebarVisible}
      aria-controls="primary-sidebar"
      data-testid="sidebar-toggle"
      onclick={toggleSidebar}
    >
      <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 6h16M4 12h16M4 18h16" /></svg>
    </button>
    <dl class="workspace-context" data-testid="header-workspace">
      <dt>{$messages.shellWorkspace}</dt>
      <dd data-testid="shell-workspace">{workspaceName ?? $messages.shellWorkspaceUnavailable}</dd>
    </dl>
    <div class="header-utilities">
      <CommandPalette />
      <HealthBar />
      <label class="header-language" for="lele-manager-language">
        <span>{$messages.languageLabel}</span>
        <select
          id="lele-manager-language"
          data-testid="language-control"
          value={$locale}
          onchange={(event) => setLocale(event.currentTarget.value)}
        >
          <option value="en">{$messages.languageEnglish}</option>
          <option value="it">{$messages.languageItalian}</option>
        </select>
      </label>
      <HeaderHelp />
    </div>
  </header>

  <aside id="primary-sidebar" class="sidebar" hidden={!sidebarVisible}>
    <a class="brand" href="#/" aria-label={$messages.brandHomeAccessible} onclick={(e) => { e.preventDefault(); navigate({ view: 'dashboard' }) }}>
      <img src="/app/brand/lele-manager-mark.svg" alt="" aria-hidden="true" />
      <span>
        <strong>LeLe Manager</strong>
        <small class="brand-tagline" data-testid="brand-tagline">{$messages.brandTagline}</small>
      </span>
    </a>
    <nav aria-label="Primary">
      {#each navigationGroups as group}
        <section
          class="nav-group"
          aria-label={$messages[group.labelKey]}
        >
          <button
            class="nav-group-title"
            type="button"
            aria-expanded={navigationGroupState[group.id]}
            aria-controls={`navigation-group-${group.id}`}
            onclick={() => toggleNavigationGroup(group.id)}
          >
            <span>{$messages[group.labelKey]}</span>
            <svg
              class:expanded={navigationGroupState[group.id]}
              class="nav-group-chevron"
              viewBox="0 0 16 16"
              aria-hidden="true"
            >
              <path d="m4 6 4 4 4-4" />
            </svg>
          </button>
          <div
            id={`navigation-group-${group.id}`}
            class="nav-group-links"
            hidden={!navigationGroupState[group.id]}
          >
            {#each group.links as link}
              <a
                href={link.hash}
                class:active={isActive(link.view)}
                aria-current={isActive(link.view) ? 'page' : undefined}
                onclick={(e) => {
                  e.preventDefault()
                  navigate({ view: link.view })
                }}
              >
                <span class="nav-link-icon" aria-hidden="true">
                  <NavIcon name={link.icon} />
                </span>
                <span>{$messages[link.labelKey]}</span>
              </a>
            {/each}
          </div>
        </section>
      {/each}
    </nav>

    <footer class="product-signature" data-testid="giadaware-signature">
      <span
        class="signature-mascot"
        data-testid="giadaware-signature-mascot"
        aria-hidden="true"
      >
        <span class="signature-face-crop">
          <img
            class="signature-mark"
            src="/app/brand/lele-cameo/05-walk-right-a.png"
            alt=""
          />
        </span>
        <span
          class="signature-tongue"
          data-testid="giadaware-signature-tongue"
          aria-hidden="true"
        ></span>
        <span
          class="signature-thought"
          data-testid="giadaware-signature-thought"
        >…</span>
      </span>
      <span class="signature-copy">
        <strong>GiadaWare™</strong>
        <small>{$messages.makerOpenSource}</small>
      </span>
    </footer>
  </aside>

  <main class="main">
    <div class="content">
      {@render children()}
    </div>

    <div
      class="lele-cameo"
      data-testid="lele-monkey-cameo"
      aria-hidden="true"
    >
      <div
        class="lele-cameo-stage"
        data-testid="lele-monkey-cameo-character"
      >
        <img
          class="lele-cameo-frame lele-cameo-enter"
          src="/app/brand/lele-cameo/01-enter.png"
          alt=""
        />
        <img
          class="lele-cameo-frame lele-cameo-walk-left-a"
          src="/app/brand/lele-cameo/02-walk-left-a.png"
          alt=""
        />
        <img
          class="lele-cameo-frame lele-cameo-walk-left-b"
          src="/app/brand/lele-cameo/03-walk-left-b.png"
          alt=""
        />
        <img
          class="lele-cameo-frame lele-cameo-scratch"
          src="/app/brand/lele-cameo/04-scratch.png"
          alt=""
        />
        <img
          class="lele-cameo-frame lele-cameo-walk-right-a"
          src="/app/brand/lele-cameo/05-walk-right-a.png"
          alt=""
        />
        <img
          class="lele-cameo-frame lele-cameo-walk-right-b"
          src="/app/brand/lele-cameo/06-walk-right-b.png"
          alt=""
        />
        <img
          class="lele-cameo-frame lele-cameo-exit"
          src="/app/brand/lele-cameo/07-exit.png"
          alt=""
        />
      </div>

      <span
        class="lele-cameo-balloon"
        data-testid="lele-monkey-cameo-balloon"
      >
        LeLe!!
      </span>
    </div>
  </main>
</div>

<style>
  .shell {
    display: grid;
    grid-template-columns: 220px 1fr;
    grid-template-areas:
      'sidebar header'
      'sidebar main';
    grid-template-rows: auto minmax(0, 1fr);
    min-height: 100vh;
  }

  .shell.sidebar-hidden {
    grid-template-columns: minmax(0, 1fr);
    grid-template-areas:
      'header'
      'main';
  }

  .sidebar {
    grid-area: sidebar;
    background: var(--sidebar);
    color: var(--sidebar-text);
    padding: 20px 16px;
    display: flex;
    flex-direction: column;
    gap: 16px;
  }

  .sidebar[hidden] {
    display: none;
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
    gap: 14px;
  }

  .nav-group {
    display: grid;
    gap: 4px;
  }

  .nav-group-title {
    display: flex;
    align-items: center;
    justify-content: space-between;
    width: 100%;
    margin: 0;
    padding: 6px 12px;
    border: 0;
    border-radius: var(--radius-sm);
    color: var(--color-text-inverse-muted);
    background: transparent;
    font: inherit;
    font-size: 0.68rem;
    font-weight: 700;
    letter-spacing: 0.08em;
    line-height: 1.25;
    text-align: left;
    text-transform: uppercase;
    cursor: pointer;
  }

  .nav-group-title:hover {
    color: var(--sidebar-text);
    background: rgb(255 255 255 / 8%);
  }

  .nav-group-title:focus-visible,
  nav a:focus-visible {
    outline: 0;
    box-shadow: var(--focus-ring);
  }

  .nav-group-chevron {
    width: 16px;
    height: 16px;
    flex: 0 0 auto;
    fill: none;
    stroke: currentColor;
    stroke-width: 1.8;
    stroke-linecap: round;
    stroke-linejoin: round;
  }

  .nav-group-chevron.expanded {
    transform: rotate(180deg);
  }

  .nav-group-links {
    display: grid;
    gap: 3px;
  }

  .nav-group-links[hidden] {
    display: none;
  }

  nav a {
    display: flex;
    align-items: center;
    gap: 7px;
    color: var(--sidebar-text);
    text-decoration: none;
    padding: 10px 12px;
    border-radius: 8px;
    opacity: 0.85;
  }

  .nav-link-icon {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 1.05rem;
    flex: 0 0 1.05rem;
    line-height: 1;
    font-size: 0.95rem;
    opacity: 0.9;
    user-select: none;
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
    padding: var(--space-3) 4px 2px;
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
    grid-area: main;
    display: flex;
    flex-direction: column;
    min-width: 0;
  }

  .global-header {
    grid-area: header;
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 14px 20px;
    border-bottom: 1px solid var(--border);
    background: rgb(255 255 255 / 94%);
    position: sticky;
    top: 0;
    z-index: 1;
  }

  .sidebar-toggle {
    display: inline-flex;
    width: 36px;
    min-height: 36px;
    flex: 0 0 auto;
    align-items: center;
    justify-content: center;
    padding: 6px;
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
    background: var(--color-surface);
    color: var(--color-text);
  }

  .sidebar-toggle svg {
    width: 18px;
    height: 18px;
    fill: none;
    stroke: currentColor;
    stroke-linecap: round;
    stroke-width: 2;
  }

  .workspace-context {
    display: grid;
    min-width: 0;
    margin: 0;
    line-height: 1.15;
  }

  .workspace-context dt {
    color: var(--color-text-muted);
    font-size: var(--font-size-xs);
  }

  .workspace-context dd {
    max-width: 190px;
    margin: 2px 0 0;
    overflow: hidden;
    font-size: var(--font-size-sm);
    font-weight: 650;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .header-utilities {
    display: flex;
    min-width: 0;
    align-items: center;
    justify-content: flex-end;
    gap: 10px;
    margin-left: auto;
  }

  .header-language {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    color: var(--color-text-muted);
    font-size: var(--font-size-xs);
  }

  .header-language select {
    min-height: 36px;
    max-width: 102px;
    padding: 5px 26px 5px 7px;
  }

  .content {
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
      grid-template-columns: minmax(0, 1fr);
      grid-template-areas:
        'header'
        'sidebar'
        'main';
      grid-template-rows: auto auto minmax(0, 1fr);
      width: 100%;
      max-width: 100%;
      overflow-x: clip;
    }

    .sidebar {
      box-sizing: border-box;
      width: 100%;
      min-width: 0;
      max-width: 100%;
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

    .global-header {
      flex-wrap: wrap;
      gap: 8px;
      padding: 10px;
    }

    .workspace-context {
      flex: 1 1 auto;
    }

    .workspace-context dd { max-width: 160px; }

    .header-utilities {
      width: 100%;
      flex: 1 1 100%;
      justify-content: space-between;
      gap: 6px;
      margin-left: 0;
    }

    .header-language > span { display: none; }

    .header-language select { max-width: 94px; }

    nav {
      box-sizing: border-box;
      width: 100%;
      min-width: 0;
      max-width: 100%;
      gap: 10px;
    }

    .nav-group,
    .nav-group-links {
      min-width: 0;
      max-width: 100%;
    }

    .nav-group {
      gap: 3px;
    }

    .nav-group-title {
      padding: 6px 4px;
    }

    .nav-group-links {
      display: flex;
      flex-wrap: wrap;
      gap: 4px;
    }

    nav a {
      padding: 8px 10px;
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

  .signature-mascot {
    position: relative;
    display: block;
    width: 32px;
    height: 32px;
    transform-origin: 50% 72%;
    animation: lele-signature-think 26s ease-in-out infinite;
  }

  .signature-face-crop {
    position: relative;
    display: block;
    width: 32px;
    height: 32px;
    overflow: hidden;
    border-radius: 50%;
  }

  .signature-mark {
    position: absolute;
    top: -8px;
    left: -17px;
    display: block;
    width: 61px;
    height: 61px;
    max-width: none;
  }

  .signature-tongue {
    position: absolute;
    left: 18px;
    top: 20px;
    z-index: 2;
    width: 4px;
    height: 5px;
    border: 1px solid rgb(81 42 35 / 28%);
    border-top: 0;
    border-radius: 0 0 999px 999px;
    background: #f28da8;
    opacity: 0;
    transform: translateY(1px) scaleY(0.2);
    transform-origin: top center;
    pointer-events: none;
    animation: lele-signature-tongue 31s ease-in-out infinite;
  }

  .signature-thought {
    position: absolute;
    left: 24px;
    top: -13px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-width: 24px;
    height: 17px;
    padding: 0 5px 2px;
    border: 1px solid rgb(255 255 255 / 42%);
    border-radius: 999px;
    background: var(--color-surface);
    color: var(--color-text);
    font-size: 12px;
    font-weight: 800;
    line-height: 1;
    letter-spacing: 1px;
    opacity: 0;
    transform: translate(-2px, 3px) scale(0.88);
    transform-origin: left bottom;
    pointer-events: none;
    animation: lele-thought-bubble 26s ease-in-out infinite;
  }

  .signature-thought::before {
    position: absolute;
    left: -5px;
    bottom: -4px;
    width: 5px;
    height: 5px;
    border-radius: 999px;
    background: var(--color-surface);
    content: '';
  }

  @keyframes lele-signature-tongue {
    0%,
    68%,
    75%,
    100% {
      opacity: 0;
      transform: translateY(1px) scaleY(0.2);
    }

    69%,
    73% {
      opacity: 1;
      transform: translateY(3px) scaleY(1);
    }
  }

  @keyframes lele-signature-think {
    0%,
    84%,
    100% {
      transform: rotate(0deg) translateY(0);
    }

    87% {
      transform: rotate(-5deg) translateY(-1px);
    }

    91% {
      transform: rotate(-4deg) translateY(-1px);
    }

    95% {
      transform: rotate(0deg) translateY(0);
    }
  }

  @keyframes lele-thought-bubble {
    0%,
    85%,
    97%,
    100% {
      opacity: 0;
      transform: translate(-2px, 3px) scale(0.88);
    }

    88%,
    94% {
      opacity: 1;
      transform: translate(0, 0) scale(1);
    }
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

  @media (prefers-reduced-motion: reduce) {
    .signature-mascot,
    .signature-thought,
    .signature-tongue,
    .lele-cameo,
    .lele-cameo-stage,
    .lele-cameo-frame,
    .lele-cameo-balloon {
      animation: none;
      transform: none;
    }

    .signature-thought,
    .signature-tongue {
      opacity: 0;
    }

    .lele-cameo {
      display: none;
      opacity: 0;
    }
  }

  /* One-shot illustrated wandering monkey cameo */
  .lele-cameo {
    --lele-cameo-duration: 12s;
    --lele-cameo-delay: 8s;

    position: fixed;
    right: -174px;
    bottom: 4px;
    z-index: 3;
    width: 174px;
    height: 174px;
    opacity: 0;
    pointer-events: none;
    animation:
      lele-cameo-path
      var(--lele-cameo-duration)
      linear
      var(--lele-cameo-delay)
      1
      both;
  }

  .lele-cameo-stage {
    position: absolute;
    inset: 0;
  }

  .lele-cameo-frame {
    position: absolute;
    inset: 0;
    display: block;
    width: 174px;
    height: 174px;
    object-fit: contain;
    opacity: 0;
    user-select: none;
  }

  .lele-cameo-enter {
    animation:
      lele-cameo-enter-frame
      var(--lele-cameo-duration)
      steps(1, end)
      var(--lele-cameo-delay)
      1
      both;
  }

  .lele-cameo-walk-left-a,
  .lele-cameo-walk-left-b {
    transform: scaleX(-1);
  }

  .lele-cameo-walk-left-a {
    animation:
      lele-cameo-walk-left-a-frame
      var(--lele-cameo-duration)
      steps(1, end)
      var(--lele-cameo-delay)
      1
      both;
  }

  .lele-cameo-walk-left-b {
    animation:
      lele-cameo-walk-left-b-frame
      var(--lele-cameo-duration)
      steps(1, end)
      var(--lele-cameo-delay)
      1
      both;
  }

  .lele-cameo-scratch {
    animation:
      lele-cameo-scratch-frame
      var(--lele-cameo-duration)
      steps(1, end)
      var(--lele-cameo-delay)
      1
      both;
  }

  .lele-cameo-walk-right-a {
    animation:
      lele-cameo-walk-right-a-frame
      var(--lele-cameo-duration)
      steps(1, end)
      var(--lele-cameo-delay)
      1
      both;
  }

  .lele-cameo-walk-right-b {
    animation:
      lele-cameo-walk-right-b-frame
      var(--lele-cameo-duration)
      steps(1, end)
      var(--lele-cameo-delay)
      1
      both;
  }

  .lele-cameo-exit {
    animation:
      lele-cameo-exit-frame
      var(--lele-cameo-duration)
      steps(1, end)
      var(--lele-cameo-delay)
      1
      both;
  }

  .lele-cameo-balloon {
    position: absolute;
    right: 110px;
    top: 2px;
    z-index: 5;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-width: 64px;
    min-height: 34px;
    padding: 2px 11px;
    border: 1px solid var(--border);
    border-radius: 999px;
    background: var(--color-surface);
    color: var(--color-text);
    font-size: 16px;
    font-weight: 800;
    line-height: 1;
    opacity: 0;
    transform: translateY(5px) scale(0.86);
    transform-origin: right bottom;
    box-shadow: 0 3px 9px rgb(36 28 22 / 12%);
    animation:
      lele-cameo-balloon
      var(--lele-cameo-duration)
      ease-in-out
      var(--lele-cameo-delay)
      1
      both;
  }

  .lele-cameo-balloon::after {
    position: absolute;
    right: -5px;
    bottom: 3px;
    width: 9px;
    height: 9px;
    border-right: 1px solid var(--border);
    border-bottom: 1px solid var(--border);
    background: var(--color-surface);
    content: '';
    transform: rotate(-45deg);
  }

  @keyframes lele-cameo-path {
    0% {
      opacity: 0;
      transform: translateX(0);
    }

    2% {
      opacity: 1;
    }

    9% {
      opacity: 1;
      transform: translateX(-105px);
    }

    13% {
      transform: translateX(-145px);
    }

    17% {
      transform: translateX(-185px);
    }

    21% {
      transform: translateX(-225px);
    }

    25% {
      transform: translateX(-265px);
    }

    29% {
      transform: translateX(-305px);
    }

    32%,
    58% {
      opacity: 1;
      transform: translateX(-325px);
    }

    62% {
      transform: translateX(-290px);
    }

    66% {
      transform: translateX(-250px);
    }

    70% {
      transform: translateX(-210px);
    }

    74% {
      transform: translateX(-170px);
    }

    78% {
      transform: translateX(-130px);
    }

    82% {
      transform: translateX(-90px);
    }

    86% {
      transform: translateX(-50px);
    }

    90% {
      transform: translateX(-15px);
    }

    98% {
      opacity: 1;
      transform: translateX(0);
    }

    100% {
      opacity: 0;
      transform: translateX(0);
    }
  }

  @keyframes lele-cameo-enter-frame {
    0%,
    9.99% {
      opacity: 1;
    }

    10%,
    100% {
      opacity: 0;
    }
  }

  @keyframes lele-cameo-walk-left-a-frame {
    0%,
    9.99%,
    13%,
    16.99%,
    21%,
    24.99%,
    29%,
    100% {
      opacity: 0;
    }

    10%,
    12.99%,
    17%,
    20.99%,
    25%,
    28.99% {
      opacity: 1;
    }
  }

  @keyframes lele-cameo-walk-left-b-frame {
    0%,
    12.99%,
    17%,
    20.99%,
    25%,
    28.99%,
    32%,
    100% {
      opacity: 0;
    }

    13%,
    16.99%,
    21%,
    24.99%,
    29%,
    31.99% {
      opacity: 1;
    }
  }

  @keyframes lele-cameo-scratch-frame {
    0%,
    31.99%,
    58%,
    100% {
      opacity: 0;
    }

    32%,
    57.99% {
      opacity: 1;
    }
  }

  @keyframes lele-cameo-walk-right-a-frame {
    0%,
    57.99%,
    62%,
    65.99%,
    70%,
    73.99%,
    78%,
    81.99%,
    86%,
    100% {
      opacity: 0;
    }

    58%,
    61.99%,
    66%,
    69.99%,
    74%,
    77.99%,
    82%,
    85.99% {
      opacity: 1;
    }
  }

  @keyframes lele-cameo-walk-right-b-frame {
    0%,
    61.99%,
    66%,
    69.99%,
    74%,
    77.99%,
    82%,
    85.99%,
    90%,
    100% {
      opacity: 0;
    }

    62%,
    65.99%,
    70%,
    73.99%,
    78%,
    81.99%,
    86%,
    89.99% {
      opacity: 1;
    }
  }

  @keyframes lele-cameo-exit-frame {
    0%,
    89.99% {
      opacity: 0;
    }

    90%,
    100% {
      opacity: 1;
    }
  }

  @keyframes lele-cameo-balloon {
    0%,
    40%,
    57%,
    100% {
      opacity: 0;
      transform: translateY(5px) scale(0.86);
    }

    41%,
    56% {
      opacity: 1;
      transform: translateY(0) scale(1);
    }
  }

  @media (max-width: 800px) {
    .lele-cameo {
      display: none;
    }
  }

  /* Compact desktop sidebar for short viewports */
  @media (min-width: 801px) and (max-height: 700px) {
    .sidebar {
      padding-top: 10px;
      padding-bottom: 10px;
      gap: 6px;
    }

    .brand > span {
      gap: 2px;
    }

    .brand-tagline {
      font-size: 11px;
      line-height: 1.2;
    }

    nav {
      gap: 5px;
    }

    .nav-group {
      gap: 1px;
    }

    .nav-group-title {
      font-size: 0.62rem;
      line-height: 1.1;
    }

    .nav-group-links {
      gap: 1px;
    }

    nav a {
      padding: 2px 10px;
      line-height: 1.15;
    }

    .product-signature {
      padding-top: 4px;
      padding-bottom: 0;
    }
  }

</style>
