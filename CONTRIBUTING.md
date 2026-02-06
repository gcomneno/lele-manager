# Contributing to lele-manager
Grazie per l’interesse! Questo progetto accetta contributi di codice, test, documentazione e bug report.

## Quick start (sviluppo locale)
Requisiti:
- Python supportato dal progetto (vedi `pyproject.toml`)
- `git`

Setup tipico:
1. Fork + clone
2. Crea un virtualenv
3. Installa le dipendenze di sviluppo (extras `dev` se presenti)

Esempio (adatta al tuo ambiente):
```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
pip install -e ".[dev]"
```

Se .[dev] non è definito nel tuo pyproject.toml, installa invece da requirements-dev.txt (se presente) o segui le istruzioni nel README.

## Quality gates (prima di aprire una PR)
Il repo usa CI con lint + test. In locale, prima di aprire una PR:
- ruff check .
- pytest


Se il progetto usa anche formatting, aggiungi quel comando qui (es. ruff format .).

## Tipi di contributi
- Bugfix: con test che riproduce il bug (quando sensato).
- Nuove feature: piccole e focalizzate; meglio aprire prima una issue per allinearci.
- Docs: chiarimenti, esempi, troubleshooting.
- Test/CI: miglioramenti di copertura e affidabilità.

## Issue e PR: come preferiamo lavorare
Quando apri una issue, includi:
- cosa ti aspettavi
- cosa hai ottenuto
- come riprodurre (comandi / input minimi)
- OS + versione Python (se rilevante)

## Pull Request
- PR piccole e leggibili (idealmente 1 tema per PR)
- descrizione chiara del “perché” (non solo “cosa”)
- test aggiornati/aggiunti quando serve
- se tocca l’API/CLI: aggiorna anche la doc/README

## Stile e compatibilità
- Mantieni lo stile già presente nel progetto
- Evita refactor massivi dentro a bugfix piccoli
- Preferisci nomi espliciti e funzioni piccole
- Nessun dato sensibile/credenziali nei commit

## Licensing
Contribuendo, accetti che il tuo contributo venga rilasciato sotto la stessa licenza del progetto.
