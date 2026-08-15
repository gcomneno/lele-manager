# LeLe Manager brand foundation and design system

[English](brand-design-system.md) | [Italiano](it/brand-design-system.md)

## Purpose and product promise

LeLe Manager is an open-source, local-first lessons learned workspace: approved
Markdown remains authoritative, while projections, caches, staging data, and ML
models are inspectable derived artifacts. Its promise is **Your local-first
lessons learned workspace**. The interface should make ownership and operational
state legible, never disguise the local product as a hosted SaaS service.

The primary audience is practitioners and small teams who capture, validate,
search, and reuse operational knowledge. The personality is warm, careful,
technically credible, and quietly confident. Write plainly, be specific about
state and consequences, and be friendly without jokes, hype, or artificial urgency.

## Visual principles

- Accumulated knowledge: use card, record, and bookmark forms sparingly to reinforce durable learning.
- Local ownership: show API, data, model, and operation states clearly; do not imply cloud sync, accounts, or invisible automation.
- Operational clarity: hierarchy, contrast, and labels take precedence over decoration. Status always has text as well as color.
- Crafted restraint: warm brown and orange provide recognition; broad blue SaaS palettes, gratuitous gradients, stock art, and decorative motion do not.

The monkey is a supporting historical mascot reference only. It is not the logo,
not a Unicode emoji dependency, and must not compete with product information.

## Identity assets and rules

Repository-owned SVG assets live in `frontend/public/brand/`:

- `lele-manager-lockup.svg` is the full lockup for documentation and spacious product contexts.
- `lele-manager-mark.svg` is the compact knowledge-card mark used in the GUI.
- `giadaware-monkey.svg` is the compact GiadaWare maker mascot used only in the sidebar signature.
- `frontend/public/favicon.svg` is the small application icon.

The mark combines a record card, approval check, and a restrained tail-like lower corner. Keep its clear space at least one quarter of the mark width; do not stretch, rotate, outline, recolor individual parts, or place it on low-contrast surfaces. Prefer the documented orange, brown, or `currentColor` lockup treatment with adequate contrast. All shipped visual assets are original repository assets distributed under the repository licensing terms. They contain no embedded raster images, external references, scripts, or remote fonts.

## Typography and layout

Use the local system sans stack `ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif`. Use the system monospace stack only for IDs, code, and technical logs. The base size is 16px, with 12px, 14px, 16px, 18px, and 22px steps; use medium, semibold, and bold weights and 1.2/1.5 line heights.

Spacing tokens are 4, 8, 12, 16, 20, 24, and 32px. Controls are 40px high; radii are 6px, 10px, 14px, and pill. Use one quiet elevation level (`0 2px 8px` at 8% brown) only for raised cards. Main content is capped at 1216px and layouts collapse near 800–900px.

## Color and tokens

The implementation in `frontend/src/app.css` is the semantic token contract. It separates raw palette (`--color-brand-*`) from roles: canvas, surface, surface-raised, text, text-muted, border, divider, action, focus, and status. Primary action is brand-600 `#b75222`; the legacy accent alias resolves to it. The accessible status roles are success `#176b3a`, warning `#915500`, danger `#ad261c`, and info `#245e8f`, each with a companion surface. Canvas is `#f7f4ee`, surface is white, text is `#241c16`, and border is `#d8d0c3`.

Existing aliases (`--bg`, `--surface`, `--border`, `--text`, `--muted`, `--accent`, `--ok`, `--warn`, `--err`, and related sidebar/radius/shadow tokens) are temporary migration compatibility names. New work should use semantic `--color-*` roles; aliases should disappear after affected components migrate.

## Components and feedback

Giada UI is the reusable authority for generic buttons, panels, surfaces, field presentation, action groups, and status feedback. Consumers use its documented public entry points and `--giu-*` theme hooks rather than copying component internals.

Native inputs, selects, and textareas remain product-owned until a matching Giada UI input contract exists; their colors, borders, focus, and opt-in invalid state use LeLe Manager semantic tokens. Existing runtime labels remain Italian; runtime English/Italian localization is delivered separately by #154.

