<script lang="ts">
  import {
    api,
    type ContextPack,
    type ContextPackDetail,
    type ContextPackMember,
    type LessonLifecycleState,
  } from '../lib/api'
  import { formatMessage, messages } from '../lib/i18n'
  import { FormStatus } from 'giadaware-ui-components'
  import {
    Button,
    FieldLabel,
  } from 'giadaware-ui-components/studio'

  type Props = {
    selectedLessonIds: string[]
    refreshToken?: number
  }

  let {
    selectedLessonIds,
    refreshToken = 0,
  }: Props = $props()

  let packs = $state<ContextPack[]>([])
  let detail = $state<ContextPackDetail | null>(null)
  let renameName = $state('')
  let loading = $state(false)
  let mutating = $state(false)
  let notice = $state('')
  let error = $state('')

  function lifecycleLabel(
    lifecycle: LessonLifecycleState | undefined,
  ): string {
    switch (lifecycle) {
      case 'review-needed':
        return $messages.lifecycleReviewNeeded
      case 'deprecated':
        return $messages.lifecycleDeprecated
      case 'archived':
        return $messages.lifecycleArchived
      case 'active':
      default:
        return $messages.lifecycleActive
    }
  }

  async function loadPacks() {
    loading = true
    error = ''

    try {
      packs = await api.listContextPacks()

      if (
        detail &&
        !packs.some((pack) => pack.id === detail?.id)
      ) {
        detail = null
        renameName = ''
      }
    } catch (e) {
      error = e instanceof Error ? e.message : String(e)
    } finally {
      loading = false
    }
  }

  async function inspectPack(pack: ContextPack) {
    error = ''
    notice = ''

    try {
      detail = await api.getContextPack(pack.id)
      renameName = detail.name
    } catch (e) {
      error = e instanceof Error ? e.message : String(e)
    }
  }

  async function refreshDetail() {
    if (!detail) return

    detail = await api.getContextPack(detail.id)
    renameName = detail.name
  }

  async function renamePack() {
    if (!detail || !renameName.trim()) return

    mutating = true
    error = ''
    notice = ''

    try {
      await api.renameContextPack(
        detail.id,
        renameName.trim(),
      )
      await loadPacks()
      await refreshDetail()
      notice = $messages.contextPackRenamed
    } catch (e) {
      error = e instanceof Error ? e.message : String(e)
    } finally {
      mutating = false
    }
  }

  async function addSelected() {
    if (!detail || selectedLessonIds.length === 0) return

    mutating = true
    error = ''
    notice = ''

    try {
      await api.addContextPackMembers(
        detail.id,
        selectedLessonIds,
      )
      await loadPacks()
      await refreshDetail()
      notice = formatMessage(
        $messages.contextPackMembersAdded,
        { count: selectedLessonIds.length },
      )
    } catch (e) {
      error = e instanceof Error ? e.message : String(e)
    } finally {
      mutating = false
    }
  }

  async function removeMember(member: ContextPackMember) {
    if (!detail) return

    mutating = true
    error = ''
    notice = ''

    try {
      await api.removeContextPackMembers(
        detail.id,
        [member.lesson_id],
      )
      await loadPacks()
      await refreshDetail()
      notice = $messages.contextPackMemberRemoved
    } catch (e) {
      error = e instanceof Error ? e.message : String(e)
    } finally {
      mutating = false
    }
  }

  async function copyPack() {
    if (!detail) return

    mutating = true
    error = ''
    notice = ''

    try {
      const markdown = await api.exportContextPack(
        detail.id,
        'markdown',
      )

      await navigator.clipboard.writeText(markdown as string)
      notice = $messages.contextPackCopied
    } catch (e) {
      error = e instanceof Error ? e.message : String(e)
    } finally {
      mutating = false
    }
  }

  async function exportPack() {
    if (!detail) return

    mutating = true
    error = ''
    notice = ''

    try {
      const markdown = await api.exportContextPack(
        detail.id,
        'markdown',
      )

      const blob = new Blob(
        [markdown as string],
        { type: 'text/markdown;charset=utf-8' },
      )
      const url = URL.createObjectURL(blob)
      const anchor = document.createElement('a')
      anchor.href = url
      anchor.download = `context-pack-${detail.id}.md`
      anchor.click()
      URL.revokeObjectURL(url)

      notice = $messages.contextPackExported
    } catch (e) {
      error = e instanceof Error ? e.message : String(e)
    } finally {
      mutating = false
    }
  }

  async function deletePack() {
    if (!detail) return

    if (!window.confirm(
      formatMessage(
        $messages.contextPackDeleteConfirm,
        { name: detail.name },
      ),
    )) {
      return
    }

    mutating = true
    error = ''
    notice = ''

    try {
      await api.deleteContextPack(detail.id)
      detail = null
      renameName = ''
      await loadPacks()
      notice = $messages.contextPackDeleted
    } catch (e) {
      error = e instanceof Error ? e.message : String(e)
    } finally {
      mutating = false
    }
  }

  $effect(() => {
    refreshToken
    void loadPacks()
  })
</script>

<section
  class="context-packs-manager"
  data-testid="context-packs-manager"
  aria-labelledby="context-packs-title"
