# LeLe Manager 🐒 — Lesson-Learned Manager

Sistema ML end-to-end per gestire e cercare le mie *lesson learned* testuali: raccolta, tagging, ricerca e suggerimenti intelligenti.

Ogni volta che imparo qualcosa (da ChatGPT, da libri, da esperimenti), LeLe Manager diventa il mio archivio centrale:
- aggiungo una lesson con **testo + metadati** (data, fonte, topic, importanza);
- posso **cercare** per testo libero, tag, periodo;
- posso vedere **lesson simili o correlate**;
- nel tempo il sistema impara a **classificare e suggerire** in autonomia.

---

## ✨ Obiettivi principali

- 📥 **Raccolta veloce** delle lesson learned via CLI e API.
- 🏷️ **Tagging e metadati**: data, fonte, topic, importanza, tag liberi.
- 🔍 **Ricerca** full-text e per filtri (topic, periodo, fonte).
- 🤝 **Similarità**: suggerimento di lesson correlate a quella che sto scrivendo.
- 🧠 In prospettiva: **classificazione automatica** per tema/cluster e ranking per importanza.

---

## 🧱 Stack tecnico

- Python **3.13** (testato anche con 3.12)
- `pandas` / `numpy` per analisi dati
- `scikit-learn` per ML classico (classificatori, KNN/similarity, ecc.)
- (opzionale) piccolo **MLP** per migliorare embedding/scoring
- **FastAPI + Uvicorn** (Step 5) per esporre API
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
````

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
  ~/LeLeVault \
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

* `text`: contenuto testuale della lesson
* `source`: origine (`chatgpt`, `libro`, `esperimento`, ecc.)
* `topic`: macro-tema (es. `python`, `ml`, `linux`, `writing`)
* `importance`: scala numerica (es. 1–5)
* `tags`: lista di tag separati da virgola

Elencare le lesson:

```bash
python -m lele_manager.cli.list_lessons --limit 10
```

---

## 📂 LeLe Vault (Markdown + YAML frontmatter)
Oltre al salvataggio diretto via CLI, LeLe Manager supporta un **vault di file Markdown** con frontmatter YAML.

L’idea:
- scrivi e organizzi le LeLe come file `.md` nella tua cartella (es. `~/LeLeVault`);
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

- `id` (str) → **identità stabile** della LeLe
  * se non presente, viene derivato dal path relativo, es. `cpp/2025-11-20.cin-vs-getline`;
  * una volta generato, conviene non toccarlo a mano.
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
  ~/LeLeVault \
  data/lessons.jsonl \
  --on-duplicate overwrite \
  --default-source note \
  --default-importance 3 \
  --write-missing-frontmatter
```

Cosa fa:
- scandisce ricorsivamente `~/LeLeVault` alla ricerca di `.md`;
- per ogni file:
  * legge frontmatter YAML + body;
  * se manca `id`, lo genera dal path (`topic/YYYY-MM-DD.slug`) e, con `--write-missing-frontmatter`, lo scrive nel file;
  * deduce `topic` (frontmatter → `--default-topic` → nome directory);
  * normalizza `tags`, `importance`, `date`;
  * calcola un `frontmatter_hash` (solo metadati).
- crea in RAM una mappa `id → record`;
- scrive **da zero** `data/lessons.jsonl` con una riga per ogni `id` unico.

### Gestione dei duplicati: `--on-duplicate`

L’identità delle LeLe è l’`id` nel frontmatter.
Se durante l’import compaiono più file con lo stesso `id`, il comportamento si controlla con:
- `--on-duplicate overwrite` (default) → l’ultimo file letto vince;
- `--on-duplicate skip` → la prima occorrenza vince, le successive vengono ignorate;
- `--on-duplicate error` → il comando fallisce appena trova un `id` duplicato (utile per “pulizia archivio”).

### Flusso consigliato

1. Scrivi/organizzi le LeLe nel vault Markdown (`~/LeLeVault`).

2. Lanci l’import:
   ```bash
   python -m lele_manager.cli.import_from_dir \
     ~/LeLeVault \
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

## 🧠 ML classico: topic + similarità (Step 3–4)
LeLe Manager include una prima infrastruttura ML testuale.