Legacy selectors such as `.btn`, `.card`, `.actions`, `.status`, `.empty-state`, and the feedback classes remain temporary compatibility code only for domain-heavy or not-yet-migrated surfaces, notably Timeline, System, TritaLeLe, the shell creation CTA, and domain cards or trees. They are not a second reusable design system and must not be used for new generic presentation.

Use a concise status word or message beside every status color. Busy controls must keep their purpose visible and use a progress label such as “Saving…”. Destructive actions need the destructive treatment and an existing confirmation surface where the flow already provides one; this issue does not add new dialogs.

## Icons, accessibility, and motion

Prefer original inline SVG or repository SVG assets; icons communicate a single known action and must not be the only label for an unfamiliar action. Decorative SVGs are hidden from assistive technology; meaningful SVGs include a title and description. No icon library, font CDN, or remote runtime asset is used.

Keyboard focus uses a visible blue 3px focus ring, including controls, navigation, and disclosure summaries. Text and controls use the documented high-contrast roles; status is never color-only. Transitions are limited to 120ms/180ms feedback and are essentially disabled by `prefers-reduced-motion`. These rules support accessible use but do not claim formal conformance without separate measurement.

## Brand rules versus implementation details

This document defines the maintained brand contract: product promise, personality, semantic roles, asset ownership, accessibility principles, and component behavior. Exact DOM structure, route-specific spacing, temporary CSS aliases, and build hashes are implementation details and may change without changing the brand. Historical GUI documents remain historical records and are not retroactively rewritten to this language.

## Product language and navigation

Navigation labels describe the destination or activity available to a person, not
the name of the underlying implementation module. Runtime product language is
currently Italian. Exact internal route identifiers (for example `browse`,
`timeline`, `tritalele`, and `ops`) remain implementation details: they preserve
route and API contracts but do not dictate the wording shown in the product.

## Explicit non-goals

This foundation does not introduce dark mode, a navigation redesign, dashboard, Settings or About routes, lifecycle commands, hosted accounts, telemetry, cloud storage, remote fonts or assets, external icon libraries, raster generation, or animated decoration. It does not change Markdown authority, API/route contracts, or business behavior.

## Product signature

On desktop, the sidebar ends with a restrained GiadaWare maker signature:
the repository-owned monkey mascot beside “GiadaWare™” and “Software open
source”. The sidebar is pinned to the viewport, so the signature remains
visible on both short and long pages.

The runtime brand lockup pairs `LeLe Manager` with the tagline
`Your Managed Second Brain`. The product name remains visually dominant, while
explicit spacing and line height prevent overlap inside the narrow brand
column.

The primary creation action keeps the accessible name “Nuova LeLe”. Its
visible presentation uses “+ Nuova” followed by the GiadaWare monkey and a
small speech balloon containing “LeLe”. The mascot remains subordinate to the
LeLe Manager product mark.

## Giada UI consumption

Giada UI is the authority for reusable presentation, accessibility behavior,
and generic interaction contracts. LeLe Manager owns product identity, routes,
domain workflows, wording, composition, and theme values.

The frontend consumes the immutable vendored artifact
`giadaware-ui-components-0.0.0.tgz`, generated from Giada UI commit
`b088653cba3c940ff6b4baf3b396a109cb04e8b7`, with SHA-256
`88b5cc12417fa911f5a885b9e554abd198f29a4322f0ac8d1fad823da16e2c7d`.

Direct adoption covers Browse, Statistics, Vault, Detail, Editor, and the
generic control and feedback surface of Duplicates. Domain-specific lesson
cards, similarity rows, duplicate-comparison records, the Vault tree, and
workflow orchestration remain local because their contracts belong to
LeLe Manager rather than Giada UI.

The dependency uses a local `file:` reference and requires no registry or
runtime network access. Product colors and spacing are mapped through documented
`--giu-*` customization properties. Missing reusable primitives must be
implemented and validated upstream in Giada UI before consumer adoption.
