# Contribuire a LeLe Manager

[English](CONTRIBUTING.md) | [Italiano](CONTRIBUTING.it.md)

Grazie per l'interesse. Il progetto accetta contributi di codice, test,
documentazione e segnalazioni di bug.

## Avvio rapido dello sviluppo locale

Requisiti:

- una versione Python supportata dal progetto; vedere `pyproject.toml`;
- `git`.

Setup tipico:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
pip install -e ".[dev]"
```

## Quality gate

Prima di aprire una pull request eseguire:

```bash
ruff check .
mypy src/lele_manager
pytest
```

Le modifiche frontend o GUI possono richiedere anche:

```bash
./scripts/build-gui.sh
cd frontend
npm install
npm run test:e2e
```

Durante lo sviluppo usare il più piccolo insieme di verifiche pertinente;
prima della revisione finale eseguire tutti i gate richiesti.

## Tipi di contributo

- I bugfix dovrebbero includere un test che riproduce il problema quando è
  ragionevole.
- Le nuove feature devono restare focalizzate; aprire prima una issue quando
  serve allineamento progettuale.
- Le modifiche documentali devono migliorare chiarezza, esempi, navigazione o
  troubleshooting senza alterare involontariamente il significato tecnico.
- Le modifiche a test e CI devono migliorare copertura o affidabilità senza
  introdurre infrastruttura non necessaria.

## Issue e pull request

Una issue utile include:

- comportamento atteso;
- comportamento osservato;
- passi, comandi o input minimi per riprodurre;
- sistema operativo e versione Python quando pertinenti.

Le pull request devono:

- affrontare un unico tema coerente;
- spiegare perché la modifica è necessaria, non soltanto cosa cambia;
- aggiornare o aggiungere test quando opportuno;
- aggiornare la documentazione API, CLI o utente quando cambia il comportamento;
- evitare refactor massivi non correlati.

## Documentazione bilingue

L'inglese è la lingua canonica della documentazione. I mirror italiani sono
ufficialmente mantenuti per le coppie dichiarate in
[`docs/it/documentation-policy.md`](docs/it/documentation-policy.md).

Quando una pull request modifica un documento canonico bilingue:

- valutare il mirror italiano nella stessa pull request;
- aggiornare entrambe le versioni quando cambiano requisiti, esempi,
  avvertenze, limitazioni o significato tecnico;
- preservare i collegamenti reciproci di selezione lingua;
- mantenere invariati comandi, opzioni, endpoint, simboli, percorsi, nomi di
  file e snippet;
- eseguire:

```bash
pytest tests/test_documentation.py
```

I documenti storici, generati, interni e le fonti tecniche solo inglese sono
esclusi soltanto come dichiarato nella politica documentale.

## Stile e compatibilità

- Seguire lo stile già usato nell'area modificata.
- Evitare refactor ampi dentro piccoli bugfix.
- Preferire nomi espliciti e funzioni piccole.
- Non committare segreti, credenziali, dati personali del vault, dataset o
  modelli.
- Preservare la compatibilità con le versioni Python e la toolchain frontend
  supportate.

## Licenza

Contribuendo, accetti che il contributo venga rilasciato con la stessa licenza
del progetto.
