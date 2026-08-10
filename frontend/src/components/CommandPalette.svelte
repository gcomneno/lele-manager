<script lang="ts">
  import { onMount, tick } from 'svelte'
  import { messages } from '../lib/i18n'
  import { navigate, type Route } from '../lib/router'

  type CommandLabel =
    | 'navDashboard'
    | 'navBrowse'
    | 'commandSearchLele'
    | 'navTimeline'
    | 'navStatistics'
    | 'navCollection'
    | 'navVault'
    | 'navDuplicates'
    | 'navSystem'
    | 'navSettings'
    | 'navAbout'
    | 'navNewLele'

  type Command = {
    labelKey: CommandLabel
    route: Route
  }

  const commands: Command[] = [
    { labelKey: 'navDashboard', route: { view: 'dashboard' } },
    { labelKey: 'navBrowse', route: { view: 'browse' } },
    { labelKey: 'commandSearchLele', route: { view: 'browse' } },
    { labelKey: 'navTimeline', route: { view: 'timeline' } },
    { labelKey: 'navStatistics', route: { view: 'stats' } },
    { labelKey: 'navCollection', route: { view: 'tritalele' } },
    { labelKey: 'navVault', route: { view: 'vault' } },
    { labelKey: 'navDuplicates', route: { view: 'duplicates' } },
    { labelKey: 'navSystem', route: { view: 'ops' } },
    { labelKey: 'navSettings', route: { view: 'settings' } },
    { labelKey: 'navAbout', route: { view: 'about' } },
    { labelKey: 'navNewLele', route: { view: 'editor' } },
  ]

  let dialog = $state<HTMLDialogElement>()
  let trigger = $state<HTMLButtonElement>()
  let input = $state<HTMLInputElement>()
  let query = $state('')
  let isOpen = $state(false)
  let filteredCommands = $derived(commands.filter((command) =>
    $messages[command.labelKey]
      .toLocaleLowerCase()
      .includes(query.trim().toLocaleLowerCase()),
  ))

  async function openPalette() {
    if (isOpen) return
    isOpen = true
    query = ''
    await tick()
    dialog?.showModal()
    input?.focus()
  }

  function closePalette() {
    dialog?.close()
  }

  function runCommand(command: Command) {
    navigate(command.route)
    closePalette()
  }

  function onDialogClose() {
    isOpen = false
    trigger?.focus()
  }

  function onInputKeydown(event: KeyboardEvent) {
    if (event.key === 'Enter' && filteredCommands[0]) {
      event.preventDefault()
      runCommand(filteredCommands[0])
    }
  }

  function isEditableTarget(target: EventTarget | null) {
    return target instanceof HTMLInputElement
      || target instanceof HTMLTextAreaElement
      || target instanceof HTMLSelectElement
      || (target instanceof HTMLElement && target.isContentEditable)
  }

  onMount(() => {
    const onKeydown = (event: KeyboardEvent) => {
      if (
        (event.ctrlKey || event.metaKey)
        && event.key.toLocaleLowerCase() === 'k'
        && !isEditableTarget(event.target)
      ) {
        event.preventDefault()
        void openPalette()
      }
    }

    window.addEventListener('keydown', onKeydown)
    return () => window.removeEventListener('keydown', onKeydown)
  })
</script>

<button
  bind:this={trigger}
  class="command-trigger"
  type="button"
  aria-haspopup="dialog"
  aria-expanded={isOpen}
  aria-controls="global-command-palette"
  data-testid="command-palette-trigger"
  onclick={() => void openPalette()}
>
  <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m21 21-4.35-4.35m1.35-5.15a6.5 6.5 0 1 1-13 0 6.5 6.5 0 0 1 13 0Z" /></svg>
  <span>{$messages.commandPaletteTrigger}</span>
  <kbd aria-label={$messages.commandPaletteShortcut}>Ctrl K</kbd>
</button>

<dialog
  bind:this={dialog}
  id="global-command-palette"
  aria-labelledby="command-palette-title"
  onclose={onDialogClose}
>
  <div class="palette">
    <div class="palette-heading">
      <h2 id="command-palette-title">{$messages.commandPaletteTitle}</h2>
      <button class="palette-close" type="button" onclick={closePalette}>
        {$messages.commandPaletteClose}
      </button>
    </div>
    <label class="visually-hidden" for="command-palette-query">
      {$messages.commandPalettePlaceholder}
    </label>
    <input
      bind:this={input}
      id="command-palette-query"
      bind:value={query}
      placeholder={$messages.commandPalettePlaceholder}
      onkeydown={onInputKeydown}
      autocomplete="off"
    />
    {#if filteredCommands.length}
      <p class="palette-hint">{$messages.commandPaletteEnterHint}</p>
      <ul aria-label={$messages.commandPaletteResults}>
        {#each filteredCommands as command, index}
          <li>
            <button
              class:default-command={index === 0}
              type="button"
              onclick={() => runCommand(command)}
            >
              {$messages[command.labelKey]}
            </button>
          </li>
        {/each}
      </ul>
    {:else}
      <p class="no-results" role="status">{$messages.commandPaletteNoResults}</p>
    {/if}
  </div>
</dialog>

<style>
  .command-trigger,
  .palette-close,
  li button {
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
    background: var(--color-surface);
    color: var(--color-text);
  }

  .command-trigger {
    display: inline-flex;
    min-height: 36px;
    align-items: center;
    gap: 7px;
    padding: 6px 9px;
    white-space: nowrap;
  }

  .command-trigger svg {
    width: 16px;
    height: 16px;
    fill: none;
    stroke: currentColor;
    stroke-width: 2;
    stroke-linecap: round;
  }

  kbd {
    padding: 1px 4px;
    border: 1px solid var(--border);
    border-radius: 4px;
    color: var(--color-text-muted);
    font-size: 0.7rem;
  }

  dialog {
    width: min(560px, calc(100vw - 32px));
    padding: 0;
    border: 1px solid var(--border);
    border-radius: var(--radius-lg);
    color: var(--color-text);
    background: var(--color-surface);
    box-shadow: 0 18px 48px rgb(36 28 22 / 28%);
  }

  dialog::backdrop { background: rgb(36 28 22 / 42%); }

  .palette { padding: var(--space-4); }

  .palette-heading {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-3);
    margin-bottom: var(--space-3);
  }

  h2 { margin: 0; font-size: var(--font-size-lg); }

  .palette-close { min-height: 32px; padding: 4px 8px; }

  input { width: 100%; }

  ul {
    display: grid;
    gap: 4px;
    margin: var(--space-3) 0 0;
    padding: 0;
    list-style: none;
  }

  li button {
    width: 100%;
    min-height: 38px;
    padding: 7px 10px;
    text-align: left;
  }

  li button:hover { background: var(--color-surface-subtle); }
  li button.default-command {
    border-color: var(--color-border-accent);
    background: var(--color-brand-100);
  }
  .palette-hint { margin: var(--space-3) 0 0; color: var(--color-text-muted); font-size: var(--font-size-xs); }
  .no-results { margin: var(--space-4) 0 0; color: var(--color-text-muted); }

  .visually-hidden {
    position: absolute;
    width: 1px;
    height: 1px;
    overflow: hidden;
    clip: rect(0 0 0 0);
    white-space: nowrap;
  }

  @media (max-width: 800px) {
    .command-trigger span { display: none; }
    .command-trigger { padding: 6px 8px; }
  }
</style>
