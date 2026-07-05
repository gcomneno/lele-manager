# LeLe Manager – Roadmap & stato d'arte
> Knowledge base personale per Lesson Learned testuali:
> Vault Markdown → JSONL → ML (topic/similarità) → API FastAPI.

---

## 1. Obiettivo del progetto
LeLe Manager vuole essere il **motore centrale** per le mie *lesson learned*:

- scrivo le LeLe come file Markdown, organizzate in cartelle (per topic, ecc.);
- LeLe Manager le importa, normalizza e le usa per:
  - **ricerca** (testo libero + filtri),
  - **classificazione per topic**,
  - **suggerimento di lesson simili**.

Target: **strumento 1.0 stabile** per uso personale quotidiano, con una base ML estendibile in futuro.

---

## 2. Step originali & stato di avanzamento
Roadmap originale:

1. **Step 1 – Setup Python & tooling**
   Ambiente, struttura progetto, primi tool CLI.
2. **Step 2 – Data & EDA sulle lesson learned**
   Formato di storage (JSONL/SQLite), ingest, prime analisi.
3. **Step 3 – ML classico**
   Topic model + similarità base (TF-IDF + k-NN/logistic).
4. **Step 4 – Pipeline & feature engineering**
   Feature condivise, pipeline sklearn, CLI ML.
5. **Step 5 – API & capstone end-to-end**
   FastAPI, endpoints, script dev, (eventuale Docker/UI).

### 2.1. Step completati ✅
- ✅ **Step 1 – Setup Python & tooling**
  - Struttura progetto (`src/lele_manager/…`).
  - `pyproject.toml`, dipendenze, ambiente virtuale, `pip install -e .[dev]`.
  - primi CLI di prova (`csv2json`, `file_watcher`, ecc.).
  - pre-commit con:
    - whitespace cleanup,
    - `check-yaml`,
    - `ruff`.

- ✅ **Step 2 – Data & formato lesson learned**
  *(EDA notebook rinviata a fase successiva)*
  - Definizione schema minimo LeLe:
    - `id`, `text`, `topic`, `source`, `importance`, `tags`, `date`, `title`.
  - Storage principale: **JSONL** (`data/lessons.jsonl`).
  - Funzioni di ingest da CSV / altre fonti.

- ✅ **Step 3 – ML classico (topic/similarità)**
  - Topic model:
    - `train_topic_model(df)` con TF-IDF + `LogisticRegression`.
    - pipeline sklearn salvata in `models/topic_model.joblib`.
  - Similarità:
    - `LessonSimilarityIndex` con TF-IDF (e meta-feature nella versione più recente),
    - CLI `suggest_similar` (da testo o da `id` esistente).

- ✅ **Step 4 – Pipeline & feature engineering + LeLe Vault**
  - `LessonFeatureExtractor`:
    - TF-IDF sul testo,
    - meta-feature (lunghezza, n° parole, importance).
  - `TopicModelConfig`, `build_topic_pipeline`, `train_topic_model`:
    - pipeline unificata: feature extractor + modello.
    - **hardening**: errore leggibile se il dataset ha un solo `topic`.
  - **LeLe Vault (Markdown + YAML)**:
    - directory radice configurabile (`LELE_VAULT_DIR`, es. `/home/baltimora/Uploads/LeLe-Vault`),
    - file `.md` con frontmatter YAML:
      - `id`, `topic`, `source`, `importance`, `tags`, `date`, `title`.
    - CLI `import_from_dir`:
      - scansiona il vault,
      - genera/sincronizza frontmatter (`--write-missing-frontmatter`),
      - gestisce duplicati con `--on-duplicate {overwrite,skip,error}`,
      - scrive il dataset in `data/lessons.jsonl`.
    - Bugfix:
      - hash frontmatter con **SHA-256** (Bandit felice),
      - serializzazione robusta delle `date` YAML (`datetime.date` → stringa JSON).

- ✅ **Step 5 – API FastAPI (base) & script dev**
  - Server `lele_manager.api.server:app` con endpoint:
    - `GET /health`
    - `GET /lessons`
    - `GET /lessons/{id}`
    - `GET /lessons/{id}/similar`
    - `POST /train/topic`
  - Robustezza API:
    - normalizzazione di `NaN` / `NaT` / valori strani → `Optional[str]`,
    - niente più 500 casuali per colpa di `date/title` sporchi.
  - **Script dev**:
    - `scripts/lele-api-refresh.sh`:
      1. importa dal vault → `data/lessons.jsonl`,
      2. allena topic model → `models/topic_model.joblib`,
      3. avvia FastAPI con Uvicorn (`--reload`).
    - alias `lele-refresh` per avere *import + train + server* in un solo comando.
  - README aggiornato con:
    - sezione LeLe Vault,
    - sezione API (FastAPI) + esempi `curl`.

---

## 3. Stato attuale (LeLe Manager “1.0”)

In pratica oggi ho:
- **Vault Markdown** organizzato (es. `git/`, `cpp/`, `python/`…) in `LELE_VAULT_DIR`.
- Un **importer** stabile dal vault a JSONL (`import_from_dir`).
- Un **topic model** che funziona su dati reali (py, C++, git, ecc.).
- Un **indice di similarità** usabile (CLI + API).
- Un **server FastAPI** che espone:
  - lettura & ricerca,
  - similarità,
  - retraining.
