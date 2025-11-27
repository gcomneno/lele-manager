# LeLe Manager 🐒 (Lesson-Learned Manager)
Sistema ML end-to-end per gestire e cercare le mie "lesson learned" testuali:
raccolta, tagging, ricerca e suggerimenti intelligenti.

Ogni volta che imparo qualcosa (da ChatGPT, da libri, da esperimenti), LeLe Manager diventa il mio archivio centrale:
- aggiungo una lesson con testo + metadati (data, fonte, topic, importanza);
- posso cercare per testo libero, tag, periodo;
- posso vedere lezioni simili o correlate;
- nel tempo il sistema impara a classificare e suggerire in autonomia;

## Caratteristiche (obiettivo)
- 📥 **Raccolta veloce** delle lesson learned via CLI e API.
- 🏷️ **Tagging e metadati**: data, fonte, topic, importanza.
- 🔍 **Ricerca** full-text e per filtri (topic, periodo, fonte).
- 🤝 **Similarità**: suggerimento di lesson correlate a quella che sto scrivendo.
- 🧠 In prospettiva: **classificazione automatica** per tema/cluster e ranking per importanza.

## Stack tecnico (previsto)
- Python 3.13
- pandas/numpy per analisi dati
- scikit-learn per ML classico (classificatori, KNN per similarità, ecc.)
- (eventuale) piccolo MLP per migliorare embedding/scoring
- FastAPI+Uvicorn per esporre API
- Storage: JSONL/SQLite (a seconda della fase del progetto)

## Setup
Clona il repository e crea un ambiente virtuale:

```bash
git clone git@github.com:gcomneno/lele-manager.git
cd lele-manager
```

```bash
python -m venv .venv
source .venv/bin/activate  # su Windows: .venv\Scripts\activate

pip install -e .[dev]
```

Esempio di utilizzo dei primi tool CLI (palestra):

```bash
python -m lele_manager.cli.csv2json samples/input.csv samples/output.json
python -m lele_manager.cli.file_watcher data
```

## Uso rapido (CLI lesson learned)

Aggiungere una lesson:
```bash
python -m lele_manager.cli.add_lesson \
  --text "Con layout src/ devo configurare PYTHONPATH o usare un conftest per pytest." \
  --source chatgpt \
  --topic python \
  --importance 4 \
  --tags "python,pytest,tooling"
```

Elencare le lesson:
```bash
python -m lele_manager.cli.list_lessons --limit 10
```

## 🔐 Sicurezza
LeLe Manager non è mission-critical, ma cerco comunque di "non far uscire la scimmia senza casco":

- **Security workflow GitHub Actions**
  - Workflow `.github/workflows/security.yml` che gira su push/PR + weekly scan:
    - `pip-audit` per vulnerabilità sulle dipendenze Python.
    - `bandit` per analisi statica del codice sotto `src/`.
- **pre-commit minimal ma ad alto valore**
  - `.pre-commit-config.yaml` con:
    - cleanup di base (spazi a fine riga, newline finale),
    - `check-yaml` per non rompere i workflow,
    - `ruff` per lint/fix del codice Python.
  - Attivazione locale:
    ```bash
    pip install pre-commit
    pre-commit install
    ```
- **Dati locali**
  - I file reali delle lesson learned vivono in `data/` e sono esclusi dal versioning (vedi `.gitignore`), così l’archivio personale resta fuori dal repo pubblico.

## Roadmap (8 settimane “Scimmia Turbo”)

- **Step 1 – Setup Python & tooling (Week 1–2)**
  Ambiente, struttura progetto, primi tool CLI per salvare e ispezionare lesson learned.

- **Step 2 – Data & EDA sulle lesson learned (Week 3–4)**
  Formato di storage (JSONL/SQLite), funzioni di ingest, notebook di analisi sulle lesson (per fonte, topic, lunghezza, tempo).

- **Step 3 – ML classico (Week 5–6)**
  Modelli base per classificazione di topic / importanza e primi modelli di similarità (TF-IDF + k-NN).

- **Step 4 – Pipeline & feature engineering (Week 6)**
  Pipeline scikit-learn completa: testo → feature → modello + API interne per suggerimenti di lesson simili.

- **Step 5 – API & capstone end-to-end (Week 7–8)**
  Servizio FastAPI: endpoints per aggiungere, cercare e recuperare lezioni simili; tests, README, (opzionale) Docker.

## Progress
- [X] Step 1: Setup Python & tooling
- [X] Step 2: Data & EDA lesson learned (“L’EDA in notebook è rimandata a una fase successiva”.)
- [ ] Step 3: ML classico (classificazione / similarità)
- [ ] Step 4: Pipeline & feature engineering
- [ ] Step 5: API & capstone end-to-end
