# LeLe Manager — Roadmap e stato attuale

[English](ROADMAP.md) | [Italiano](ROADMAP.it.md)

> Knowledge base personale per lesson learned testuali:
> vault Markdown → projection store / JSONL → ML (topic e similarità) →
> API FastAPI e GUI.

## 1. Obiettivo del progetto

LeLe Manager è il motore centrale per le lesson learned personali:

- le lesson vengono scritte come file Markdown organizzati per topic;
- LeLe Manager le importa, valida, normalizza ed espone per:
  - ricerca full-text e tramite filtri;
  - classificazione per topic;
  - suggerimenti di lesson simili;
  - revisione, export e integrazioni downstream.

L'obiettivo è uno strumento local-first stabile per l'uso quotidiano, con dati
recuperabili e una base ML capace di evolvere senza diventare la fonte
autorevole.

## 2. Step originali e avanzamento

La roadmap originale comprendeva:

1. **Setup Python e tooling** — ambiente, struttura del progetto e primi
   strumenti CLI.
2. **Dati e analisi esplorativa** — formato delle lesson, storage, ingestione e
   prime analisi.
3. **ML classico** — classificazione topic e similarità basata su TF-IDF.
4. **Pipeline e feature engineering** — feature condivise, pipeline
   scikit-learn e strumenti CLI ML.
5. **FastAPI e capstone end-to-end** — endpoint API, script di sviluppo e
   successiva integrazione GUI.

### 2.1 Fondamenta completate

- **Setup Python e tooling**
  - layout del package `src/lele_manager/`;
  - `pyproject.toml`, extra di sviluppo e flusso ambiente virtuale;
  - primi strumenti CLI come `csv2json` e `file_watcher`;
  - hook pre-commit per whitespace, YAML e Ruff.

- **Dati e ingestione delle lesson**
  - campi principali: `id`, `text`, `topic`, `source`, `importance`, `tags`,
    `date` e `title`;
  - vault Markdown con frontmatter YAML;
  - dataset di compatibilità JSONL;
  - ingestione da CSV e altre fonti;
  - chunking deterministico delle fonti grezze e staging candidati TritaLeLe.

- **ML classico**
  - `train_topic_model(df)` con TF-IDF e `LogisticRegression`;
  - pipeline scikit-learn serializzata in `models/topic_model.joblib`;
  - `LessonSimilarityIndex`;
  - similarità da testo e da ID;
  - backend di similarità LSA opzionale.

- **Pipeline di feature condivisa**
  - `LessonFeatureExtractor`;
  - TF-IDF del testo, numero caratteri, numero parole e `importance`;
  - `TopicModelConfig`, `build_topic_pipeline` ed errori di training robusti;
  - comportamento condiviso tra classificazione topic e similarità.

- **LeLe Vault**
  - root configurabile tramite `LELE_VAULT_DIR`;
  - ingresso importer tollerante e validazione canonica rigorosa con
    `lele doctor`;
  - verifica canonica di `topic` e `id` rispetto al percorso relativo;
  - gestione duplicati con `overwrite`, `skip` ed `error`;
  - hash SHA-256 del frontmatter;
  - serializzazione robusta delle date YAML;
  - write-back Markdown e flussi di refresh del vault.

- **FastAPI e script di sviluppo**
  - endpoint principali per lesson, ricerca, training, similarità, duplicati,
    analytics, export, vault e operazioni;
  - workflow versionato dei candidati TritaLeLe sotto `/api/v1/tritalele`;
  - `scripts/lele-api-dev.sh`;
  - `scripts/lele-api-refresh.sh`;
  - serving statico della GUI e composizione applicativa.

- **GUI web**
  - SPA Svelte con Browse, Detail, Editor, Vault, Ops, Timeline e Stats;
  - suggerimenti live e similarità spiegata;
  - export Markdown;
  - write-back nel vault;
  - smoke test E2E Playwright.

- **Confine projection store**
  - port tipizzato indipendente dal backend;
  - snapshot coerenti e immutabili;
  - ordinamento, conteggi e generazione del contenuto deterministici;
  - pubblicazione validata e atomica dell'intero snapshot;
  - adapter di compatibilità JSONL;
  - facade esplicita per il legacy append.

## 3. Stato attuale del prodotto

LeLe Manager fornisce oggi:

- un vault Markdown canonico per l'authoring delle lesson approvate;
- un knowledge doctor locale rigoroso;
- una proiezione JSONL derivata usata dai flussi di compatibilità e ML;
- classificazione topic e similarità su dati reali;
- report di duplicati esatti e quasi-duplicati;
- un server FastAPI;
- il client CLI `lele` orientato alle API;
- una GUI Svelte;
- flussi TritaLeLe per ingestione fonti grezze, revisione candidati e
  approvazione;
- validazione package PKPS v1 e staging tramite il confine candidati TritaLeLe,
  senza scritture di vault o proiezioni prima dell'approvazione;
- test deterministici sui confini domain, storage, API, CLI e GUI.

Il progetto è utilizzabile come strumento personale in produzione, mentre la
migrazione storage e alcune pulizie architetturali restano attività aperte.

## 4. Lavoro prodotto e qualità completato

### 4.1 Test automatici

La copertura comprende:

