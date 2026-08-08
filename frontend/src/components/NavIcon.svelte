<script lang="ts">
  type IconName =
    | 'browse'
    | 'timeline'
    | 'stats'
    | 'new'
    | 'collection'
    | 'vault'
    | 'duplicates'
    | 'system'

  interface Props {
    name: IconName
  }

  let { name }: Props = $props()
</script>

<svg
  viewBox="0 0 24 24"
  width="18"
  height="18"
  fill="none"
  stroke="currentColor"
  stroke-width="1.8"
  stroke-linecap="round"
  stroke-linejoin="round"
  aria-hidden="true"
>
  {#if name === 'browse'}
    <path d="M4 5.5h6l2 2H20v11H4z" />
    <path d="M4 9h16" />
  {:else if name === 'timeline'}
    <circle cx="12" cy="12" r="8" />
    <path d="M12 7v5l3 2" />
  {:else if name === 'stats'}
    <path d="M5 19V10" />
    <path d="M12 19V5" />
    <path d="M19 19v-7" />
  {:else if name === 'new'}
    <path d="M12 5v14M5 12h14" />
  {:else if name === 'collection'}
    <rect x="5" y="6" width="14" height="13" rx="2" />
    <path d="M8 3h8M8 10h8M8 14h5" />
  {:else if name === 'vault'}
    <rect x="4" y="5" width="16" height="14" rx="3" />
    <circle cx="12" cy="12" r="3" />
    <path d="M12 9V7M12 17v-2M9 12H7M17 12h-2" />
  {:else if name === 'duplicates'}
    <rect x="4" y="4" width="11" height="11" rx="2" />
    <rect x="9" y="9" width="11" height="11" rx="2" />
  {:else}
    <circle cx="12" cy="12" r="3" />
    <path d="M12 3v2M12 19v2M3 12h2M19 12h2" />
    <path d="m5.6 5.6 1.4 1.4M17 17l1.4 1.4M18.4 5.6 17 7M7 17l-1.4 1.4" />
  {/if}
</svg>
