# LeLe Manager 🐒 — Lesson-Learned Manager
[![Security](https://github.com/gcomneno/lele-manager/actions/workflows/security.yml/badge.svg)](https://github.com/gcomneno/lele-manager/actions/workflows/security.yml)
[![CI](https://github.com/gcomneno/lele-manager/actions/workflows/ci.yml/badge.svg)](https://github.com/gcomneno/lele-manager/actions/workflows/ci.yml)

Sistema ML end-to-end per gestire e cercare le mie *lesson learned* testuali: raccolta, tagging, ricerca e suggerimenti intelligenti.

Ogni volta che imparo qualcosa (da ChatGPT, da libri, da esperimenti), LeLe Manager diventa il mio archivio centrale:
- aggiungo una lesson con **testo + metadati** (data, fonte, topic, importanza);
- posso **cercare** per testo libero, tag, periodo;
- posso vedere **lesson simili o correlate**;
- nel tempo il sistema impara a **classificare e suggerire** in autonomia.

---

## ✅ Quality gates (quick scan)

- **CI**: `ruff check .` + `pytest` (GitHub Actions, Python 3.12)
- **Security**: `pip-audit` + `bandit` (GitHub Actions)
- **pre-commit**: whitespace/end-of-file, `check-yaml`, `ruff`

## 🗺️ Roadmap (quick links)

- Milestone **v1.2 (stabilizzazione)**: [milestone/1](https://github.com/gcomneno/lele-manager/milestone/1)
- Milestone **v2 (future/esperimenti)**: [milestone/2](https://github.com/gcomneno/lele-manager/milestone/2)
- Documento completo: `ROADMAP.md`
- Changelog: `CHANGELOG.md`

---

## ✨ Obiettivi principali

- 📥 **Raccolta veloce** delle lesson learned via CLI e API.
- 🏷️ **Tagging e metadati**: data, fonte, topic, importanza, tag liberi.
- 🔍 **Ricerca** full-text e per filtri (topic, periodo, fonte).
- 🤝 **Similarità**: suggerimento di lesson correlate a quella che sto scrivendo.
- 🧠 In prospettiva: **classificazione automatica** per tema/cluster e ranking per importanza.

---

## 🧱 Stack tecnico

- Python **3.12** (CI) — testato anche con 3.13
- `pandas` / `numpy` per analisi dati
- `scikit-learn` per ML classico (classificatori, KNN/similarity, ecc.)
- (opzionale) piccolo **MLP** per migliorare embedding/scoring
- **FastAPI + Uvicorn** per esporre API HTTP
- Storage: **JSONL / SQLite** (a seconda della fase del progetto)

---

## 🚀 Setup

Clona il repository e crea un ambiente virtuale:

```bash
git clone git@github.com:gcomneno/lele-manager.git
cd lele-manager

python -m venv .venv
source .venv/bin/activate  # su Windows: .venv\Scripts\activate

pip install -e .[dev]
```

---

## 🛠️ Primi tool CLI (palestra)

Alcuni comandi base già disponibili:

```bash
# Converti un CSV di lesson in JSON
python -m lele_manager.cli.csv2json samples/input.csv samples/output.json

# Monitora una directory (es. data/) per nuovi file
python -m lele_manager.cli.file_watcher data

# Importa LeLe da una directory Markdown con frontmatter YAML nel vault personale
python -m lele_manager.cli.import_from_dir \
  "$LELE_VAULT_DIR" \
  data/lessons.jsonl \
  --on-duplicate overwrite \
  --default-source note \
  --default-importance 3 \
  --write-missing-frontmatter
```

---

## 📝 Uso rapido – Lesson Learned via CLI

Aggiungere una lesson:

```bash
python -m lele_manager.cli.add_lesson \
  --text "Con layout src/ devo configurare PYTHONPATH o usare un conftest per pytest." \
  --source chatgpt \
  --topic python \
  --importance 4 \
  --tags "python,pytest,tooling"
```

Campi principali:

- `text`: contenuto testuale della lesson
- `source`: origine (`chatgpt`, `libro`, `esperimento`, ecc.)
- `topic`: macro-tema (es. `python`, `ml`, `linux`, `writing`)
- `importance`: scala numerica (es. 1–5)
- `tags`: lista di tag separati da virgola

Elencare le lesson:

```bash
python -m lele_manager.cli.list_lessons --limit 10
```

---

## 📂 LeLe Vault (Markdown + YAML frontmatter)

Oltre al salvataggio diretto via CLI, LeLe Manager supporta un **vault di file Markdown** con frontmatter YAML.

L’idea:

- scrivi e organizzi le LeLe come file `.md` nella tua cartella (es. `~/LeLeVault` o `/home/utente/Uploads/LeLe-Vault`);
- uno script (`import_from_dir`) li legge, normalizza i metadati e genera `data/lessons.jsonl`;
- l’ID della LeLe vive nel **frontmatter**, non nel path → puoi correggere e spostare i file senza perdere l’identità.

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

Convenzioni (soft):

- directory = **topic** principale (`python`, `cpp`, `linux`, `writing`, …);
- filename = `YYYY-MM-DD.slug.md` (senza underscore, usa `.` e `-`).

### Frontmatter YAML: schema base

Ogni LeLe può avere in testa un frontmatter YAML:

```markdown
---
id: cpp/2025-11-20.cin-vs-getline
topic: cpp
source: libro
importance: 4
tags: [cpp, io, stringhe]
date: 2025-11-20
title: "LL-5 — std::cin vs std::getline"
---
```

Campi supportati (tutti opzionali, tranne `id` che viene generato se manca):

- `id` (str) → identità stabile della LeLe
  - se non presente, viene derivato dal path relativo, es. `cpp/2025-11-20.cin-vs-getline`;
  - una volta generato, conviene non toccarlo a mano.
- `topic` (str) → se manca, può essere dedotto dal nome della directory (`python`, `cpp`, etc.) o da `--default-topic`.
- `source` (str) → es. `chatgpt`, `libro`, `esperimento`, `note`.
- `importance` (int) → tipicamente 1–5.
- `tags` (lista o stringa) → es. `["python", "pytest", "tooling"]` oppure `"python, pytest, tooling"`.
- `date` (str, ISO-like) → es. `2025-11-20`. Se mancante, può essere dedotta dal filename `YYYY-MM-DD.slug.md`.
- `title` (str) → titolo umano della LeLe (opzionale).

Internamente LeLe Manager calcola anche un `frontmatter_hash` (hash del solo frontmatter) utile per debug/versioning, ma l’identità resta sempre `id`.

### Import da vault Markdown → JSONL

Per costruire `data/lessons.jsonl` a partire dalla cartella del vault:

```bash
python -m lele_manager.cli.import_from_dir \
  "$LELE_VAULT_DIR" \
  data/lessons.jsonl \
  --on-duplicate overwrite \
  --default-source note \
  --default-importance 3 \
  --write-missing-frontmatter
```

Cosa fa:

- scandisce ricorsivamente `$LELE_VAULT_DIR` alla ricerca di `.md`;
- per ogni file:
  - legge frontmatter YAML + body;
  - se manca `id`, lo genera dal path (`topic/YYYY-MM-DD.slug`) e, con `--write-missing-frontmatter`, lo scrive nel file;
  - deduce `topic` (frontmatter → `--default-topic` → nome directory);
  - normalizza `tags`, `importance`, `date`;
  - calcola un `frontmatter_hash` (solo metadati);
- crea in RAM una mappa `id → record`;
- scrive da zero `data/lessons.jsonl` con una riga per ogni `id` unico.

### Gestione dei duplicati: `--on-duplicate`

L’identità delle LeLe è l’`id` nel frontmatter.
Se durante l’import compaiono più file con lo stesso `id`, il comportamento si controlla con:

- `--on-duplicate overwrite` (default) → l’ultimo file letto vince;
- `--on-duplicate skip` → la prima occorrenza vince, le successive vengono ignorate;
- `--on-duplicate error` → il comando fallisce appena trova un `id` duplicato.

### Flusso consigliato

1. Scrivi/organizzi le LeLe nel vault Markdown (`$LELE_VAULT_DIR`).
2. Lanci l’import:

   ```bash
   python -m lele_manager.cli.import_from_dir \
     "$LELE_VAULT_DIR" \
     data/lessons.jsonl \
     --on-duplicate overwrite \
     --write-missing-frontmatter
   ```

3. Alleni il topic model:

   ```bash
   python -m lele_manager.cli.train_topic_model \
     --input data/lessons.jsonl \
     --output models/topic_model.joblib \
     --overwrite
   ```

4. Esplori l’archivio con la similarità:

   ```bash
   python -m lele_manager.cli.suggest_similar \
     --input data/lessons.jsonl \
     --model models/topic_model.joblib \
     --text "Quando uso std::cin >> su una string, l'input viene troncato agli spazi" \
     --top-k 5 \
     --min-score 0.1
   ```

---

## 🧠 ML classico: topic + similarità

LeLe Manager include una prima infrastruttura ML testuale.

### Classificatore di topic

Funzione interna:

- `train_topic_model(df)`

Caratteristiche:

- TF-IDF (unigrammi + bigrammi) sul testo delle lesson.
- `LogisticRegression` per predire il campo `topic`.

### Estrattore di feature unificato

Classe:

- `LessonFeatureExtractor`

Produce una matrice di feature combinando:

- TF-IDF del testo (`text`);
- meta-feature numeriche:
  - lunghezza in caratteri,
  - numero di parole,
  - `importance` (se presente).

Questo estrattore è usato sia per la classificazione di topic sia per l’indice di similarità.

### Indice di similarità tra lesson

Classe:

- `LessonSimilarityIndex.from_lessons(...)` / `from_topic_pipeline(...)`

Metodo principale:

- `most_similar(query_text, top_k)` → restituisce gli ID delle lesson più simili e il relativo score (coseno).

Uso previsto:

- raccomandare lesson correlate quando ne aggiungo una nuova;
- in futuro, auto-proporre topic/cluster a partire dal testo.

---

## 🧪 Training del topic model (CLI)

Per addestrare il topic model a partire dal tuo archivio JSONL:

```bash
python -m lele_manager.cli.train_topic_model \
  --input data/lessons.jsonl \
  --output models/topic_model.joblib \
  --overwrite
```

Requisiti del file `data/lessons.jsonl`:

- formato JSONL (una lesson per riga),
- colonne minime:
  - `text`: testo della lesson,
  - `topic`: label di training (stringa).

Esempio di riga:

```json
{"id": "89c6bca8-941b-4a93-a7ca-a35e584ae5ec",
 "text": "Con layout src/ devo gestire PYTHONPATH o usare un conftest per pytest.",
 "topic": "python",
 "source": "chatgpt",
 "importance": 4,
 "tags": ["python", "pytest", "tooling"]}
```

L’output è una pipeline sklearn completa (feature + modello) salvata in:

- `models/topic_model.joblib`

---

## 🔍 Suggerire lesson simili (CLI)

Nota: via API è disponibile anche `POST /similar` per confrontare testo libero senza ID.

### Query da testo libero

```bash
python -m lele_manager.cli.suggest_similar \
  --input data/lessons.jsonl \
  --model models/topic_model.joblib \
  --text "Con layout src/ devo configurare PYTHONPATH o usare un conftest per pytest." \
  --top-k 5 \
  --min-score 0.1
```

### Query a partire da una lesson esistente

Se nel dataset hai una colonna `id` (UUID, string o int), puoi usare una lesson come query:

```bash
python -m lele_manager.cli.suggest_similar \
  --input data/lessons.jsonl \
  --model models/topic_model.joblib \
  --from-id "89c6bca8-941b-4a93-a7ca-a35e584ae5ec" \
  --id-column id \
  --top-k 5 \
  --min-score 0.1
```

L’output mostra:

- ID della lesson,
- score di similarità,
- anteprima del testo.

---

## 🔐 Sicurezza

LeLe Manager non è mission-critical, ma l’obiettivo è non far uscire la scimmia senza casco.

### Security workflow GitHub Actions

Workflow `.github/workflows/security.yml` che gira su push/PR + scan settimanale:

- `pip-audit` per vulnerabilità sulle dipendenze Python.
- `bandit` per analisi statica del codice sotto `src/`.

### ✅ pre-commit minimal ma ad alto valore

File `.pre-commit-config.yaml` con hook:

- cleanup di base (spazi a fine riga, newline finale),
- `check-yaml` per non rompere i workflow,
- `ruff` per lint/fix del codice Python.

Attivazione locale:

```bash
pip install pre-commit
pre-commit install
```

---

## 📂 Dati e modelli locali

- I file reali delle lesson learned vivono in `data/`.
- I modelli allenati vivono in `models/`.
- `data/` e `models/` sono esclusi dal versioning (vedi `.gitignore`).

Risultato: l’archivio personale e i modelli restano fuori dal repo pubblico.

---

## 🔧 Script di utilità (`scripts/`)

### `scripts/lele-api-refresh.sh`

Script “tasto F5” completo:

1. importa le LeLe dal vault Markdown (`$LELE_VAULT_DIR`) in `data/lessons.jsonl`;
2. riallena il topic model in `models/topic_model.joblib`;
3. avvia LeLe API in dev con Uvicorn (`--reload`).

Uso tipico:

```bash
cd ~/Progetti/lele-manager
export LELE_VAULT_DIR=/home/utente/Uploads/LeLe-Vault  # adattare al proprio path
./scripts/lele-api-refresh.sh
```

### `scripts/lele-api-dev.sh`

Script leggero per avviare solo le API FastAPI (senza re-importare né riallenare):

```bash
cd ~/Progetti/lele-manager
./scripts/lele-api-dev.sh
```

Fa:

- individua la root del progetto;
- attiva `.venv` (se manca segnala come crearla);
- controlla che `uvicorn` sia installato nella venv;
- avvia il server su `http://127.0.0.1:8000` con `--reload`.

---

## 🌐 API FastAPI

LeLe Manager espone un’API HTTP (FastAPI) sopra il motore interno:

- lettura e ricerca delle LeLe,
- training del topic model,
- similarità tra lesson.

### Avvio del server API

Modalità “giro completo” (vault → JSONL → modello → API):

```bash
./scripts/lele-api-refresh.sh
```

Modalità “solo API” (dataset e modello già pronti):

```bash
./scripts/lele-api-dev.sh
```

### Endpoints principali

- `GET /health` → stato rapido del servizio (dati/modello presenti).
- `GET /lessons` → lista/ricerca delle LeLe (query param base).
- `GET /lessons/{id}` → dettaglio di una LeLe.
- `GET /lessons/{id}/similar` → LeLe simili a quella indicata.
- `POST /train/topic` → (ri)allena il topic model a partire da `data/lessons.jsonl`.
- `POST /lessons/search` → ricerca avanzata con payload JSON (testo + filtri).
- `POST /similar` → suggerisce LeLe simili a partire da testo libero (senza `lesson_id`).

---

## 🖥️ GUI Web (v2.0 alpha)

Oltre alla CLI e al PoC legacy (`GET /ui`), LeLe Manager include una **GUI Svelte** servita dall'API:

```bash
# 1) Build frontend (Vite + Svelte)
./scripts/build-gui.sh

# 2) Avvia API
./scripts/lele-api-dev.sh

# 3) Apri browser
# http://127.0.0.1:8000/app/
```

### Viste disponibili (Fase 1)

| Vista | Cosa fa |
|-------|---------|
| **Browse** | Ricerca avanzata (`POST /lessons/search`) + filtri |
| **Detail** | Lettura LeLe + pannello simili |
| **Editor** | Scrittura con suggest live (`POST /editor/suggest`) |
| **Vault** | Albero filesystem reale (`GET /vault/tree`) + import |
| **Ops** | Health + retrain + **import vault** + **refresh completo** |

**Salvataggio:** Editor → **Salva nel vault** scrive il file `.md` e risincronizza il JSONL (`PUT` / `POST /vault/lessons`).

Richiede `LELE_VAULT_DIR` (default `~/LeLeVault`).

**Dev frontend** (hot reload, proxy API):

```bash
cd frontend
npm install
npm run dev
# apri l'URL indicato da Vite (proxy verso :8000 se configurato)
```

---

## 📦 Versioni & release

LeLe Manager segue il versioning semantico (SemVer):

- MAJOR: cambiamenti incompatibili nelle API/nei formati (es. 1.x → 2.0.0).
- MINOR: nuove funzionalità retro-compatibili (es. 1.0.0 → 1.1.0).
- PATCH: bugfix o piccoli miglioramenti interni (es. 1.0.0 → 1.0.1).

Per l’uso quotidiano:

- lavori normalmente sul branch `main`;
- quando uno stato è “buono per un lungo periodo”, viene taggato (`vX.Y.Z`) e usato come release;
- il primo stato considerato “strumento 1.0 stabile” è quello con:
  - import dal vault Markdown (`import_from_dir`),
  - dataset JSONL (`data/lessons.jsonl`),
  - topic model + similarità (`models/topic_model.joblib`),
  - API FastAPI (`/lessons`, `/lessons/search`, `/lessons/{id}/similar`, ecc.),
  - client CLI `lele` funzionante,
  - tests `pytest` verdi.

Esempio di creazione di una release dall’ultimo commit stabile:

```bash
git tag -a v1.0.0 -m "LeLe Manager 1.0.0 – primo rilascio stabile"
git push origin v1.0.0
```

---

## 👤 User stories (come lo uso davvero)

### 1) Aggiungo una nuova LeLe Git e vedo i suggerimenti

1. Scrivo una nuova LeLe nel vault, es.
   `~/Uploads/LeLe-Vault/git/2025-12-05.architettura-locale-remoto.md`
   con frontmatter YAML (`topic: git`, `importance: 5`, ecc.).
2. Lancio:

   ```bash
   ./scripts/lele-api-refresh.sh
   ```

   che fa in sequenza:
   - import dal vault → `data/lessons.jsonl`,
   - training del topic model → `models/topic_model.joblib`,
   - avvio di Uvicorn con LeLe API su `http://127.0.0.1:8000`.
3. Cerco dal client CLI:

   ```bash
   lele search git --topic git --limit 5
   ```

4. Se voglio le LeLe più simili a quella che ho appena scritto:

   ```bash
   lele similar "git/2025-12-05.architettura-locale-remoto" --top-k 5
   ```

### 2) Aggiorno una LeLe esistente e allineo il modello

1. Modifico il contenuto di una LeLe già esistente nel vault (stesso `id` nel frontmatter YAML).
2. Rilancio:

   ```bash
   ./scripts/lele-api-refresh.sh
   ```

3. Il comando:
   - riscrive il JSONL,
   - riallena il topic model,
   - riavvia l’API.
4. Da qui in poi:
   - `/lessons` restituisce il nuovo testo,
   - `/lessons/{id}/similar` e `lele similar` lavorano sul contenuto aggiornato.

### 3) Uso LeLe Manager da un altro progetto

1. Avvio LeLe API in una shell:

   ```bash
   cd ~/Progetti/lele-manager
   ./scripts/lele-api-dev.sh
   ```

2. Dal progetto esterno, interrogo le API, ad esempio:

   ```bash
   curl -s "http://127.0.0.1:8000/lessons/search" \
     -H "Content-Type: application/json" \
     -d '{"q": "git", "topic_in": ["git"], "limit": 5}'
   ```

3. Oppure, sempre dall’altro repo, uso direttamente il client CLI `lele`
   (se è nel PATH, o via `python -m lele_manager.cli.lele`).

## Contributing
See [`CONTRIBUTING.md`](CONTRIBUTING.md).


---

## 🧩 Nuovo CLI: `lele` (API client)

Oltre agli script tecnici (`python -m lele_manager.cli.*`), è disponibile un client CLI più ergonomico:

```bash
lele --help
```

### 🔍 Suggerire LeLe simili mentre scrivi

Query da testo libero (via API `POST /similar`):

```bash
lele suggest --text "Quando uso std::cin >> su una string, l'input viene troncato agli spazi"
```

Da file:

```bash
lele suggest --file note.md
```

Da stdin:

```bash
cat note.md | lele suggest
```

Modalità watch (ogni 2 secondi):

```bash
lele suggest --watch note.md --every 2
```

Opzioni principali:

- `--top-k` → numero massimo risultati (default 5)
- `--min-score` → soglia minima di similarità (default 0.1)
- `--json` → output JSON grezzo

Questo comando usa l’API locale (default `http://127.0.0.1:8000`).
Assicurati che il server sia attivo (`./scripts/lele-api-dev.sh`).
