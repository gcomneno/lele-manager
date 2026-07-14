# ADR 0001: backend di storage per LeLe Manager

- **Stato:** Proposto
- **Data:** 2026-07-13
- **Issue:** [#91 — Compare storage backends](https://github.com/gcomneno/lele-manager/issues/91)
- **Epic:** [#82 — TritaLeLe Knowledge Ingestion Pipeline](https://github.com/gcomneno/lele-manager/issues/82)

## Contesto

LeLe Manager è un'applicazione personale e local-first. Il repository descrive spesso il flusso come `vault Markdown -> JSONL -> ML -> API`, ma il codice attuale non ha una sola sorgente autoritativa applicata in modo uniforme:

- `src/lele_manager/cli/import_from_dir.py::import_from_dir` legge i file Markdown, usa l'`id` nel frontmatter (o lo deriva dal path), normalizza metadati e body e produce record che includono anche `path`, `frontmatter` e `frontmatter_hash`;
- `src/lele_manager/core/vault.py::write_lesson_markdown` scrive body e frontmatter nel vault, mentre `import_vault_to_jsonl` ricostruisce interamente il JSONL dal vault;
- `src/lele_manager/api/server.py::create_vault_lesson` e `update_lesson` scrivono prima il Markdown e poi reimportano il vault. Questo rende il vault la sorgente di authoring nel flusso GUI corrente;
- la stessa API usa però `load_lessons_df` per leggere direttamente JSONL e `append_lesson_to_jsonl` per `POST /lessons`, che non scrive nel vault;
- le CLI storiche `src/lele_manager/cli/add_lesson.py` e `list_lessons.py` usano direttamente `src/lele_manager/core/storage.py`, basato su append e scansione completa del JSONL;
- la CLI principale `src/lele_manager/cli/lele.py` e la GUI in `frontend/src/lib/api.ts` passano invece dall'API;
- training e similarità ricevono `pandas.DataFrame`: `src/lele_manager/cli/train_topic_model.py` e `suggest_similar.py` leggono JSONL, mentre `src/lele_manager/api/server.py::train_topic` e `build_similarity_index` usano il DataFrame caricato dallo stesso dataset. Il modello serializzato da `src/lele_manager/ml/topic_model.py` è un artefatto derivato;
- `scripts/lele-api-refresh.sh` rende esplicito il rebuild completo `vault -> data/lessons.jsonl -> models/topic_model.joblib`;
- `tests/test_api_vault.py` verifica write-back Markdown e reimport, mentre `tests/test_lessons_storage.py` e `tests/test_add_lesson_cli.py` preservano il comportamento JSONL diretto;
- i percorsi predefiniti in `src/lele_manager/core/paths.py` collocano dataset e modello nelle directory XDG. `.gitignore` esclude dati, database e modelli locali, quindi oggi Git versiona il vault dell'utente solo se questo è gestito separatamente, non `data/lessons.jsonl` nel repository.

Di conseguenza, **oggi il vault è la sorgente intenzionale del flusso completo, ma JSONL è ancora uno storage operativamente mutabile e può contenere record che non esistono nel vault**. Questa ambiguità va risolta prima di aggiungere altri flussi di ingestione. L'ADR definisce lo stato obiettivo; non cambia il comportamento corrente e non implementa la successiva astrazione.

### Livelli architetturali

| Livello | Stato attuale | Stato deciso |
|---|---|---|
| Vault Markdown | Authoring e write-back GUI; rebuild del dataset | Sorgente autoritativa delle lesson approvate |
| Storage applicativo | JSONL letto o scritto direttamente da più componenti | SQLite locale, ricostruibile e interrogabile |
| JSONL | Dataset, storage mutabile, input ML e fixture | Snapshot derivato per export, interoperabilità, fixture e ML |
| API / CLI / GUI | Accesso misto: API o JSONL diretto | Accesso alle lesson tramite confine applicativo/storage |
| Topic e similarità | DataFrame da JSONL più modello `joblib` | Artefatti derivati da uno snapshot identificabile dello storage |
| Export e integrazioni | Markdown da risultati API; JSONL implicito | Operazioni esplicite, separate dal backend |

## Requisiti e criteri decisionali

La scelta deve:

1. restare semplice da installare e gestire per un'app locale Python;
2. conservare portabilità, inspectability e possibilità di recupero manuale;
3. supportare upsert, cancellazioni e sostituzioni complete senza rewrite non protetti;
4. offrire transazioni, vincoli, query, filtri e indici;
5. sostenere letture concorrenti e scritture occasionali realistiche per FastAPI/GUI locale;
6. avere una strategia esplicita per schema e migrazioni;
7. consentire full-text search senza renderla un prerequisito di portabilità;
8. funzionare bene sia con dataset piccoli sia con una crescita moderata;
9. integrarsi con Python, Pandas e scikit-learn;
10. consentire backup, export e test isolati;
11. non introdurre un servizio esterno senza un requisito concreto;
12. minimizzare il costo di migrazione dal codice e dai dati attuali;
13. mantenere Markdown e JSONL come formati interoperabili, senza confonderli con il database applicativo;
14. preparare i confini richiesti dalle issue [#92](https://github.com/gcomneno/lele-manager/issues/92), [#93](https://github.com/gcomneno/lele-manager/issues/93) e [#94](https://github.com/gcomneno/lele-manager/issues/94).

## Opzioni considerate

### JSONL

JSONL ha il costo concettuale e operativo più basso: è UTF-8, leggibile con strumenti comuni, diffabile per riga e già consumato da Pandas e dagli script del progetto. È adatto a export, fixture, scambio e snapshot di training.

Come storage mutabile, però, l'append non garantisce unicità dell'ID e un upsert o delete richiede leggere e riscrivere il file. Il codice corrente mostra entrambi i modelli: `core.storage.append_lesson` appende, mentre `core.vault.upsert_jsonl_lesson` e `import_vault_to_jsonl` riscrivono. Non ci sono transazioni multi-record, schema o indici; lettura e filtri richiedono scansione e materializzazione. Lock, scrittura atomica e recovery dovrebbero essere implementati dall'applicazione. La buona compatibilità teorica con Git non cambia il fatto che i dati locali sono esclusi dal Git del repository.

**Valutazione:** mantenere JSONL come formato derivato, non come backend applicativo primario.

### SQLite

SQLite è embedded, serverless e memorizza normalmente il database in un singolo file. Python espone `sqlite3` nella standard library; la documentazione Python precisa però che il modulo dipende dalla libreria SQLite ed è opzionale per chi distribuisce una build CPython. Questo va verificato sulle piattaforme supportate, ma non richiede una nuova dipendenza Python nel packaging ordinario.

Fornisce transazioni, vincoli, query SQL, indici, update e delete efficienti e una storia di migrazioni tramite versione dello schema. È adatto a una singola applicazione locale con molti read e scritture occasionali. In modalità WAL lettori e writer possono procedere contemporaneamente, ma resta un solo writer alla volta e l'applicazione deve gestire timeout/`SQLITE_BUSY`; il WAL non è adatto a filesystem di rete e i file `-wal`/`-shm` fanno parte dello stato da considerare nelle copie.

FTS5 offre ricerca full-text indicizzata, ma la sua disponibilità dipende da come SQLite è stato compilato. Le build e i pacchetti supportati devono provarla; la ricerca di base deve poter funzionare senza FTS5. Backup coerenti possono usare la Backup API o `VACUUM INTO`; copiare alla cieca il solo file durante una sessione WAL non è una strategia di backup.

L'integrazione con Pandas può avvenire tramite query/record convertiti in DataFrame al confine ML. Il database non va versionato in Git: il vault e gli export testuali restano i formati versionabili e recuperabili.

**Valutazione:** miglior corrispondenza al workload locale CRUD + ricerca di LeLe Manager.

### DuckDB

DuckDB è embedded, transazionale e ottimizzato per workload analitici colonnari e operazioni bulk. Il client Python interroga direttamente DataFrame Pandas, Arrow e altri formati, quindi è molto attraente per EDA, statistiche e preparazione di dataset.

Non è però una dipendenza attuale di `pyproject.toml`. La documentazione DuckDB indica come modalità embedded read-write ordinaria un singolo processo, nel quale sono possibili writer concorrenti. La scrittura multi-processo è tecnicamente possibile tramite il protocollo remoto Quack, ancora beta; DuckLake con catalogo PostgreSQL è un'altra alternativa, ma introduce infrastruttura esterna. Queste modalità aggiungono costo operativo senza soddisfare meglio di SQLite il requisito locale, semplice, embedded e orientato al CRUD. Inoltre, molte piccole transazioni non sono il workload primario di DuckDB e i vantaggi colonnari sono limitati per il dataset personale attuale.

**Valutazione:** non backend CRUD primario; candidato futuro per analisi secondaria su snapshot JSONL/Parquet o, se utile, sui dati SQLite.

### Storage document-oriented embedded o locale

Questa categoria comprende librerie in-process come TinyDB e prodotti embedded analoghi, non un servizio di rete. TinyDB, per esempio, persiste documenti Python in un file JSON e offre una query API. La corrispondenza con frontmatter flessibile è naturale e il debug può restare semplice.

Le garanzie su transazioni, concorrenza, indici, full-text search e migrazioni variano però per prodotto. Una soluzione JSON-file ripropone parte dei problemi di rewrite e locking di JSONL; una soluzione più completa aggiunge una dipendenza e un ecosistema specifici. Le lesson hanno già campi stabili e relazioni utili (ID univoco, tag, provenance, generazione di sync): la flessibilità schemaless non compensa la perdita delle funzionalità mature disponibili in SQLite. Campi futuri possono essere gestiti con migrazioni e, se necessario, una colonna JSON per metadati non ancora promossi.

**Valutazione:** respinto per il backend primario; nessun vantaggio concreto sufficiente rispetto a SQLite.

### Document store server esterno

MongoDB o un equivalente offre documenti flessibili, query, indici, concorrenza e, in configurazioni appropriate, transazioni. È però un processo o servizio separato da installare, configurare, proteggere, aggiornare e sottoporre a backup. Alcune garanzie dipendono anche dalla topologia di deployment.

LeLe Manager è oggi personale, locale e distribuibile come applicazione Python. Non esistono requisiti di replica, sharding, accesso remoto multiutente o volume che giustifichino tale costo operativo.

**Valutazione:** respinto. Potrà essere riesaminato solo in presenza di requisiti distribuiti reali.

## Matrice comparativa

Legenda: `++` molto favorevole, `+` favorevole, `0` neutro/misto, `-` sfavorevole, `--` molto sfavorevole. I punteggi sono valutazioni progettuali per LeLe Manager, non benchmark universali.

| Criterio | JSONL | SQLite | DuckDB | Document store embedded | Document store server |
|---|---:|---:|---:|---:|---:|
| Semplicità operativa local-first | ++ | ++ | + | + | -- |
| Dipendenze Python/runtime | ++ | ++\* | - | - | -- |
| Portabilità del dato | ++ | + | + | 0 | 0 |
| Lettura e debug manuale | ++ | + (CLI/tool) | 0 (tool) | +/0 | 0 |
| Transazioni e consistenza | -- | ++ | ++ | variabile | ++ |
| Update e delete | -- | ++ | + | + | ++ |
| Query, filtri e indici | -- | ++ | ++ | +/0 | ++ |
| CRUD interattivo | - | ++ | 0/- | +/0 | ++ |
| Concorrenza per app locale | -- | + | 0/- | variabile | ++ |
| Schema, vincoli e migrazioni | -- | ++ | + | 0/- | + |
| Full-text search | -- | +\* | -/0 | variabile | + |
| Dataset piccoli | ++ | ++ | + | + | - |
| Crescita moderata | - | ++ | ++ analitica | 0/+ | ++ |
| Pandas / scikit-learn | ++ | + | ++ | 0/+ | + |
| Backup coerente | 0 | ++ | + | variabile | + ma operativo |
| Diff/versionamento Git | ++ | -- | -- | +/-- secondo formato | -- |
| Test isolati e in-memory | + | ++ | ++ | + | -- |
| Packaging desktop/locale | ++ | ++\* | 0/- | 0/- | -- |
| Interoperabilità strumenti | ++ | ++ | ++ | 0/+ | + |
| Costo migrazione attuale | ++ | + | 0/- | 0/- | -- |

`\*` La disponibilità di `sqlite3` e soprattutto FTS5 deve essere verificata nelle build Python/SQLite effettivamente distribuite.

## Decisione

1. **Source of truth e identità:** il vault Markdown diventa la sorgente autoritativa delle lesson approvate. Il body autoritativo vive nel corpo del file e i metadati nel frontmatter. La convenzione canonica lega identità e collocazione: `topic` corrisponde alla prima directory del path relativo e `id` al path relativo senza estensione `.md`. Di conseguenza, spostare o rinominare un file richiede di aggiornare `id`; cambiare la directory topic richiede anche di aggiornare `topic`. Con la convenzione attuale un move o rename è una migrazione d'identità e può invalidare riferimenti esterni.
2. **Backend applicativo:** SQLite diventa lo storage locale interrogabile e indicizzato. È una proiezione ricostruibile del vault, non una seconda fonte autoritativa indipendente.
3. **Ruolo di JSONL:** JSONL resta uno snapshot derivato per export, interoperabilità, fixture e input riproducibile di training/analisi. Durante la migrazione può restare un backend di compatibilità dietro l'astrazione della #92, ma non è il backend finale né il luogo canonico delle modifiche.
4. **Ruolo di DuckDB:** nessun ruolo nel CRUD primario. Può essere rivalutato come strumento analitico secondario quando volume o query colonnari lo giustificheranno, lavorando su export o snapshot.
5. **Storage document-oriented:** sia il document store embedded sia il server esterno sono respinti. Il primo non offre un vantaggio sufficiente rispetto a SQLite per consistenza e query; il secondo introduce operatività sproporzionata senza requisito distribuito.
6. **Servizi e confine della #92:** le operazioni user-facing di create, update e delete passano da un servizio di authoring, che valida e scrive il vault. Un servizio di sincronizzazione legge il vault e aggiorna un projection store interrogabile; eventuali `upsert`, `delete` e `replace-all` sono capacità interne usate dal sync, non operazioni offerte alla business logic o agli endpoint per modificare direttamente SQLite. Servizi di export separati leggono uno snapshot della proiezione e producono JSONL o altri formati. L'astrazione della #92 rappresenta il minimo contratto della proiezione senza esporre JSONL, SQLite, SQL, Pandas o filesystem.
7. **Stato della proiezione:** ogni proiezione registra la generazione o il fingerprint del vault da cui deriva. Un mismatch deve essere rilevabile ed esposto; API e CLI non devono dichiarare corrente una proiezione stale. La policy concreta potrà imporre il sync, restituire un errore esplicito o operare in modalità degradata segnalata, ma lo stale silenzioso è vietato.

Questa è una decisione sullo **stato obiettivo**. La #92 deve inizialmente preservare il comportamento JSONL richiesto dalla propria issue; il passaggio del default a SQLite avverrà solo dopo parità verificata e riconciliazione dei dati JSONL-only.

## Motivazione

SQLite risolve i limiti già visibili nel codice: append duplicabili, rewrite completo per upsert, scansioni per ogni filtro e assenza di transazioni. Lo fa con un componente embedded coerente con il packaging e il workload locale, senza imporre un servizio.

Mantenere Markdown come autorità conserva l'esperienza di authoring, la leggibilità, la portabilità e la storia Git del vault. Mantenere JSONL come snapshot conserva l'integrazione già funzionante con Pandas/scikit-learn e con strumenti esterni, senza chiedergli di essere anche un database mutabile.

La separazione elimina inoltre una falsa scelta: Markdown, SQLite e JSONL non competono per lo stesso ruolo. Sono rispettivamente contenuto autoritativo, indice/storage applicativo e formato di scambio o dataset derivato.

## Conseguenze positive

- ID univoci, vincoli, update, delete e rebuild possono essere atomici nello storage applicativo.
- API, CLI e GUI possono condividere query e ordinamento senza caricare sempre l'intero dataset.
- Indici ordinari e, dove disponibile, FTS5 preparano ricerca e filtri più efficienti.
- SQLite è facile da creare in un file temporaneo o in memoria nei test.
- Il vault resta leggibile, modificabile con editor comuni e versionabile indipendentemente dall'app.
- JSONL resta semplice da esportare, ispezionare e caricare in Pandas.
- Il database può essere ricostruito dal vault dopo corruzione o cambio schema.
- Il confine storage rende sostituibile il backend senza esporlo ai consumer esterni.

## Conseguenze negative e trade-off

- Esisteranno migrazioni di schema SQLite e una versione dello schema da mantenere.
- Il file SQLite non è adatto a diff o merge Git e non deve essere trattato come backup del vault.
- Il coordinamento tra commit filesystem e transazione SQLite non è una singola transazione ACID. Serve un protocollo di sincronizzazione esplicito.
- WAL, timeout, checkpoint e gestione di `SQLITE_BUSY` richiedono scelte operative e test; un singolo writer resta il limite realistico.
- FTS5 non può essere assunto disponibile ovunque: serve feature detection e fallback.
- La conversione verso DataFrame diventa un adattatore esplicito invece di un semplice `pd.read_json`.
- Durante la migrazione coesisteranno due backend, aumentando temporaneamente la superficie di test.
- I record creati solo in JSONL devono essere identificati e riconciliati prima che il vault possa essere dichiarato unica autorità operativa.

## Piano di adozione

Questo piano appartiene alle issue successive; la #91 non lo implementa.

1. Nella #92, introdurre il confine storage e un adapter JSONL che preservi il comportamento corrente.
2. Introdurre il servizio di authoring come unico ingresso user-facing per create, update e delete delle lesson approvate; deve validare e scrivere il vault Markdown.
3. Introdurre il servizio di sincronizzazione, separato dall'authoring, che pubblica snapshot della proiezione e ne registra generazione o fingerprint; rimuovere dalle regole di business la conoscenza di path JSONL, `pd.read_json` e append/rewrite senza cambiare ancora il backend predefinito.
4. Aggiungere un adapter SQLite dietro lo stesso confine, con versione dello schema e migrazioni esplicite. Le sue capacità incrementali e transazionali restano interne al sync.
5. Eseguire un inventario read-only di vault e JSONL. Segnalare duplicati, record JSONL-only, ID mancanti e conflitti; **non modificare automaticamente i Markdown**.
6. Importare il vault in un database SQLite nuovo e confrontare conteggi, ID, campi, hash e risultati delle query con il backend JSONL.
7. Solo dopo la riconciliazione, spostare in modo graduale le letture di API e CLI sul backend SQLite; GUI e CLI principale restano consumer dell'API e le scritture continuano a passare dall'authoring del vault.
8. Separare i servizi di export e generare JSONL esplicitamente come pubblicazione atomica dello stesso snapshot, usandolo per le pipeline non ancora migrate.
9. Spostare training e similarità verso uno snapshot/DataFrame ottenuto dal confine applicativo, registrandone fingerprint o generazione.
10. Eliminare gli accessi diretti a JSONL soltanto dopo test di parità, stabilizzazione e una finestra di compatibilità documentata.

## Compatibilità e migrazione

### Modello dei dati

- **Vault:** `id`, topic, source, importance, tags, date, title e provenance approvata nel frontmatter; contenuto nel body Markdown. `topic` deve coincidere con la prima directory del path relativo e `id` con l'intero path relativo senza `.md`; rename, move o cambio della directory topic richiedono l'aggiornamento coerente dei campi canonici. Metadati frontmatter sconosciuti non devono essere persi durante il round-trip.
- **SQLite:** copia interrogabile di ID, metadati e body, più informazioni di sincronizzazione come path relativo, hash del frontmatter/contenuto e generazione. La forma esatta delle tabelle e la rappresentazione dei tag sono rinviate alla #92.
- **JSONL:** rappresentazione completa e documentata di una generazione; non log append-only e non authority. L'ordine deve essere deterministico per diff e test riproducibili.
- **Modelli ML:** artefatti derivati, rigenerabili, associati al fingerprint/generazione del dataset da cui provengono.

### Aggiornamenti, cancellazioni e consistenza

Le modifiche user-facing a lesson approvate devono passare dal servizio di authoring del vault. Il projection store non è un'interfaccia di authoring. Concettualmente:

1. validare l'intera lesson;
2. scrivere o sostituire il Markdown in modo atomico;
3. far rilevare la nuova generazione del vault al servizio di sincronizzazione;
4. applicare internamente al projection store un upsert/delete opzionale o una sostituzione completa; per SQLite il sync può usare una transazione;
5. pubblicare la nuova generazione della proiezione solo a sincronizzazione conclusa;
6. invalidare o rigenerare JSONL, statistiche e modelli derivati.

Una cancellazione approvata rimuove il Markdown (la storia può restare in Git) e il successivo sync elimina la voce dalla proiezione. Se la scrittura Markdown riesce ma il sync fallisce, la proiezione precedente può restare materialmente leggibile, ma la sua generazione o fingerprint non coincide più con il vault ed è quindi stale. Il mismatch deve essere rilevato ed esposto: API e CLI non possono presentarla silenziosamente come corrente. La policy concreta — sync obbligatorio, errore esplicito o modalità degradata segnalata — è rinviata; il vault prevale, il sync è ripetibile e non si tenta un rollback distruttivo del Markdown già confermato.

Per un rebuild completo, tutti i Markdown vanno analizzati e validati prima di aprire la transazione che sostituisce il dataset. Errori o ID duplicati impediscono la pubblicazione della nuova generazione. JSONL va esportato tramite file temporaneo e rename, non aggiornato in-place riga per riga.

Non è ammesso un doppio write permanente Markdown + database senza questa regola di autorità. In particolare, un endpoint applicativo non deve aggiornare SQLite e “provare poi” a scrivere il vault lasciando ambiguo quale copia vinca.

### Rollback

- Finché SQLite non è il default, il backend JSONL resta selezionabile e i test di compatibilità garantiscono il ritorno al comportamento precedente.
- Dopo lo switch, un rollback applicativo rigenera JSONL dal vault e può usarlo temporaneamente al posto di SQLite come proiezione. Le modifiche user-facing continuano a passare dal servizio di authoring del vault: il rollback non riabilita scritture autoritative dirette su JSONL e non promuove una copia SQLite più recente del vault ad authority.
- Ogni migrazione SQLite opera su backup coerente o database ricostruibile e deve poter fallire senza modificare il vault.
- Nessuna fase di migrazione riscrive automaticamente frontmatter o body. Le correzioni segnalate dall'audit richiedono revisione esplicita.

### Strategia di test

- suite contrattuale sul minimo comune JSONL/SQLite: lettura per ID, elenco/ricerca deterministici, lettura coerente di uno snapshot, pubblicazione o sostituzione atomica dell'intero snapshot, conteggi e generazione/fingerprint;
- test specifici SQLite per transazioni e aggiornamenti incrementali del sync, senza estendere tali promesse al backend JSONL;
- golden dataset con record completi, campi opzionali, Unicode, tag e ID canonici contenenti `/`, verificando che `id` sia il path relativo senza `.md` e `topic` la prima directory;
- test di rename e move come migrazioni d'identità, incluso il possibile invalidamento di riferimenti al vecchio ID;
- parità di filtri, ordinamento e serializzazione con gli endpoint attuali;
- test di rollback su import invalido, duplicato, transazione interrotta e migrazione fallita;
- test concorrenti realistici con più reader, un writer, timeout e retry limitato;
- feature test di FTS5 nel packaging supportato e test del fallback senza FTS5;
- confronto di fingerprint fra vault, SQLite, export JSONL e input del modello;
- smoke API/CLI/GUI senza accessi diretti al formato del backend.

## Confine concettuale per la #92

Il port deve offrire capacità, senza fissare firme Python definitive:

- lettura di una lesson per ID;
- elenco e ricerca filtrata, con ordinamento e limiti deterministici;
- lettura coerente di uno snapshot;
- pubblicazione o sostituzione atomica dell'intero snapshot;
- conteggi/statistiche essenziali che evitino scansioni duplicate;
- esposizione di una generazione o fingerprint utile a cache e derivati.

L'adapter SQLite può inoltre offrire al servizio di sincronizzazione upsert, delete e transazioni come capacità interne o opzionali. Non fanno parte del minimo comune e non obbligano JSONL a simulare transazioni generali o semantiche ACID.

Restano fuori dal port:

- parsing e rendering Markdown;
- scansione e write-back del vault;
- operazioni user-facing di create, update e delete;
- import/export JSONL, Markdown o altri formati;
- costruzione di DataFrame;
- training, serializzazione e cache dei modelli;
- dettagli SQL, path del database e tipi specifici di Pandas.

L'authoring è un servizio applicativo distinto: valida le operazioni user-facing e scrive il vault. La sincronizzazione legge il vault già autoritativo, verifica la convenzione canonica di ID/topic e pubblica una nuova proiezione con `replace-all` o, se l'adapter lo consente, con upsert/delete incrementali; le transazioni SQLite sono un dettaglio di questa implementazione. L'export è un ulteriore servizio: legge uno snapshot tramite il port e serializza JSONL o altri formati.

## Impatto sulle issue successive

### #92 — Introduce storage abstraction layer

La #92 deve implementare il port minimo e l'adapter JSONL di compatibilità, preservando il comportamento esterno e le semantiche JSONL correnti, inclusi temporaneamente i flussi di scrittura legacy. Deve isolare gli accessi presenti in `core.storage`, `core.vault` e `api.server` e introdurre i confini concettuali fra authoring, sincronizzazione, projection store ed export, senza imporre nella stessa issue il passaggio definitivo delle scritture user-facing al vault. Il cutover verso l'authoring vault-only avviene in una fase successiva, dopo riconciliazione e test di parità. Nello stato obiettivo endpoint e business logic non chiamano direttamente le mutazioni del projection store; upsert/delete e transazioni SQLite appartengono al sync. Import/export non va incorporato nel repository.

### #93 — Expose lessons for external quiz and review tools

La #93 può dipendere da un contratto applicativo stabile di lesson/snapshot: get per ID, ricerca/elenco deterministici, metadati, body e generazione. La stabilità del contratto non implica però che un ID sopravviva a uno spostamento: poiché l'ID canonico deriva dal path, rename e move sono migrazioni d'identità e possono invalidare riferimenti esterni. I consumer non devono presumere la permanenza dell'ID attraverso tali operazioni. Una futura strategia di alias o una chiave esterna immutabile potrà essere valutata separatamente, senza definirne ora lo schema. Il consumer esterno non deve ricevere path SQLite, righe SQL, DataFrame o promesse sul formato JSONL interno. Un export JSONL versionato o un'API paginata possono essere trasporti dello stesso contratto. I quiz restano consumer read-only e non diventano una seconda authority.

### #94 — TritaLeLe

TritaLeLe introduce sorgenti grezze, provenance, chunking, candidati e revisione umana. I candidati **non** sono lesson approvate e non devono entrare direttamente nel vault autoritativo o nel dataset ML. Il workflow deve mantenere uno staging separato; solo l'approvazione umana produce un Markdown con ID e provenance, seguito dal sync transazionale verso SQLite e dalla rigenerazione dei derivati. Lo storage abstraction può essere esteso in futuro con un port distinto per i candidati, senza sovraccaricare il repository delle lesson.

Questa separazione rende deterministico il passaggio `source material -> candidate -> approval -> vault -> storage -> export/ML` e impedisce che testo non revisionato alteri ricerca, topic o similarità.

## Alternative rinviate

- FTS5 come requisito obbligatorio: rinviato finché packaging e tokenizer non sono verificati; SQLite resta la scelta anche con ricerca fallback.
- DuckDB come layer analitico o export Parquet: rinviato finché non esiste un workload analitico che ne dimostri il valore.
- Metadati interamente normalizzati rispetto a colonna JSON per campi estesi: decisione di schema della #92, purché ID e campi interrogati abbiano vincoli/indici espliciti.
- Change log, event sourcing o tombstone permanenti: non richiesti oggi; Git del vault e generazioni di sync coprono il recupero iniziale.
- Database server multiutente: rinviato finché non esistono requisiti di accesso remoto, replica o writer multipli.

## Condizioni che potrebbero far riesaminare la decisione

La decisione va riesaminata se si verifica almeno una di queste condizioni:

- LeLe Manager diventa multiutente o richiede writer distribuiti/remoti;
- il vault Markdown non può più rappresentare senza perdita i contenuti o la provenance approvata;
- volume e query analitiche rendono SQLite misurabilmente inadeguato nonostante indici e query corrette;
- una pipeline richiede scansioni colonnari/Parquet come workload dominante, rendendo DuckDB candidato primario;
- packaging target rilevanti non forniscono in modo affidabile `sqlite3` e non è accettabile distribuire SQLite;
- sync filesystem/database causa problemi operativi non risolvibili con generazioni, rebuild atomico e rilevamento stale;
- emerge un requisito concreto per documenti eterogenei con query che uno schema SQLite più campi JSON non soddisfa.

## Rischi e domande aperte

- Quali record reali esistono solo in JSONL e come verranno promossi nel vault senza perdere `created_at` o altri campi?
- Qual è la policy UX per delete: rimozione fisica versionata in Git o tombstone esplicito?
- Quali metadati di provenance della #94 devono diventare campi interrogabili e quali restano estensioni del frontmatter?
- Quali build Python e sistemi operativi fanno parte della matrice di packaging per `sqlite3` e FTS5?
- Il processo API sarà l'unico writer SQLite o devono essere coordinati anche CLI/processi separati?
- Quale strategia di rilevamento cambiamenti del vault (refresh esplicito, watcher o scan all'avvio) soddisfa l'uso reale? Questa scelta non cambia l'autorità del vault.
- Quale UX deve accompagnare una migrazione d'identità dovuta a rename o move, dato che l'ID canonico cambia e i riferimenti esterni possono diventare invalidi?
- Quale policy concreta deve applicare API/CLI quando la generazione della proiezione non coincide con il fingerprint del vault: sync obbligatorio, errore esplicito o modalità degradata segnalata?
- In futuro servono alias o una chiave esterna immutabile per riferimenti durevoli? La convenzione canonica attuale resta `id = path relativo senza .md` e questa ADR non ne definisce lo schema.

## Riferimenti

### Repository e pianificazione

- [Issue #82 — Epic: TritaLeLe Knowledge Ingestion Pipeline](https://github.com/gcomneno/lele-manager/issues/82)
- [Issue #91 — Compare storage backends](https://github.com/gcomneno/lele-manager/issues/91)
- [Issue #92 — Introduce storage abstraction layer](https://github.com/gcomneno/lele-manager/issues/92)
- [Issue #93 — Expose lessons for external quiz and review tools](https://github.com/gcomneno/lele-manager/issues/93)
- [Issue #94 — Add raw knowledge ingestion workflow (TritaLeLe)](https://github.com/gcomneno/lele-manager/issues/94)
- `README.md`, sezioni “LeLe Vault”, “ML classico”, “API” e “GUI”
- `ROADMAP.md`, sezioni sul flusso vault/JSONL/ML/API e sullo stato attuale
- `src/lele_manager/cli/import_from_dir.py::{LeLeRecord,import_from_dir}`
- `src/lele_manager/core/vault.py::{write_lesson_markdown,import_vault_to_jsonl,upsert_jsonl_lesson}`
- `src/lele_manager/core/storage.py::{append_lesson,load_lessons,iter_lessons}`
- `src/lele_manager/api/server.py::{load_lessons_df,append_lesson_to_jsonl,create_vault_lesson,update_lesson,ops_refresh,train_topic}`
- `src/lele_manager/cli/{add_lesson,list_lessons,lele,train_topic_model,suggest_similar}.py`
- `src/lele_manager/ml/{features,topic_model,similarity,similarity_service,similarity_backend}.py`
- `frontend/src/lib/api.ts`
- `scripts/{lele-api-refresh.sh,e2e-prepare.py}`
- `tests/{test_lessons_storage.py,test_add_lesson_cli.py,test_api_vault.py,test_import_from_dir.py,test_api_basic.py,test_search_api.py,test_train_topic_model_cli.py,test_similarity_service_equivalence.py}`

### Documentazione tecnica ufficiale

- [Python `sqlite3` — DB-API 2.0 interface for SQLite databases](https://docs.python.org/3/library/sqlite3.html)
- [SQLite — FTS5 Extension](https://www.sqlite.org/fts5.html)
- [SQLite — Write-Ahead Logging](https://www.sqlite.org/wal.html)
- [SQLite — Online Backup API](https://www.sqlite.org/backup.html)
- [DuckDB — Concurrency](https://duckdb.org/docs/stable/connect/concurrency)
- [DuckDB — Python API overview](https://duckdb.org/docs/stable/clients/python/overview)
- [DuckDB — Transaction management](https://duckdb.org/docs/stable/sql/statements/transactions)
- [TinyDB documentation](https://tinydb.readthedocs.io/en/latest/)
- [MongoDB — Self-managed deployments](https://www.mongodb.com/docs/manual/self-managed-deployments/)
- [MongoDB — Production notes for self-managed deployments](https://www.mongodb.com/docs/manual/administration/production-notes/)
