# Politica linguistica della documentazione

[English](../documentation-policy.md) | [Italiano](documentation-policy.md)

## Lingua canonica

L'inglese è la lingua canonica e predefinita della documentazione pubblica
mantenuta. L'italiano è una traduzione ufficialmente mantenuta per le famiglie
di documenti indicate come bilingui più avanti.

Quando il testo inglese e quello italiano divergono, il documento inglese è la
fonte autorevole. Una traduzione deve preservare requisiti, esempi, avvertenze,
limitazioni e significato tecnico; non deve diventare un riassunto abbreviato.

Comandi, opzioni CLI, endpoint HTTP, simboli Python, variabili d'ambiente,
percorsi, nomi di file e snippet di codice non vengono mai tradotti.

## Nomi e navigazione

- I documenti nella root usano `.it.md` per il mirror italiano:
  `README.md` / `README.it.md`, `ROADMAP.md` / `ROADMAP.it.md` e
  `CONTRIBUTING.md` / `CONTRIBUTING.it.md`.
- I documenti canonici sotto `docs/` sono in inglese.
- Le traduzioni italiane mantenute sotto `docs/it/` preservano lo stesso nome
  di file e la stessa struttura relativa.
- Ogni coppia mantenuta inizia con collegamenti reciproci visibili
  `English` e `Italiano`.
- I link interni devono restare nella lingua del lettore quando esiste un
  mirror. In caso contrario possono puntare alla fonte canonica inglese.

## Inventario e copertura

| Percorso o famiglia documentale | Lingua prima della #135 | Politica dopo la #135 | Motivazione |
|---|---|---|---|
| `README.md` | Prevalentemente italiano | Bilingue e mantenuto; inglese canonico | Introduzione utente e riferimento principale del prodotto |
| `README.it.md` | Assente | Bilingue e mantenuto; mirror italiano | Punto di ingresso italiano ufficiale |
| `ROADMAP.md` | Prevalentemente italiano | Bilingue e mantenuto; inglese canonico | Direzione e stato pubblico del progetto |
| `ROADMAP.it.md` | Assente | Bilingue e mantenuto; mirror italiano | Roadmap italiana ufficiale |
| `CONTRIBUTING.md` | Prevalentemente italiano | Bilingue e mantenuto; inglese canonico | Flusso pubblico per i contributor |
| `CONTRIBUTING.it.md` | Assente | Bilingue e mantenuto; mirror italiano | Guida italiana ufficiale per i contributor |
| `CHANGELOG.md` | Italiano e inglese mescolati | Fonte tecnica/release solo inglese | Le voci storiche restano invariate; le nuove voci usano l'inglese |
| `RELEASE_NOTES.md` | Inglese | Documento storico/archivio solo inglese | Le note storiche non sono mantenute come manuale bilingue |
| `frontend/README.md` | Inglese | Artefatto generato | Contenuto scaffold Vite/Svelte upstream; l'eventuale guida specifica richiede un lavoro separato |
| `.github/pull_request_template.md` | Prevalentemente italiano | Metadato contributor solo inglese | Flusso predefinito del repository con controlli per la sincronizzazione bilingue |
| `docs/documentation-policy.md` | Assente | Bilingue e mantenuto; inglese canonico | Definisce il contratto linguistico del repository |
| `docs/it/documentation-policy.md` | Assente | Bilingue e mantenuto; mirror italiano | Politica italiana ufficiale |
| `docs/projection-store.md` | Inglese | Bilingue e mantenuto; inglese canonico | Contratto storage corrente per i contributor |
| `docs/it/projection-store.md` | Assente | Bilingue e mantenuto; mirror italiano | Traduzione italiana ufficiale del contratto storage |
| `docs/brand-design-system.md` | Assente | Bilingue e mantenuto; inglese canonico | Contratto mantenuto di brand e design system del prodotto |
| `docs/it/brand-design-system.md` | Assente | Bilingue e mantenuto; mirror italiano | Traduzione ufficiale italiana di brand e design system |
| `docs/adr/0001-storage-backend.md` | Prevalentemente italiano | Fonte tecnica solo inglese | Gli ADR sono record tecnici canonici mantenuti in inglese |
| `docs/gui-design.md` | Prevalentemente italiano | Documento storico/archivio | Record di design GUI completato, conservato nella lingua originale |
| `docs/phase-4-issue.md` | Prevalentemente italiano | Documento storico/archivio | Documento locale di tracking completato, senza obbligo di traduzione |

Anche gli issue form rivolti ai contributor, pur non essendo Markdown,
influenzano l'esperienza linguistica del repository:

| Percorso | Politica dopo la #135 |
|---|---|
| `.github/ISSUE_TEMPLATE/bug_report.yml` | Metadato contributor solo inglese |
| `.github/ISSUE_TEMPLATE/feature_request.yml` | Metadato contributor solo inglese |

Ogni esclusione è deliberata: scaffold generati, record storici e fonti
tecniche solo inglese non creano un obbligo di sincronizzazione italiana.

## Flusso di sincronizzazione

Una pull request che modifica un documento canonico bilingue deve:

1. valutare se il mirror italiano richiede la stessa modifica;
2. aggiornare entrambi i file nella stessa pull request quando cambia il
   significato tecnico;
3. preservare i collegamenti reciproci per la selezione della lingua;
4. mantenere invariati token tecnici e snippet;
5. eseguire i controlli documentali.

Eseguire i controlli mirati con:

```bash
pytest tests/test_documentation.py
```

I controlli verificano le coppie obbligatorie, i selettori linguistici
reciproci, la navigazione root nella stessa lingua e i link relativi nei
documenti bilingui mantenuti. Non tentano traduzioni automatiche né confronti
semantici automatici; la parità semantica resta responsabilità della review.

## Politica ADR

Gli Architecture Decision Record sono record tecnici canonici solo inglese.
Il contenuto dell'ADR esistente viene migrato in inglese senza cambiare la
decisione registrata. I nuovi ADR devono essere scritti in inglese e non
richiedono mirror italiani, salvo modifica esplicita di questa politica.

## Politica changelog

`CHANGELOG.md` è la cronologia release canonica in inglese. Le voci storiche
che mescolano le lingue vengono conservate per non riscrivere la storia delle
release. Le nuove voci devono usare l'inglese.

## Non obiettivi

Questa politica non introduce internazionalizzazione della GUI, localizzazione
di CLI o API, selezione dinamica della lingua, traduzione automatica, un
generatore di sito documentale o una piattaforma di gestione traduzioni.