- Uno **script dev** (`lele-refresh`) che riallinea tutto: vault → JSONL → modello → API.

È, di fatto, un **LeLe Manager 1.0 usabile in produzione personale**.

---

## 4. TODO “assoluti” — stato aggiornato (2026-07)

La maggior parte dei TODO originali è **completata**. Questa sezione riflette lo stato reale del codice su `main`.

### 4.1. Test automatici minimi ✅

**Obiettivo:** evitare che una modifica futura spacchi in silenzio il flusso base.

- [x] **Test `import_from_dir`** (`test_import_from_dir.py`, `test_import_from_dir_cli.py`, `test_frontmatter_hash.py`)
  - [x] frontmatter mancante → viene creato correttamente
  - [x] `date` YAML → stringa `"YYYY-MM-DD"` nel JSONL
  - [x] `--on-duplicate overwrite` / `skip` / `error`
  - [x] hash frontmatter (SHA-256) stabile

- [x] **Test `train_topic_model`** (`test_train_topic_model_cli.py`, `test_text_ml.py`)
  - [x] dataset con due topic → training ok
  - [x] dataset con un solo topic → `ValueError` leggibile
  - [x] dataset senza colonna `topic` → errore chiaro

- [x] **Test API base** (`test_api_basic.py`, `test_search_api.py`, `test_api_similar_edgecases.py`, …)
  - [x] `GET /health` (dataset/modello presenti o mancanti)
  - [x] `GET /lessons` con `NaN`/`NaT` e `tags` non lista
  - [x] `GET /lessons/{id}` → 200 / 404
  - [x] `GET /lessons/{id}/similar` → ok o 503 se modello mancante

Suite attuale: **~36 file di test, ~75 casi** — copertura ben oltre il minimo originale.

### 4.2. Endpoint di ricerca avanzata ✅

- [x] `POST /lessons/search` con payload JSON (`topic_in`, `source_in`, `importance_gte/lte`, `limit`, …)
- [x] Filtri lato server con DataFrame normalizzato + ordinamento deterministico
- [x] Esempi nel README

### 4.3. Client CLI sopra le API ✅

- [x] `lele search "pytest" --topic python --limit 10`
- [x] `lele show <id>`
- [x] `lele similar <id> --top-k 5 --min-score 0.1`
- [x] `lele train-topic`
- [x] `lele suggest` (`--text`, `--file`, stdin, `--watch`)
- [x] Configurazione via `LELE_API_URL` (default `http://127.0.0.1:8000`)

### 4.4. Documentazione & versioni ✅ (con piccoli residui)

- [x] Sezione **Versioni** nel README + `CHANGELOG.md`
- [x] User stories complete nel README
- [x] `LICENSE` (MIT)
- [ ] Pin dipendenze in `pyproject.toml` (reproducibilità build)
- [x] Tag `v1.5.0` per le feature post-1.4.1

---

## 5. Evoluzione futura (nice-to-have)
Queste sono le idee “da laboratorio” — alcune già parzialmente realizzate.

### 5.1. ML più ricco
- [x] Embedding densi (SVD) come backend opt-in (`LsaSimilarityBackend`, TF-IDF + TruncatedSVD).
- [ ] doc2vec / altri embedding al posto/insieme di TF-IDF.
- [ ] MLP o altro modellino leggero sopra le feature attuali per:
  * migliorare similarità,
  * stimare una “priorità di revisita” della LeLe (ranking personalizzato).

### 5.2. UX & interfacce
- [x] Mini UI web (`GET /ui`) con ricerca e similarità free-text.
- [x] Integrazione editor: `POST /editor/suggest` per similarità live mentre si scrive.
- [ ] Plugin editor nativo (VS Code / Obsidian) che chiama l’API in background.

### 5.3. Architettura & distribuzione
- [x] Separazione in moduli (`core`, `ml`, `cli`, `api`).
- [x] Packaging smoke test + release workflow (PyPI gated da `PYPI_ENABLED`).
- [ ] Refactor `server.py` in router FastAPI separati.
- [ ] Pubblicazione effettiva su PyPI.
- [ ] Pin dipendenze per build riproducibili.

---

## 6. Priorità operative (in ordine pratico)
1. ✅ Vault + import + ML + API + `lele-refresh`.
2. ✅ Test minimi, `POST /lessons/search`, client CLI `lele`.
3. ✅ UI minimale, similarity service boundary, backend abstraction, LSA opt-in.
4. 🔴 **Prossimi passi sensati**:
   1. Tag release `v1.5.0` (feature post-1.4.1 documentate in `CHANGELOG.md`).
   2. Pin dipendenze (`pyproject.toml` o lockfile).
   3. Split `server.py` in router (manutenibilità).
5. 🟢 **Ricerca & giocattoni**:
   * embedding più sofisticati (doc2vec, ecc.),
   * ranking personalizzato,
   * plugin editor,
   * integrazione con altri progetti (GYTE, ecc.).

---