>
  <div class="context-packs-heading">
    <div>
      <h2 id="context-packs-title">
        {$messages.contextPacksTitle}
      </h2>
      <p class="meta">
        {$messages.contextPacksDescription}
      </p>
    </div>
  </div>

  {#if error}
    <FormStatus
      message={error}
      tone="error"
      style="--giu-form-status-padding: var(--space-2) var(--space-3)"
    />
  {/if}

  {#if notice}
    <FormStatus
      message={notice}
      tone="success"
      style="--giu-form-status-padding: var(--space-2) var(--space-3)"
    />
  {/if}

  {#if loading && packs.length === 0}
    <p class="meta">{$messages.commonLoading}</p>
  {:else if packs.length === 0}
    <p class="meta">{$messages.contextPacksEmpty}</p>
  {:else}
    <div class="context-pack-list">
      {#each packs as pack (pack.id)}
        <button
          type="button"
          class:active={detail?.id === pack.id}
          class="context-pack-list-item"
          onclick={() => inspectPack(pack)}
        >
          <strong>{pack.name}</strong>
          <span>
            {formatMessage(
              $messages.contextPackMemberCount,
              { count: pack.lesson_ids.length },
            )}
          </span>
        </button>
      {/each}
    </div>
  {/if}

  {#if detail}
    <div
      class="context-pack-detail"
      data-testid={`context-pack-detail-${detail.id}`}
    >
      <div class="context-pack-detail-heading">
        <div>
          <h3>{detail.name}</h3>
          <p class="meta">{detail.id}</p>
        </div>

        <div class="context-pack-actions">
          <Button
            type="button"
            variant="secondary"
            size="compact"
            class="lele-secondary-button"
            disabled={mutating}
            onclick={copyPack}
          >
            {$messages.contextPackCopy}
          </Button>

          <Button
            type="button"
            variant="secondary"
            size="compact"
            class="lele-secondary-button"
            disabled={mutating}
            onclick={exportPack}
          >
            {$messages.contextPackExport}
          </Button>

          <Button
            type="button"
            variant="secondary"
            size="compact"
            class="lele-secondary-button"
            disabled={mutating}
            onclick={deletePack}
          >
            {$messages.contextPackDelete}
          </Button>
        </div>
      </div>

      <div class="context-pack-edit-row">
        <label>
          <FieldLabel label={$messages.contextPackRenameLabel} />
          <input bind:value={renameName} />
        </label>

        <Button
          type="button"
          variant="secondary"
          size="compact"
          class="lele-secondary-button"
          disabled={mutating || !renameName.trim()}
          onclick={renamePack}
        >
          {$messages.contextPackRename}
        </Button>

        <Button
          type="button"
          variant="secondary"
          size="compact"
          class="lele-secondary-button"
          disabled={mutating || selectedLessonIds.length === 0}
          onclick={addSelected}
        >
          {$messages.contextPackAddSelected}
        </Button>
      </div>

      {#if selectedLessonIds.length === 0}
        <p class="meta">
          {$messages.contextPackSelectToAdd}
        </p>
      {/if}

      {#if detail.members.length === 0}
        <p class="meta">
          {$messages.contextPackNoMembers}
        </p>
      {:else}
        <ol class="context-pack-members">
          {#each detail.members as member (member.lesson_id)}
            <li
              class:broken={!member.resolved}
              data-testid={`context-pack-member-${member.lesson_id}`}
            >
              <div class="context-pack-member-content">
                <strong>
                  {member.lesson?.title?.trim() || member.lesson_id}
                </strong>

                <span class="meta">{member.lesson_id}</span>

                {#if member.resolved && member.lesson}
                  <span>
                    {lifecycleLabel(member.lesson.lifecycle)}
                  </span>
                {:else}
                  <strong class="broken-reference">
                    {$messages.contextPackBrokenReference}
                  </strong>
                {/if}
              </div>

              <Button
                type="button"
                variant="secondary"
                size="compact"
                class="lele-secondary-button"
                disabled={mutating}
                onclick={() => removeMember(member)}
              >
                {$messages.contextPackRemoveMember}
              </Button>
            </li>
          {/each}
        </ol>
      {/if}
    </div>
  {/if}
</section>

<style>
  .context-packs-manager {
    display: grid;
    gap: var(--space-3);
    margin: var(--space-4) 0;
    padding: var(--space-4);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
  }

  .context-packs-heading h2,
  .context-pack-detail-heading h3 {
    margin: 0;
  }

  .context-pack-list {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-2);
  }

  .context-pack-list-item {
    display: grid;
    gap: var(--space-1);
    padding: var(--space-2) var(--space-3);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-sm);
    background: transparent;
    color: inherit;
    text-align: left;
    cursor: pointer;
  }

  .context-pack-list-item.active {
    border-color: var(--color-accent);
  }

  .context-pack-detail {
    display: grid;
    gap: var(--space-3);
    padding-top: var(--space-3);
    border-top: 1px solid var(--color-border);
  }

  .context-pack-detail-heading,
  .context-pack-edit-row,
  .context-pack-actions {
    display: flex;
    align-items: end;
    gap: var(--space-2);
    flex-wrap: wrap;
  }

  .context-pack-detail-heading {
    justify-content: space-between;
  }

  .context-pack-edit-row label {
    min-width: min(100%, 20rem);
  }

  .context-pack-members {
    display: grid;
    gap: var(--space-2);
    margin: 0;
    padding-left: var(--space-5);
  }

  .context-pack-members li {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: var(--space-3);
  }

  .context-pack-member-content {
    display: grid;
    gap: var(--space-1);
  }

  .context-pack-members li.broken {
    border-left: 3px solid var(--color-warning);
    padding-left: var(--space-2);
  }

  .broken-reference {
    color: var(--color-warning);
  }
</style>