### Classificatore di topic

Funzione interna:

* `train_topic_model(df)`

Caratteristiche:

* TF-IDF (unigrammi + bigrammi) sul testo delle lesson.
* `LogisticRegression` per predire il campo `topic`.

### Estrattore di feature unificato

Classe:

* `LessonFeatureExtractor`

Produce una matrice di feature combinando:

* TF-IDF del testo (`text`);
* meta-feature numeriche:

  * lunghezza in caratteri;
  * numero di parole;
  * `importance` (se presente).

Questo estrattore è usato sia per la classificazione di topic sia per l’indice di similarità (Step 4).

### Indice di similarità tra lesson

Classe:

* `LessonSimilarityIndex.from_lessons(...)` / `from_topic_pipeline(...)`

Metodo principale:

* `most_similar(query_text, top_k)` → restituisce gli ID delle lesson più simili e il relativo score (coseno).

Uso previsto:

* raccomandare lesson **correlate** quando ne aggiungo una nuova;
* in futuro, auto-proporre topic/cluster a partire dal testo.

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

* formato JSONL (una lesson per riga),
* colonne minime:

  * `text`: testo della lesson,
  * `topic`: label di training (stringa).

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

* `models/topic_model.joblib`

---

## 🔍 Suggerire lesson simili (CLI)

**Query da testo libero:**

```bash
python -m lele_manager.cli.suggest_similar \
  --input data/lessons.jsonl \
  --model models/topic_model.joblib \
  --text "Con layout src/ devo configurare PYTHONPATH o usare un conftest per pytest." \
  --top-k 5 \
  --min-score 0.1
```

**Query a partire da una lesson esistente:**

Se nel dataset hai una colonna `id` (UUID o int), puoi usare una lesson come query:

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

* ID della lesson,
* score di similarità,
* anteprima del testo.

---

## 🔐 Sicurezza

LeLe Manager non è mission-critical, ma l’obiettivo è **"non far uscire la scimmia senza casco"**.

### 🧪 Security workflow GitHub Actions

Workflow `.github/workflows/security.yml` che gira su push/PR + scan settimanale:

* `pip-audit` per vulnerabilità sulle dipendenze Python.
* `bandit` per analisi statica del codice sotto `src/`.

### ✅ pre-commit minimal ma ad alto valore

File `.pre-commit-config.yaml` con hook:

* cleanup di base (spazi a fine riga, newline finale),
* `check-yaml` per non rompere i workflow,
* `ruff` per lint/fix del codice Python.

Attivazione locale:

```bash
pip install pre-commit
pre-commit install
```

---

## 📂 Dati e modelli locali

* I file reali delle lesson learned vivono in `data/`.
* I modelli allenati vivono in `models/`.
* `data/` e `models/` sono esclusi dal versioning (vedi `.gitignore`).

Risultato: l’archivio personale e i modelli restano **fuori** dal repo pubblico.

---

## 🌐 API (FastAPI)
LeLe Manager espone anche un’API HTTP (FastAPI) sopra il motore interno:
- lettura e ricerca delle LeLe,
- training del topic model,
- similarità tra lesson.

### Avvio del server API
In sviluppo, il modo più semplice è usare lo script helper:
```bash
./scripts/lele-api-refresh.sh
```

#### Cosa fa, in sequenza:
    importa le LeLe dal vault Markdown ($LELE_VAULT_DIR, es. /home/baltimora/Uploads/LeLe-Vault) → data/lessons.jsonl;
    allena/riallena il topic model → models/topic_model.joblib;
    avvia il server FastAPI con Uvicorn su http://127.0.0.1:8000 (con --reload).

Se hai definito un alias nel tuo ~/.bashrc:
```bash
  alias lele-refresh='cd ~/Progetti/lele-manager && ./scripts/lele-api-refresh.sh'
```

allora ti basta:
```bash
  lele-refresh
```

#### Endpoints principali
```bash
    GET /health → stato rapido del servizio (dati/modello presenti).
    GET /lessons → lista/ricerca delle LeLe (con filtri).
    GET /lessons/{id} → dettaglio di una LeLe.
    GET /lessons/{id}/similar → LeLe simili a quella indicata.
    POST /train/topic → (ri)allena il topic model a partire da data/lessons.jsonl.
```

