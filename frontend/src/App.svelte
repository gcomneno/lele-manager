<script lang="ts">
  import { onMount } from 'svelte'
  import Shell from './components/Shell.svelte'
  import Browse from './routes/Browse.svelte'
  import Detail from './routes/Detail.svelte'
  import Editor from './routes/Editor.svelte'
  import Vault from './routes/Vault.svelte'
  import Ops from './routes/Ops.svelte'
  import Stats from './routes/Stats.svelte'
  import Timeline from './routes/Timeline.svelte'
  import { parseRoute, type Route } from './lib/router'

  let route = $state<Route>({ view: 'browse' })

  onMount(() => {
    route = parseRoute()
    const onHash = () => {
      route = parseRoute()
    }
    window.addEventListener('hashchange', onHash)
    return () => window.removeEventListener('hashchange', onHash)
  })
</script>

<Shell {route}>
  {#if route.view === 'browse'}
    <Browse />
  {:else if route.view === 'detail'}
    <Detail id={route.id} />
  {:else if route.view === 'editor'}
    <Editor id={route.id} />
  {:else if route.view === 'vault'}
    <Vault />
  {:else if route.view === 'ops'}
    <Ops />
  {:else if route.view === 'stats'}
    <Stats />
  {:else if route.view === 'timeline'}
    <Timeline />
  {/if}
</Shell>
