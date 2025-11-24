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
- [-] Step 1: Setup Python & tooling
- [ ] Step 2: Data & EDA lesson learned
- [ ] Step 3: ML classico (classificazione / similarità)
- [ ] Step 4: Pipeline & feature engineering
- [ ] Step 5: API & capstone end-to-end