- comportamento dell'importer e riparazione frontmatter;
- validazione canonica del vault e ID duplicati;
- successo e fallimenti del training topic model;
- equivalenza ed edge case del servizio di similarità;
- health API, ricerca, dettaglio, similarità, analytics, export e vault;
- contratto projection store;
- ingestione, review, approval, CLI e API TritaLeLe;
- build GUI e smoke test Playwright.

### 4.2 Ricerca avanzata

- `POST /lessons/search`;
- filtri per topic, source, importance e testo;
- record normalizzati e ordinamento deterministico;
- consumer CLI e GUI.

### 4.3 CLI orientata alle API

- `lele search`;
- `lele show`;
- `lele similar`;
- `lele train-topic`;
- `lele suggest`;
- `lele export`;
- `lele duplicates`;
- `lele doctor`;
- comandi candidati TritaLeLe;
- `lele pkps import PACKAGE_PATH` per package lesson GYTE versionati;
- configurazione `LELE_API_URL` dove applicabile.

### 4.4 Documentazione e igiene release

- Semantic Versioning;
- `CHANGELOG.md`;
- licenza MIT;
- guida contributor;
- politica documentale bilingue con inglese canonico;
- mirror inglese/italiano mantenuti per i documenti principali utente e
  contributor;
- test documentali mirati;
- workflow release e packaging.

Resta da definire il pinning delle dipendenze o una strategia lockfile
giustificata.

## 5. Direzione architetturale attiva

### 5.1 Contenuto canonico e proiezioni

La separazione obiettivo è:

- **vault Markdown:** contenuto autorevole delle lesson approvate;
- **projection store:** vista applicativa interrogabile;
- **JSONL:** snapshot derivato per interoperabilità, fixture, export e ML;
- **modelli ML:** artefatti rigenerabili legati a una generazione del dataset.

L'adapter corrente resta JSONL per compatibilità. SQLite è il backend locale
interrogabile previsto dopo il lavoro di parità, migrazione e riconciliazione
descritto da [ADR 0001](docs/adr/0001-storage-backend.md), fonte tecnica
canonica inglese.

### 5.2 Ingestione TritaLeLe

Il flusso obiettivo è:

```text
source material
  → deterministic chunks
  → staged candidates
  → explicit human review
  → approval
  → canonical Markdown vault
  → projection refresh
  → export and ML derivatives
```

I candidati non sono lesson approvate. Restano isolati dal vault canonico e
dal dataset ML fino al completamento di un'approvazione esplicita.

### 5.3 Personal Knowledge Publishing System (PKPS)

PKPS v1 è un confine locale package completato: GYTE esporta un package lesson
versionato, mentre LeLe lo valida e mette in staging un ordinario candidato
TritaLeLe. La provenienza del package è immutabile e fluisce nell'approvazione;
identità canonica, gestione duplicati e pubblicazione restano decisioni di
LeLe. Consultare il [contratto package PKPS](docs/it/pkps-package.md).

### 5.4 Documentazione

L'inglese è canonico e predefinito. L'italiano è ufficialmente mantenuto per le
coppie elencate nella
[politica documentale](docs/it/documentation-policy.md).

Record storici, artefatti generati e fonti tecniche selezionate sono esclusi
soltanto tramite classificazione e motivazione esplicite.

## 6. Priorità pratiche

1. **Mantenere stabile il sistema corrente**
   - preservare contratti domain e storage deterministici;
   - mantenere verdi lint, typing, test, packaging, security ed E2E;
   - sincronizzare le coppie documentali.

2. **Completare l'evoluzione storage**
   - riconciliare record presenti solo nel vault o solo in JSONL;
   - introdurre e validare l'adapter SQLite;
   - dimostrare parità con il backend di compatibilità JSONL;
   - esporre esplicitamente lo stato stale della proiezione;
   - effettuare il cutover gradualmente senza creare una seconda autorità.

3. **Completare l'integrazione prodotto TritaLeLe**
   - collegare il workflow candidati alla GUI;
   - preservare review e approval esplicite;
   - rendere visibili provenance e recupero dai fallimenti;
   - evitare la promozione diretta dei candidati nei dataset canonici.

4. **Migliorare la manutenibilità**
   - dividere i moduli FastAPI sovradimensionati in router e servizi focalizzati;
   - definire pinning dipendenze o politica lockfile;
   - mantenere espliciti i confini tra authoring, sincronizzazione, proiezione,
     export e ML.

5. **Espandere le integrazioni quando giustificato**
   - integrazioni editor come VS Code o Obsidian;
   - consumer esterni per quiz e review;
   - embedding o ranking più ricchi solo dopo benefici misurabili;
   - strumenti analitici come DuckDB solo per workload dimostrati.

## 7. Ricerca nice-to-have

- embedding densi alternativi o retrieval ibrido;
- ranking personalizzato della priorità di revisita;
- explainability più ricca per similarità e duplicati;
- flussi nativi negli editor;
- contratti versionati per consumer esterni;
- analytics su snapshot esportati più grandi.

Questi elementi non devono indebolire recuperabilità local-first, comportamento
deterministico o autorità del contenuto Markdown revisionato.

## 8. Non priorità esplicite

Il progetto attuale non necessita di:

- database distribuito;
- servizio document store remoto;
- approvazione automatica non revisionata dei candidati;
- traduzione automatica opaca;
- piattaforma documentale pesante;
- infrastruttura sproporzionata rispetto al workload personale local-first.
