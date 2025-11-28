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
```

## 🛠️ Primi tool CLI (palestra)

Alcuni comandi base già disponibili:

# Converti un CSV di lesson in JSON
python -m lele_manager.cli.csv2json samples/input.csv samples/output.json

# Monitora una directory (es. data/) per nuovi file
python -m lele_manager.cli.file_watcher data

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
    text: contenuto testuale della lesson
    source: origine (chatgpt, libro, esperimento, ecc.)
    topic: macro-tema (es. python, ml, linux, writing)
    importance: scala numerica (es. 1–5)
    tags: lista di tag separati da virgola

# Elencare le lesson
```bash
python -m lele_manager.cli.list_lessons --limit 10
```

## 🧠 ML classico: topic + similarità (Step 3–4)

LeLe Manager include una prima infrastruttura ML testuale.

### Classificatore di topic
Funzione interna:
    train_topic_model(df)

Caratteristiche:
    TF-IDF (unigrammi + bigrammi) sul testo delle lesson.
    LogisticRegression per predire il campo topic.

### Estrattore di feature unificato
Classe:
    LessonFeatureExtractor

Produce una matrice di feature combinando:
    TF-IDF del testo (text);
    meta-feature numeriche:
        lunghezza in caratteri,
        numero di parole,
        importance (se presente).

Questo estrattore è usato sia per la classificazione di topic sia per l’indice di similarità (Step 4).

### Indice di similarità tra lesson
Classe:
    LessonSimilarityIndex.from_lessons(...) / from_topic_pipeline(...)

Metodo principale:
    most_similar(query_text, top_k) -> restituisce gli ID delle lesson più simili e il relativo score (coseno).

Uso previsto:
    raccomandare lesson correlate quando ne aggiungo una nuova;
    in futuro, auto-proporre topic/cluster a partire dal testo.

## 🧪 Training del topic model (CLI)
Per addestrare il topic model a partire dal tuo archivio JSONL:
```bash
python -m lele_manager.cli.train_topic_model \
  --input data/lessons.jsonl \
  --output models/topic_model.joblib \
  --overwrite
```

Requisiti del file data/lessons.jsonl:
    formato JSONL (una lesson per riga),
    colonne minime:
        text: testo della lesson,
        topic: label di training (stringa).

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
    models/topic_model.joblib

## 🔍 Suggerire lesson simili (CLI)
Query da testo libero:
```bash
python -m lele_manager.cli.suggest_similar \
  --input data/lessons.jsonl \
  --model models/topic_model.joblib \
  --text "Con layout src/ devo configurare PYTHONPATH o usare un conftest per pytest." \
  --top-k 5 \
  --min-score 0.1
```

Query a partire da una lesson esistente:
Se nel dataset hai una colonna id (UUID o int), puoi usare una lesson come query:
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
    ID lesson,
    score di similarità,
    anteprima del testo.

## 🔐 Sicurezza
LeLe Manager non è mission-critical, ma l’obiettivo è "non far uscire la scimmia senza casco":

## 🧪 Security workflow GitHub Actions
Workflow .github/workflows/security.yml che gira su push/PR + scan settimanale:
    pip-audit per vulnerabilità sulle dipendenze Python.
    bandit per analisi statica del codice sotto src/.

✅ pre-commit minimal ma ad alto valore

File .pre-commit-config.yaml con hook:
    cleanup di base (spazi a fine riga, newline finale),
    check-yaml per non rompere i workflow,
    ruff per lint/fix del codice Python.

Attivazione locale:
```bash
pip install pre-commit
pre-commit install
```

## 📂 Dati e modelli locali
    I file reali delle lesson learned vivono in data/.
    I modelli allenati vivono in models/.
    data/ e models/ sono esclusi dal versioning (vedi .gitignore).
    Risultato: l’archivio personale e i modelli restano fuori dal repo pubblico.

## 🗺️ Roadmap (8 settimane “Scimmia Turbo”)

    Step 1 – Setup Python & tooling (Week 1–2)
    Ambiente, struttura progetto, primi tool CLI per salvare e ispezionare lesson learned.

    Step 2 – Data & EDA sulle lesson learned (Week 3–4)
    Formato di storage (JSONL/SQLite), funzioni di ingest, notebook di analisi sulle lesson (per fonte, topic, lunghezza, tempo).

        L’EDA in notebook è rimandata a una fase successiva.

    Step 3 – ML classico (Week 5–6)
    Modelli base per classificazione di topic / importanza e primi modelli di similarità (TF-IDF + k-NN).

    Step 4 – Pipeline & feature engineering (Week 6)
    Pipeline scikit-learn completa: testo → feature → modello (topic),
    estrattore di feature condiviso (TF-IDF + meta-feature),
    CLI di training (train_topic_model) e similarity (suggest_similar).

    Step 5 – API & capstone end-to-end (Week 7–8)
    Servizio FastAPI: endpoints per aggiungere, cercare e recuperare lesson simili; tests, README, (opzionale) Docker.

### ✅ Progress

✅ Step 1 – Setup Python & tooling
✅ Step 2 – Data & formato lesson learned (EDA in notebook rinviata a fase successiva)
✅ Step 3 – ML classico (classificazione / similarità)
✅ Step 4 – Pipeline & feature engineering (topic + indice di similarità)
Step 5 – API & capstone end-to-end