#### Documentazione interattiva (Swagger UI):
```bash
    http://127.0.0.1:8000/docs
```

#### Esempi di utilizzo via curl

1️⃣ Health check
```bash
curl -s http://127.0.0.1:8000/health | jq
```

Esempio di risposta:
```bash
{
  "status": "ok",
  "has_data": true,
  "has_model": true
}
```

2️⃣ Lista delle LeLe

# primi 5 elementi
curl -s "http://127.0.0.1:8000/lessons?limit=5" | jq

# filtro testuale (case-insensitive) sul testo
curl -s "http://127.0.0.1:8000/lessons?q=python&limit=5" | jq

# filtro per topic
curl -s "http://127.0.0.1:8000/lessons?topic=C%2B%2B&limit=5" | jq

3️⃣ Dettaglio di una LeLe

Dato un id presente nel dataset, ad esempio: "Cpp20 - std cin tronca sugli spazi", puoi recuperare il dettaglio con:
  curl -s "http://127.0.0.1:8000/lessons/Cpp20%20-%20std%20cin%20tronca%20sugli%20spazi" | jq

(le space vanno URL-encoded come %20).

4️⃣ LeLe simili via API

Usando lo stesso id come query per la similarità:

curl -s \
  "http://127.0.0.1:8000/lessons/Cpp20%20-%20std%20cin%20tronca%20sugli%20spazi/similar?top_k=5&min_score=0.1" \
  | jq

Esempio di risposta:
```json
{
  "query": "### LL-5 – `std::cin >>` tronca sugli spazi, `std::getline` no\n...",
  "results": [
    {
      "id": "Cpp20 - Boost vs Standard",
      "score": 0.36,
      "text_preview": "### LL-4 – Boost vs Standard Library (C++20)..."
    },
    {
      "id": "Cpp20 - Hello s e std string",
      "score": 0.35,
      "text_preview": "### LL-2 – \"Hello\"s e std::string_literals..."
    }
  ]
}
```

5️⃣ Retrain del topic model via API

Se hai aggiornato il vault e rifatto l’import, puoi rilanciare il training direttamente da HTTP:
  curl -s -X POST http://127.0.0.1:8000/train/topic | jq

Esempio:
```json
{
  "message": "Topic model allenato con successo e salvato in models/topic_model.joblib",
  "n_lessons": 42,
  "topics": ["C++", "python", "linux", "writing"]
}
```

Questo endpoint usa la stessa logica di train_topic_model da CLI e fallisce con errore esplicito se nel dataset è presente un solo topic (caso da evitare).

---

## 🗺️ Roadmap (8 settimane “Scimmia Turbo”)

* **Step 1 – Setup Python & tooling (Week 1–2)**
  Ambiente, struttura progetto, primi tool CLI per salvare e ispezionare lesson learned.

* **Step 2 – Data & EDA sulle lesson learned (Week 3–4)**
  Formato di storage (JSONL/SQLite), funzioni di ingest, notebook di analisi sulle lesson (per fonte, topic, lunghezza, tempo).

  > L’EDA in notebook è rimandata a una fase successiva.

* **Step 3 – ML classico (Week 5–6)**
  Modelli base per classificazione di topic / importanza e primi modelli di similarità (TF-IDF + k-NN).

* **Step 4 – Pipeline & feature engineering (Week 6)**
  Pipeline scikit-learn completa: testo → feature → modello (topic),
  estrattore di feature condiviso (TF-IDF + meta-feature),
  CLI di training (`train_topic_model`) e similarity (`suggest_similar`).

* **Step 5 – API & capstone end-to-end (Week 7–8)**
  Servizio FastAPI: endpoints per aggiungere, cercare e recuperare lesson simili; tests, README, (opzionale) Docker.

### ✅ Progress

* ✅ **Step 1** – Setup Python & tooling
* ✅ **Step 2** – Data & formato lesson learned *(EDA in notebook rinviata a fase successiva)*
* ✅ **Step 3** – ML classico (classificazione / similarità)
* ✅ **Step 4** – Pipeline & feature engineering (topic + indice di similarità)
* ✅ **Step 5** – API & capstone end-to-end
