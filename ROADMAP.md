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

## 4. TODO “assoluti” (da fare davvero)
Queste sono le cose da fare **prima** di complicare il progetto con nuove feature grosse.

### 4.1. Test automatici minimi
**Obiettivo:** evitare che una modifica futura spacchi in silenzio il flusso base.

- [ ] **Test `import_from_dir`**
  - [ ] frontmatter mancante → viene creato correttamente (`id`, `topic`, `source`, `importance`).
  - [ ] `date` YAML → finisce come stringa `"YYYY-MM-DD"` nel JSONL.
  - [ ] `--on-duplicate overwrite` / `skip` / `error`:
    - [ ] overwrite: vince l’ultima versione,
    - [ ] skip: vince la prima,
    - [ ] error: solleva eccezione al primo duplicato.
  - [ ] hash frontmatter (SHA-256) stabile al cambiare dell’ordine delle chiavi.

- [ ] **Test `train_topic_model`**
  - [ ] dataset con due topic diversi → training ok.
  - [ ] dataset con un solo topic → `ValueError` con messaggio leggibile.
  - [ ] dataset senza colonna `topic` → `KeyError` chiaro.

- [ ] **Test API base**
  - [ ] `GET /health` con:
    - dataset/modello presenti,
    - dataset/modello mancanti.
  - [ ] `GET /lessons` con JSONL contenente:
    - valori `NaN`/`NaT` su `date`/`title`,
    - `tags` non lista → vengono resi `null`.
  - [ ] `GET /lessons/{id}`:
    - id presente → 200,
    - id assente → 404.
  - [ ] `GET /lessons/{id}/similar` con:
    - modello presente → risposta ok,
    - modello mancante → errore 503 leggibile.

### 4.2. Endpoint di ricerca avanzata

_Nota: `POST /similar` (text-based similarity) è stato implementato in v1.2.0._

**Motivazione:** i query param (`q`, `topic`, `source`, `limit`) sono limitati; serve qualcosa di più espressivo.

- [ ] Aggiungere endpoint `POST /lessons/search` con payload JSON, es.:

```json
{
"q": "pytest",
"topic_in": ["python", "git"],
"source_in": ["note", "chatgpt"],
"importance_gte": 3,
"importance_lte": 5,
"limit": 20
}
```

* [ ] Implementare logica di filtro lato server con un DataFrame “pulito” (simile all’attuale `list_lessons`, ma più ricca).
* [ ] Aggiungere esempi nel README.

### 4.3. Client CLI sopra le API

_Stato: prima versione implementata in v1.2.0 (`lele suggest`)._

**Motivazione:** non voglio ricordarmi `curl` a memoria ogni volta.

Nuovo modulo CLI, ad es. `lele_manager.cli.api_client` + entrypoint `lele` (o simile):

* [ ] `lele search "pytest" --topic python --limit 10`
* [ ] `lele show <id>`
* [ ] `lele similar <id> --top-k 5 --min-score 0.1`
* [ ] `lele train-topic` (chiama `POST /train/topic`)

Extra:
* [ ] Configurazione host/port in un file di config o variabile d’ambiente (di default `http://127.0.0.1:8000`).

### 4.4. Documentazione & versioni
* [ ] Aggiungere una sezione **“Versioni”** nel README (o in `CHANGELOG.md`), es.:

  ```markdown
  ## Versioni

  - 1.0.0 – Prima versione completa:
    - LeLe Vault (Markdown + YAML),
    - import JSONL,
    - topic model + similarità,
    - API FastAPI,
    - script `lele-refresh`.
  ```

* [ ] Aggiungere 1–2 **“User story complete”** nel README:

  * [ ] “Aggiungo una nuova LeLe Git nel vault → la vedo via `/lessons` → chiedo simili via `/lessons/{id}/similar`”.
  * [ ] “Aggiorno una LeLe esistente (stesso `id`) → `lele-refresh` → dataset e modello aggiornati”.

---

## 5. Evoluzione futura (nice-to-have)
Queste sono le idee “da laboratorio” che possono arrivare dopo i TODO assoluti.

### 5.1. ML più ricco
- [ ] Embedding densi (SVD / doc2vec / altro) al posto/insieme di TF-IDF.
- [ ] MLP o altro modellino leggero sopra le feature attuali per:
  * migliorare similarità,
  * stimare una “priorità di revisita” della LeLe (ranking personalizzato).

### 5.2. UX & interfacce
- [ ] Mini UI web (HTML/JS minimale) servita da FastAPI:
  * pagina `/ui` con:
    * barra di ricerca,
    * lista risultati,
    * pannello “similar” a lato.
- [ ] Integrazione con editor (in futuro):
  * script che, mentre scrivi una LeLe, chiama `/lessons/similar` e propone link.

### 5.3. Architettura & distribuzione
- [ ] Separazione netta in moduli:
  * `lele_manager.core` (modello dati, IO),
  * `lele_manager.ml` (feature, modelli),
  * `lele_manager.cli`,
  * `lele_manager.api`.
- [ ] Packaging per PyPI:
  * pubblicare il pacchetto `lele-manager`,
  * in modo da poterlo usare/pilottare da altri tool GiadaWare.

---

## 6. Priorità operative (in ordine pratico)
1. ✅ *Già fatto*: Vault + import + ML + API + `lele-refresh`.
2. 🔴 **Subito dopo**:
   1. Test minimi (`import_from_dir`, `train_topic_model`, API base).
   2. Endpoint `POST /lessons/search`.
   3. Client CLI `lele` sopra le API.
3. 🟡 **Quando c’è fiato**:
   * versione 1.0.1 / 1.1.0 con search avanzata + CLI,
   * UI minimale,
   * miglioramenti ML/UX.
4. 🟢 **Ricerca & giocattoni**:
   * embedding più sofisticati,
   * ranking personalizzato,
   * integrazione con altri progetti (GYTE, ecc.).

---
