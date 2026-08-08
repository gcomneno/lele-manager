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
  import NavIcon from './NavIcon.svelte'

  interface Props {
    route: Route
    children: import('svelte').Snippet
  }

  let { route, children }: Props = $props()

  const navigationGroups = [
    {
      labelKey: 'navGroupKnowledge' as const,
      links: [
        { view: 'dashboard' as const, labelKey: 'navDashboard' as const, hash: '#/', icon: 'dashboard' as const },
        { view: 'browse' as const, labelKey: 'navBrowse' as const, hash: '#/browse', icon: 'browse' as const },
        { view: 'timeline' as const, labelKey: 'navTimeline' as const, hash: '#/timeline', icon: 'timeline' as const },
        { view: 'stats' as const, labelKey: 'navStatistics' as const, hash: '#/stats', icon: 'stats' as const },
      ],
    },
    {
      labelKey: 'navGroupCapture' as const,
      links: [
        { view: 'editor' as const, labelKey: 'navNewLele' as const, hash: '#/editor', icon: 'new' as const },
        { view: 'tritalele' as const, labelKey: 'navCollection' as const, hash: '#/tritalele', icon: 'collection' as const },
      ],
    },
    {
      labelKey: 'navGroupManage' as const,
      links: [
        { view: 'vault' as const, labelKey: 'navVault' as const, hash: '#/vault', icon: 'vault' as const },
        { view: 'duplicates' as const, labelKey: 'navDuplicates' as const, hash: '#/duplicates', icon: 'duplicates' as const },
        { view: 'ops' as const, labelKey: 'navSystem' as const, hash: '#/ops', icon: 'system' as const },
        { view: 'settings' as const, labelKey: 'navSettings' as const, hash: '#/settings', icon: 'system' as const },
        { view: 'about' as const, labelKey: 'navAbout' as const, hash: '#/about', icon: 'system' as const },
      ],
    },
  ]

  let appVersion = $state<string | null>(null)
  let workspaceName = $state<string | null>(null)

  function basename(path: string): string {
    const parts = path.split(/[\\/]+/).filter(Boolean)
    return parts.at(-1) ?? path
  }

  onMount(() => {
    let active = true

    void Promise.allSettled([
      api.runtimeInfo(),
      api.vaultStatus(),
    ]).then(([runtime, vault]) => {
      if (!active) return

      if (runtime.status === 'fulfilled') {
        appVersion = runtime.value.version
      }

      if (vault.status === 'fulfilled') {
        workspaceName = basename(vault.value.vault_dir)
      }
    })

    return () => {
      active = false
    }
  })

  function isActive(view: Route['view']) {
    return route.view === view || (view === 'editor' && route.view === 'editor')
  }
</script>

