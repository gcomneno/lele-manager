export type Route =
  | { view: 'browse' }
  | { view: 'detail'; id: string }
  | { view: 'editor'; id?: string }
  | { view: 'vault' }
  | { view: 'ops' }
  | { view: 'duplicates' }
  | { view: 'stats' }
  | { view: 'timeline' }
  | { view: 'tritalele' }

export function parseRoute(hash = location.hash): Route {
  const path = hash.replace(/^#/, '') || '/'

  if (path === '/' || path === '/browse') return { view: 'browse' }
  if (path === '/ops') return { view: 'ops' }
  if (path === '/duplicates') return { view: 'duplicates' }
  if (path === '/vault') return { view: 'vault' }
  if (path === '/stats') return { view: 'stats' }
  if (path === '/timeline') return { view: 'timeline' }
  if (path === '/tritalele') return { view: 'tritalele' }
  if (path === '/editor') return { view: 'editor' }

  const editorMatch = path.match(/^\/editor\/(.+)$/)
  if (editorMatch) return { view: 'editor', id: decodeURIComponent(editorMatch[1]) }

  const detailMatch = path.match(/^\/lesson\/(.+)$/)
  if (detailMatch) return { view: 'detail', id: decodeURIComponent(detailMatch[1]) }

  return { view: 'browse' }
}

export function routeToHash(route: Route): string {
  switch (route.view) {
    case 'browse':
      return '#/'
    case 'ops':
      return '#/ops'
    case 'duplicates':
      return '#/duplicates'
    case 'vault':
      return '#/vault'
    case 'stats':
      return '#/stats'
    case 'timeline':
      return '#/timeline'
    case 'tritalele':
      return '#/tritalele'
    case 'editor':
      return route.id ? `#/editor/${encodeURIComponent(route.id)}` : '#/editor'
    case 'detail':
      return `#/lesson/${encodeURIComponent(route.id)}`
  }
}

export function navigate(route: Route): void {
  const next = routeToHash(route)
  if (location.hash !== next) {
    location.hash = next.slice(1)
  }
}
