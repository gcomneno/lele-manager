# LeLe Manager 🐒 — Lesson-Learned Manager

[English](README.md) | [Italiano](README.it.md)

[![Security](https://github.com/gcomneno/lele-manager/actions/workflows/security.yml/badge.svg)](https://github.com/gcomneno/lele-manager/actions/workflows/security.yml)
[![CI](https://github.com/gcomneno/lele-manager/actions/workflows/ci.yml/badge.svg)](https://github.com/gcomneno/lele-manager/actions/workflows/ci.yml)

LeLe Manager è un sistema local-first end-to-end per raccogliere, validare,
cercare e riutilizzare lesson learned testuali.

Una lesson combina contenuto Markdown e metadati stabili. LeLe Manager può:

- raccogliere lesson tramite flussi Markdown, CLI, GUI e API;
- cercare per testo, topic, fonte, data, importanza e tag;
- individuare duplicati esatti, quasi-duplicati e lesson correlate;
- addestrare un topic model e riutilizzare la stessa pipeline di feature per la
  similarità;
- preservare un vault Markdown ispezionabile pubblicando dataset e modelli
  derivati.

L'inglese è la lingua canonica della documentazione. Consultare la
[politica linguistica](docs/it/documentation-policy.md).

## Quality gate

- **CI:** `ruff check .`, `mypy src/lele_manager`, `pytest`, packaging smoke e
  smoke E2E Playwright con Python 3.12 e Node.js 22.
- **Security:** `pip-audit` e `bandit` tramite GitHub Actions.
- **pre-commit:** pulizia whitespace e fine file, `check-yaml` e `ruff`.
- **Documentazione:** coppie bilingui obbligatorie, selettori lingua reciproci,
  navigazione root nella stessa lingua e link relativi.

Eseguire i controlli documentali con:

```bash
pytest tests/test_documentation.py
```

## Collegamenti del progetto

- Roadmap completa: [ROADMAP.it.md](ROADMAP.it.md)
- Changelog: [CHANGELOG.md](CHANGELOG.md)
- Guida contributor: [CONTRIBUTING.it.md](CONTRIBUTING.it.md)
- Politica documentale:
  [docs/it/documentation-policy.md](docs/it/documentation-policy.md)
- Contratto projection store:
  [docs/it/projection-store.md](docs/it/projection-store.md)

- Contratto consumer PKPS di LeLe Manager:
  [docs/it/pkps-package.md](docs/it/pkps-package.md)

- Manuale della GUI: [docs/it/gui-user-guide.md](docs/it/gui-user-guide.md)

## Obiettivi principali

- Raccolta veloce delle lesson tramite CLI e API.
- Metadati stabili: data, fonte, topic, importanza, tag e titolo.
- Ricerca full-text e tramite filtri.
- Suggerimenti di similarità durante scrittura e revisione.
- Authoring local-first in Markdown con JSONL e artefatti ML derivati.
- Automazione progressiva di classificazione e ranking senza rendere opachi o
  difficili da recuperare i dati dell'utente.

## Stack tecnico

- Python **3.12** in CI; testato anche con Python 3.13.
- `pandas` e `numpy` per l'elaborazione dati.
- `scikit-learn` per TF-IDF, classificazione e similarità.
- FastAPI e Uvicorn per l'API HTTP.
- Svelte, TypeScript e Vite per la GUI web.
- Un port projection-store indipendente dal backend con JSONL come adapter di
  compatibilità corrente. SQLite resta un obiettivo di migrazione successivo;
  vedere il [contratto projection store](docs/it/projection-store.md) e
  [ADR 0001](docs/adr/0001-storage-backend.md), fonte tecnica canonica inglese.

## Installazione e avvio

Per il normale utilizzo utente, scaricare da GitHub Releases il pacchetto nativo
per il proprio sistema operativo, estrarlo e avviare **LeLe-Manager**. I
pacchetti nativi per Linux, macOS e Windows sono autosufficienti: non richiedono
Python, Node.js, npm, un ambiente virtuale o un checkout del repository.

Al primo avvio LeLe Manager prepara fuori dalla directory di installazione le
directory applicative locali e il vault Markdown predefinito, avvia
l'applicazione FastAPI locale, attende che sia pronta e apre `/app/` nel browser
predefinito. I dati utente persistenti sopravvivono quindi alla sostituzione o
all'aggiornamento della cartella applicativa estratta.

Su Linux l'archive include anche `./install.sh` per un'installazione locale
utente esplicita. L'installer colloca l'app nativa in
`${XDG_DATA_HOME:-~/.local/share}/lele-manager/install/app` e crea il launcher
stabile `~/.local/bin/lele-manager`. La directory `lele-manager` resta lo
spazio dei dati runtime persistenti; solo `install/` e' gestita e sostituibile
dall'installer. L'archive estratto resta utilizzabile in modo portabile.

Ogni archive nativo include `LEGGIMI_PRIMA.txt` con istruzioni di primo avvio
specifiche per la piattaforma.

Per utenti Python e power user, LeLe Manager è pubblicato anche su PyPI. È
consigliata l'installazione come applicazione isolata tramite `pipx`:

```bash
pipx install lele-manager
```

Il pacchetto PyPI espone sia `lele-manager` per avviare l'applicazione locale,
sia `lele` per la CLI. I pacchetti nativi delle GitHub Release restano il
percorso di installazione consigliato per il normale utilizzo utente.

Per lo sviluppo dai sorgenti, clonare il repository e creare un ambiente
virtuale:

```bash
git clone git@github.com:gcomneno/lele-manager.git
cd lele-manager

python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

pip install -e .[dev]
```

Eseguire controlli statici e test Python:

```bash
ruff check .
mypy src/lele_manager
pytest
```

## Primi strumenti CLI

Gli strumenti originali basati sui moduli restano disponibili:

```bash
# Converti un file CSV di lesson in JSON
python -m lele_manager.cli.csv2json samples/input.csv samples/output.json

# Monitora una directory per nuovi file
python -m lele_manager.cli.file_watcher data

# Importa lesson Markdown con frontmatter YAML da un vault
python -m lele_manager.cli.import_from_dir \
  "$LELE_VAULT_DIR" \
  data/lessons.jsonl \
  --on-duplicate overwrite \
  --default-source note \
  --default-importance 3 \
  --write-missing-frontmatter
```

## Flusso rapido tramite CLI legacy

Aggiungere una lesson:

```bash
python -m lele_manager.cli.add_lesson \
  --text "With a src layout I must configure PYTHONPATH or use a conftest for pytest." \
  --source chatgpt \
  --topic python \
  --importance 4 \
  --tags "python,pytest,tooling"
```

Campi principali:

- `text`: contenuto della lesson;
- `source`: origine come `chatgpt`, `book`, `experiment` o `note`;
- `topic`: topic principale come `python`, `ml`, `linux` o `writing`;
- `importance`: importanza numerica, normalmente da 1 a 5;
- `tags`: tag separati da virgola.

Elencare le lesson:

```bash
python -m lele_manager.cli.list_lessons --limit 10
```

## LeLe Vault: Markdown e frontmatter YAML

LeLe Manager supporta un vault Markdown come superficie di authoring delle
lesson approvate.

Il flusso tipico è:

- scrivere e organizzare file `.md` sotto una directory come `~/LeLeVault`;
- importarli e normalizzarli in `data/lessons.jsonl`;
- addestrare o aggiornare i modelli derivati;
- interrogarli tramite CLI, API o GUI.

L'ID della lesson vive nel frontmatter. Nel contratto canonico del vault,
identità e collocazione sono allineate: `topic` corrisponde alla prima
directory relativa e `id` al percorso relativo senza `.md`. Rinominare o
spostare un file canonico richiede quindi di aggiornare i metadati di identità.

### Struttura consigliata del vault

```text
LeLeVault/
  python/
    2025-11-20.pytest-src-layout.md
  cpp/
    2025-11-20.cin-vs-getline.md
  linux/
    2025-11-20.rsync-dry-run-backup.md
  writing/
    2025-11-22.show-dont-tell.md
```

Convenzioni soft:

- nome directory = topic principale;
- nome file = `YYYY-MM-DD.slug.md`;
- nello slug usare `.` e `-`, non `_`.

### Schema di ingresso dell'importer

Una lesson può iniziare con frontmatter YAML:

```markdown
---
id: cpp/2025-11-20.cin-vs-getline
topic: cpp
source: book
importance: 4
tags: [cpp, io, strings]
date: 2025-11-20
title: "LL-5 — std::cin vs std::getline"
---
```

L'importer accetta uno schema di ingresso tollerante:

- `id` è opzionale e può essere derivato dal percorso relativo;
- `topic` può provenire dal frontmatter, da `--default-topic` o dalla directory;
- `source` identifica l'origine;
- `importance` è normalmente un intero da 1 a 5;
- `tags` può essere una lista o una stringa separata da virgole;
- `date` usa una forma ISO-like e può essere derivata dal nome file;
- `title` è opzionale per l'ingresso dell'importer.

LeLe Manager calcola anche `frontmatter_hash` per diagnostica e versionamento.
L'identità resta `id`.

La tolleranza dell'importer non implica che ogni file importabile soddisfi il
contratto canonico di `doctor`.

### Schema canonico validato da `lele doctor`

`lele doctor` richiede tutti e sette i campi:

- `id`;
- `topic`;
- `source`;
- `importance`;
- `tags`;
- `date`;
- `title`.

`id`, `topic`, `source` e `title` devono essere stringhe non vuote.
`importance` deve essere un intero da 1 a 5. `date` deve essere una data valida
`YYYY-MM-DD`. `tags` deve essere una lista non vuota di stringhe non vuote.
Anche il body Markdown deve essere non vuoto.

Quando è disponibile un contesto vault, i file selezionati devono restare
dentro il vault dopo la risoluzione dei symlink. `topic` deve corrispondere alla
prima directory relativa e `id` all'intero percorso relativo senza `.md`.

### Validare un vault

```bash
# Valida ricorsivamente il vault configurato tramite LELE_VAULT_DIR
lele doctor

# Valida un vault specifico
lele doctor --vault /path/to/LeLeVault

# Valida file selezionati usando il vault configurato come contesto
lele doctor "$LELE_VAULT_DIR/python/2026-07-13.example.md"

# Produce JSON adatto agli script
lele doctor --json
```

`lele doctor` legge il Markdown senza riscrivere intenzionalmente contenuto,
timestamp o permessi. L'accesso filesystem può comunque aggiornare l'access
time.

Exit code:

- `0`: report valido;
- `1`: errori di validazione;
- `2`: errore operativo o di utilizzo, compresa la selezione di un file esterno
  al vault configurato.

### Importare Markdown in JSONL

```bash
python -m lele_manager.cli.import_from_dir \
  "$LELE_VAULT_DIR" \
  data/lessons.jsonl \
  --on-duplicate overwrite \
  --default-source note \
  --default-importance 3 \
  --write-missing-frontmatter
```

L'importer:

- cerca ricorsivamente file `.md`;
- legge frontmatter e body;
- deriva un ID mancante dal percorso relativo;
- deriva o normalizza topic, tag, importanza e data;
- calcola `frontmatter_hash`;
- costruisce in memoria una mappa `id -> record`;
- pubblica uno snapshot JSONL completo con un record per ID unico.

`--write-missing-frontmatter` ripara soltanto campi di ingresso mancanti o non
validi. Un frontmatter completo e valido non viene riscritto soltanto per
normalizzare l'output JSONL.

Il comportamento sui duplicati si seleziona con:

- `--on-duplicate overwrite`: vince l'ultimo record scandito;
- `--on-duplicate skip`: vince il primo record;
- `--on-duplicate error`: arresto al primo ID duplicato.

### Flusso di refresh consigliato

1. Scrivere o organizzare le lesson Markdown in `$LELE_VAULT_DIR`.
2. Importare il vault.
3. Addestrare il topic model.
4. Interrogare l'archivio.

```bash
python -m lele_manager.cli.import_from_dir \
  "$LELE_VAULT_DIR" \
  data/lessons.jsonl \
  --on-duplicate overwrite \
  --write-missing-frontmatter

python -m lele_manager.cli.train_topic_model \
  --input data/lessons.jsonl \
  --output models/topic_model.joblib \
  --overwrite

python -m lele_manager.cli.suggest_similar \
  --input data/lessons.jsonl \
  --model models/topic_model.joblib \
  --text "When std::cin reads a string, input is truncated at whitespace" \
  --top-k 5 \
  --min-score 0.1
```

## Topic model e similarità

`train_topic_model(df)` costruisce una pipeline scikit-learn con feature TF-IDF
e `LogisticRegression`.

`LessonFeatureExtractor` combina:

- feature TF-IDF dal testo della lesson;
- lunghezza in caratteri;
- numero di parole;
- `importance`, quando disponibile.

La stessa rappresentazione delle feature supporta classificazione del topic e
similarità.

`LessonSimilarityIndex.from_lessons(...)` e
`LessonSimilarityIndex.from_topic_pipeline(...)` costruiscono l'indice di
similarità. `most_similar(query_text, top_k)` restituisce ID e punteggi coseno.

### Addestramento tramite CLI del modulo

```bash
python -m lele_manager.cli.train_topic_model \
  --input data/lessons.jsonl \
  --output models/topic_model.joblib \
  --overwrite
```

L'ingresso JSONL deve contenere almeno `text` e `topic`.

```json
{"id": "89c6bca8-941b-4a93-a7ca-a35e584ae5ec",
 "text": "With a src layout I must manage PYTHONPATH or use a conftest for pytest.",
 "topic": "python",
 "source": "chatgpt",
 "importance": 4,
 "tags": ["python", "pytest", "tooling"]}
```

La pipeline completa viene salvata in `models/topic_model.joblib`.

### Trovare lesson simili tramite CLI del modulo

Query da testo libero:

```bash
python -m lele_manager.cli.suggest_similar \
  --input data/lessons.jsonl \
  --model models/topic_model.joblib \
  --text "With a src layout I must configure PYTHONPATH or use a conftest for pytest." \
  --top-k 5 \
  --min-score 0.1
```

Query tramite ID di una lesson esistente:

```bash
python -m lele_manager.cli.suggest_similar \
  --input data/lessons.jsonl \
  --model models/topic_model.joblib \
  --from-id "89c6bca8-941b-4a93-a7ca-a35e584ae5ec" \
  --id-column id \
  --top-k 5 \
  --min-score 0.1
```

L'output comprende ID della lesson, punteggio di similarità e anteprima del
testo.

## Sicurezza e pre-commit

Il workflow security viene eseguito su push, pull request e con cadenza
settimanale:

- `pip-audit` controlla le dipendenze Python;
- `bandit` controlla il codice Python sotto `src/`.

Installare gli hook pre-commit locali con:

```bash
pip install pre-commit
pre-commit install
```

La configurazione fornisce pulizia whitespace e newline finale, validazione
YAML e controlli Ruff.

## Dati e modelli locali

- I dati personali delle lesson vivono sotto `data/`.
- I modelli addestrati vivono sotto `models/`.
- Entrambe le directory sono escluse dal versionamento.

Il repository pubblico non contiene quindi vault personale, dataset derivato
o modelli addestrati.

## Script di utilità

### Refresh completo: `scripts/lele-api-refresh.sh`

Il refresh di sviluppo completo:

1. importa `$LELE_VAULT_DIR` in `data/lessons.jsonl`;
2. riaddestra `models/topic_model.joblib`;
3. avvia il server FastAPI con Uvicorn `--reload`.

```bash
cd ~/Projects/lele-manager
export LELE_VAULT_DIR=/home/user/LeLeVault
./scripts/lele-api-refresh.sh
```

### Solo API: `scripts/lele-api-dev.sh`

Usare questo script quando dataset e modello sono già pronti:

```bash
cd ~/Projects/lele-manager
./scripts/lele-api-dev.sh
```

Lo script individua la root del progetto, attiva `.venv`, controlla Uvicorn e
avvia il server su `http://127.0.0.1:8000`.

## API FastAPI

Gli endpoint principali comprendono:

- `GET /health`;
- `GET /lessons`;
- `GET /lessons/{id}`;
- `GET /lessons/{id}/similar`;
- `GET /duplicates`;
- `POST /similar`;
- `POST /editor/suggest`;
- `POST /export/search`;
- `GET /stats/summary`;
- `GET /stats/timeline`;
- `POST /train/topic`;
- `POST /lessons/search`.

Gli endpoint di similarità accettano `explain=true`, dove documentato, per
includere rank, topic e metadati sui tag condivisi.

Il workflow versionato dei candidati TritaLeLe è esposto sotto
`/api/v1/tritalele`.

Avviare il flusso completo con:

```bash
./scripts/lele-api-refresh.sh
```

Oppure soltanto l'API con:

```bash
./scripts/lele-api-dev.sh
```

## GUI web

Per il percorso completo di avvio, uso quotidiano, backup, ripristino e
troubleshooting vedere il
[manuale della GUI](docs/it/gui-user-guide.md).

Costruire il frontend Svelte e avviare l'API:

```bash
./scripts/build-gui.sh
./scripts/lele-api-dev.sh
# Aprire http://127.0.0.1:8000/app/
```

Viste disponibili:

| Vista | Scopo |
|---|---|
| **Dashboard** | Stato dello spazio di lavoro, riepilogo bounded e prossime azioni utili |
| **Browse** | Ricerca avanzata, filtri ed export Markdown |
| **Detail** | Contenuto completo e similarità spiegata |
| **Editor** | Authoring Markdown con suggerimenti live |
| **TritaLeLe** | Ingestione controllata, review, rifiuto e approvazione dei candidati |
| **Duplicates** | Revisione read-only di duplicati esatti e near-duplicate |
| **Timeline** | Timeline di acquisizione e export per bucket |
| **Stats** | Conteggi, tag, topic e medie |
| **Vault** | Albero filesystem reale e import |
| **Ops** | Health, training, import vault e refresh completo |
| **Impostazioni** | Percorsi locali effettivi, ruoli di archiviazione e diagnostica bounded esplicita |
| **Informazioni** | Identità prodotto, versione, licenza MIT, dichiarazione local-first e collegamenti di supporto |

Il salvataggio dall'Editor scrive il file Markdown nel vault e aggiorna la
proiezione JSONL tramite `PUT` o `POST /vault/lessons`.

La GUI richiede `LELE_VAULT_DIR`; il default è `~/LeLeVault`.

### Consumer package PKPS di LeLe Manager

LeLe Manager implementa esclusivamente il lato consumer locale del protocollo
PKPS. GYTE Study Tools può consegnare una lesson revisionata all'esistente
confine TritaLeLe senza esporre il proprio workspace:

```bash
lele pkps import PACKAGE_PATH
lele pkps import PACKAGE_PATH --json
```

L'import v1 accetta una directory package o uno ZIP con root singola, valida
manifest, confinamento dei path, lesson UTF-8, conteggio byte e SHA-256, poi
mette in staging un candidato. Reimportare `package_id` e hash invariati è
idempotente; un package ID riutilizzato con hash differente viene rifiutato.
Nessuna scrittura nel vault, nelle proiezioni o nel ML avviene prima
dell'esistente approvazione esplicita. Questo confine non costituisce il
progetto PKPS completo né un orchestratore cross-repository. Consultare il
[contratto consumer PKPS](docs/it/pkps-package.md).

Il record di design completato resta disponibile in italiano in
[`docs/gui-design.md`](docs/gui-design.md). È classificato come documento
storico di design e non come manuale bilingue mantenuto.

### Sviluppo frontend

```bash
cd frontend
npm install
npm run dev
```

Usare l'URL stampato da Vite. La configurazione di sviluppo inoltra le chiamate
API quando il proxy è configurato.

### Smoke E2E Playwright

```bash
./scripts/build-gui.sh

cd frontend
npm install
npx playwright install chromium
npm run test:e2e
```

`scripts/e2e-serve.sh` avvia Uvicorn sulla porta `8765` con dati sotto
`.e2e-fixture/`. La CI esegue gli stessi flussi smoke dopo la build GUI e i test
Python.

## Versionamento e release

LeLe Manager segue Semantic Versioning:

- MAJOR: modifiche incompatibili ad API o formati;
- MINOR: feature retrocompatibili;
- PATCH: bugfix e miglioramenti interni.

Una release stabile comprende import del vault, proiezione JSONL, modelli topic
e similarità, endpoint FastAPI, client `lele`, GUI incorporata e verifiche
Python, frontend, sicurezza, packaging e release nativa tutte verdi.

Gli archive nativi vengono verificati dopo il packaging e prima dell'upload:
la CI estrae l'artefatto nello stesso formato destinato alla pubblicazione,
avvia l'eseguibile packaged su loopback con runtime isolato, verifica health,
GUI, licenza, Informazioni e Impostazioni/runtime e controlla che i percorsi
persistenti restino fuori dalla directory applicativa estratta.

Esempio di tag annotato:

```bash
git tag -a v1.0.0 -m "LeLe Manager 1.0.0 — first stable release"
git push origin v1.0.0
```

## Flussi di utilizzo reali

### Aggiungere una LeLe Git e controllare i suggerimenti

1. Creare una lesson Markdown sotto un percorso come
   `~/LeLeVault/git/2025-12-05.local-remote-architecture.md`.
2. Eseguire:

   ```bash
   ./scripts/lele-api-refresh.sh
   ```

3. Cercare:

   ```bash
   lele search git --topic git --limit 5
   ```

4. Trovare lesson simili:

   ```bash
   lele similar "git/2025-12-05.local-remote-architecture" --top-k 5
   ```

### Aggiornare una lesson esistente

1. Modificare body Markdown o frontmatter preservando coerenza tra percorso
   canonico, `id` e `topic`.
2. Eseguire `./scripts/lele-api-refresh.sh`.
3. Snapshot JSONL, topic model e API vengono aggiornati.
4. `/lessons`, `/lessons/{id}/similar` e `lele similar` usano il nuovo
   contenuto.

### Interrogare LeLe Manager da un altro progetto

Avviare l'API:

```bash
cd ~/Projects/lele-manager
./scripts/lele-api-dev.sh
```

Interrogarla:

```bash
curl -s "http://127.0.0.1:8000/lessons/search" \
  -H "Content-Type: application/json" \
  -d '{"q": "git", "topic_in": ["git"], "limit": 5}'
```

Il progetto esterno può anche usare `lele` quando è nel `PATH`, oppure
`python -m lele_manager.cli.lele`.

## Client API `lele`

```bash
lele --help
```

### Suggerimenti durante la scrittura

```bash
lele suggest --text "When std::cin reads a string, input is truncated at whitespace"
lele suggest --file note.md
cat note.md | lele suggest
lele suggest --watch note.md --every 2
```

### Esportare risultati di ricerca in Markdown

```bash
lele export --search "pytest" --topic python -o results.md
lele export --search "git" -o git-lessons.md --no-frontmatter
```

### Rilevare duplicati e quasi-duplicati

```bash
lele duplicates
lele duplicates --min-score 0.90 --limit 100
lele duplicates --exact-only
lele duplicates --json
```

I duplicati esatti comprendono ID ripetuti e testi uguali dopo una
normalizzazione prudente di Unicode, line ending e spazi finali. I
quasi-duplicati sono coppie non esatte il cui punteggio coseno raggiunge
`--min-score` usando l'estrattore di feature fittato per la similarità.

Topic, titolo, fonte, data e tag condivisi sono segnali esplicativi; da soli
non rendono la coppia un quasi-duplicato. La soglia predefinita `0.85` è
euristica e configurabile.

Il modello addestrato è necessario per i quasi-duplicati. `--exact-only`
funziona senza modello. Il confronto globale ha costo quadratico in tempo e
memoria ed è destinato al dataset personale corrente, non a collezioni molto
grandi.

### Spiegare la similarità

```bash
lele similar "python/2025-01-01.slug" --explain
lele suggest --text "pytest fixtures" --explain
```

Opzioni comuni:

- `--top-k`: numero massimo di risultati, default 5;
- `--min-score`: soglia minima di similarità, default 0.1;
- `--json`: output JSON grezzo.

Il client API usa `http://127.0.0.1:8000` per default. Avviare
`./scripts/lele-api-dev.sh` prima di usarlo.

## Contribuire

Vedere [CONTRIBUTING.it.md](CONTRIBUTING.it.md).
