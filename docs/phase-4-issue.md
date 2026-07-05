# Fase 4 — Explain similarity, export Markdown, E2E smoke

> **Tracking locale** — GitHub Issues disabilitate sul repo (`has_issues: false`).  
> Quando riattivate, usare questo file per aprire l'issue su GitHub.  
> **Epic parent:** [#95](https://github.com/gcomneno/lele-manager/issues/95)  
> **Milestone:** [v2.0](https://github.com/gcomneno/lele-manager/milestone/3)  
> **Target release:** v1.9.0  
> **Baseline:** v1.8.0

---

## Contesto

Sub-issue dell'epic GUI **#95**.

Fasi 0–3 completate:

| Fase | Contenuto | Release |
|------|-----------|---------|
| 0 | Design (`docs/gui-design.md`) | — |
| 1 | GUI-alpha (Browse, Detail, Editor, Ops) | v1.6.0 |
| 2 | Vault write-back, tree, save | v1.7.0 |
| 3 | Stats, Timeline, deprecate `/ui` | v1.8.0 |

Questa fase porta la GUI da “funziona” a “mi fido mentre scrivo”: capire *perché* una LeLe è simile, esportare risultati, e non rompere l'UI in silenzio.

---

## Obiettivo

1. **Explain similarity** in GUI ([#90](https://github.com/gcomneno/lele-manager/issues/90))
2. **Export risultati ricerca → Markdown** ([#87](https://github.com/gcomneno/lele-manager/issues/87))
3. **Playwright smoke E2E** sui flussi critici GUI

---

## Scope

### 4.1 Explain similarity in GUI (#90)

- [x] Usare `explain=true` su `/similar`, `/editor/suggest`, `/lessons/{id}/similar`
- [x] Pannello **“Perché simile?”** in `Detail` e `Editor` (rank, score, preview)
- [x] Mostrare metadati utili: topic, tag overlap (se disponibili in explain meta)
- [x] CLI: opzionale `lele similar --explain` / `lele suggest --explain`
- [x] Test API + snapshot minimi risposta explain

**Non in scope:** LLM/RAG per spiegazioni in linguaggio naturale.

### 4.2 Export search → Markdown (#87)

- [x] API: `POST /export/search` → contenuto Markdown
  - input: stesso payload di `POST /lessons/search` (+ opzioni formato)
  - output: `text/markdown` o JSON `{ "markdown": "..." }`
- [x] GUI: bottone **Esporta** in Browse (e opz. Timeline)
- [x] CLI: `lele export --search "pytest" --topic python -o results.md`
- [x] Test: export con filtri, encoding UTF-8, frontmatter opzionale

### 4.3 Playwright E2E smoke

- [x] Setup `frontend/` — `@playwright/test`, script `npm run test:e2e`
- [x] CI: avvia API test fixture + build GUI + 3 smoke:
  - [x] browse → click risultato → detail
  - [x] editor: digita testo → suggest panel risponde (mock o dataset fixture)
  - [x] stats/timeline caricano senza 500
- [x] Documentare in README sezione “Test E2E”

**Non in scope:** copertura E2E completa di ogni vista.

### 4.4 Documentazione & release

- [x] Aggiornare `docs/gui-design.md` (sezione Fase 4)
- [x] `CHANGELOG.md` + bump `1.9.0`
- [x] README: explain + export + E2E

---

## Fuori scope (Fase 5+)

- Dedup / near-duplicate review ([#85](https://github.com/gcomneno/lele-manager/issues/85))
- Knowledge doctor ([#84](https://github.com/gcomneno/lele-manager/issues/84))
- TritaLeLe pipeline ([#82](https://github.com/gcomneno/lele-manager/issues/82), [#94](https://github.com/gcomneno/lele-manager/issues/94))
- Tauri desktop wrapper
- PyPI publish / pin dipendenze (issue separata o tech-debt)

---

## Acceptance criteria (Fase 4 done)

- [x] In GUI vedo *perché* una LeLe è simile (non solo il numero)
- [x] Posso esportare una ricerca Browse in `.md` utilizzabile in Obsidian/vault
- [x] CI verde con smoke Playwright
- [x] `pytest` resta verde (nessuna regressione API)
- [x] Issue #90 e #87 chiudibili (o chiuse con riferimento a questa)

---

## Dipendenze

- **Parent:** #95
- **Milestone:** v2.0
- **Correlate:** #90, #87, #85 (fase 5), #84
- **Baseline API/GUI:** `/app/`, vault save, stats/timeline (`GET /stats/summary`, `GET /stats/timeline`)

---

## Stima indicativa

| Blocco | Ore |
|--------|-----|
| Explain in GUI + API wiring | 4–6h |
| Export Markdown API + GUI | 4–6h |
| Playwright smoke + CI | 4–6h |
| **Totale** | **~12–18h** |

---

## Aprire l'issue su GitHub (quando Issues sono riattivate)

### 1. Riattiva Issues

GitHub → **Settings** → **General** → **Features** → **Issues** → Save.

```bash
gh api -X PATCH repos/gcomneno/lele-manager -f has_issues=true
```

### 2. Crea l'issue

```bash
cd ~/Progetti/lele-manager

gh issue create --repo gcomneno/lele-manager \
  --title "Fase 4 — Explain similarity, export Markdown, E2E smoke" \
  --label "enhancement" --label "v2" --label "ux" --label "api" --label "tests" \
  --milestone "v2.0" \
  --body-file docs/phase-4-issue.md
```

Poi aggiungi un commento su #95: `Fase 4 tracciata in #<numero-issue>`.

---

*La scimmia vuole capire il 0.84 prima di fidarsi del suggerimento. Giusto.*