<div class="shell">
  <aside class="sidebar">
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
          <span class="nav-group-title">
            {$messages[group.labelKey]}
          </span>
          <div class="nav-group-links">
            {#each group.links as link}
              <a
                href={link.hash}
                class:active={isActive(link.view)}
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

    <dl class="shell-context" data-testid="shell-context">
      {#if workspaceName}
        <div>
          <dt>{$messages.shellWorkspace}</dt>
          <dd data-testid="shell-workspace">{workspaceName}</dd>
        </div>
      {/if}
      {#if appVersion}
        <div>
          <dt>{$messages.shellVersion}</dt>
          <dd data-testid="shell-version">{appVersion}</dd>
        </div>
      {/if}
    </dl>
    <div
      class="language-control"
      data-testid="language-control"
    >
      <label for="lele-manager-language">
        {$messages.languageLabel}
      </label>
      <select
        id="lele-manager-language"
        value={$locale}
        onchange={(event) => {
          setLocale(event.currentTarget.value)
        }}
      >
        <option value="en">
          {$messages.languageEnglish}
        </option>
        <option value="it">
          {$messages.languageItalian}
        </option>
      </select>
    </div>

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

  <div class="main">
    <header>
      <HealthBar />
      <a
        class="btn btn-primary new-lesson-cta"
        href="#/editor"
        aria-label={$messages.newLeleAccessible}
        data-testid="new-lesson-cta"
        onclick={(e) => {
          e.preventDefault()
          navigate({ view: 'editor' })
        }}
      >
        <span class="new-lesson-visible" aria-hidden="true">
          <span class="new-lesson-prefix">+ {$messages.newLelePrefix}</span>
          <span class="lele-mascot-badge">
            <span
              class="lele-monkey-face"
              data-testid="lele-monkey-motion"
            >
              <img
                src="/app/brand/lele-cameo/05-walk-right-a.png"
                alt=""
              />
            </span>
            <span class="lele-balloon">LeLe</span>
          </span>
        </span>
      </a>
    </header>
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
    gap: 14px;
  }

  .nav-group {
    display: grid;
    gap: 4px;
  }

  .nav-group-title {
    display: block;
    margin: 0;
    padding: 0 12px;
    color: var(--color-text-inverse-muted);
    font-size: 0.68rem;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
  }

  .nav-group-links {
    display: grid;
    gap: 3px;
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

  .shell-context {
    display: grid;
    gap: 6px;
    margin: 0;
    padding: 10px 4px 0;
    border-top: 1px solid rgb(255 255 255 / 14%);
  }

  .shell-context div {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    gap: 8px;
    align-items: baseline;
  }

  .shell-context dt,
  .shell-context dd {
    margin: 0;
    min-width: 0;
    font-size: 0.68rem;
  }

  .shell-context dt {
    color: var(--color-text-inverse-muted);
  }

  .shell-context dd {
    max-width: 110px;
    overflow: hidden;
    color: var(--sidebar-text);
    font-weight: 600;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .language-control {
    display: grid;
    gap: 5px;
    margin-top: auto;
    padding: var(--space-4) 4px 0;
    border-top: 1px solid rgb(255 255 255 / 14%);
  }

  .language-control label {
    color: var(--color-text-inverse-muted);
    font-size: var(--font-size-xs);
    font-weight: 600;
  }

  .language-control select {
    box-sizing: border-box;
    width: 100%;
    min-height: 36px;
    padding: 6px 28px 6px 9px;
    border: 1px solid rgb(255 255 255 / 24%);
    border-radius: var(--radius-sm);
    color: var(--sidebar-text);
    background: var(--sidebar);
    font: inherit;
  }

  .language-control select:focus-visible {
    outline: 0;
    box-shadow: var(--focus-ring);
  }

  .product-signature {
    display: grid;
    gap: 2px;
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

    .product-signature,
    .shell-context {
      display: none;
    }

    .language-control {
      flex: 0 0 140px;
      margin-top: 0;
      margin-left: auto;
      padding: 0;
      border-top: 0;
    }

    .language-control label {
      color: var(--sidebar-text);
    }

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
      padding: 0 4px;
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
    transform: translateY(-2px) scaleY(0.2);
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
      transform: translateY(-2px) scaleY(0.2);
    }

    69%,
    73% {
      opacity: 1;
      transform: translateY(0) scaleY(1);
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

  .lele-monkey-face {
    position: relative;
    display: inline-flex;
    width: 25px;
    height: 25px;
    flex: 0 0 25px;
    overflow: hidden;
    border-radius: 50%;
    transform-origin: 50% 70%;
    animation: lele-monkey-idle 18s ease-in-out infinite;
  }

  .lele-mascot-badge img {
    position: absolute;
    top: -6px;
    left: -13px;
    display: block;
    width: 48px;
    height: 48px;
    max-width: none;
    flex: none;
    transform-origin: 53% 39%;
  }

  .new-lesson-cta:hover .lele-monkey-face,
  .new-lesson-cta:focus-visible .lele-monkey-face {
    animation-play-state: paused;
  }

  .new-lesson-cta:hover .lele-monkey-face img,
  .new-lesson-cta:focus-visible .lele-monkey-face img {
    animation: lele-monkey-react 360ms ease-out 2;
  }

  @keyframes lele-monkey-idle {
    0%,
    90%,
    100% {
      transform: translateY(0) rotate(0deg);
    }

    92% {
      transform: translateY(-2px) rotate(-5deg);
    }

    94% {
      transform: translateY(-1px) rotate(4deg);
    }

    96% {
      transform: translateY(0) rotate(0deg);
    }
  }

  @keyframes lele-monkey-react {
    0%,
    100% {
      transform: rotate(0deg) scale(1);
    }

    35% {
      transform: translateY(-2px) rotate(-8deg) scale(1.08);
    }

    68% {
      transform: translateY(-1px) rotate(5deg) scale(1.04);
    }
  }

  @media (prefers-reduced-motion: reduce) {
    .lele-monkey-face,
    .signature-mascot,
    .signature-thought,
    .signature-tongue,
    .lele-cameo,
    .lele-cameo-stage,
    .lele-cameo-frame,
    .lele-cameo-balloon,
    .new-lesson-cta:hover .lele-monkey-face img,
    .new-lesson-cta:focus-visible .lele-monkey-face img {
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

    .shell-context {
      gap: 2px;
      padding-top: 5px;
    }

    .shell-context dt,
    .shell-context dd {
      font-size: 0.64rem;
      line-height: 1.15;
    }

    .language-control {
      gap: 2px;
      padding-top: 5px;
    }

    .language-control select {
      min-height: 30px;
      padding-top: 3px;
      padding-bottom: 3px;
    }

    .product-signature {
      padding-top: 4px;
      padding-bottom: 0;
    }
  }

</style>
