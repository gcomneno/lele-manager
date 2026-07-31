# Projection store

[English](../projection-store.md) | [Italiano](projection-store.md)

LeLe Manager accede al dataset interrogabile delle lesson tramite il port
tipizzato in `lele_manager.core.projection_store`. Il confine è
intenzionalmente piccolo e indipendente dal backend:

- apre uno snapshot coerente e immutabile;
- recupera una lesson tramite il suo ID canonico, inclusi gli ID contenenti `/`;
- elenca e cerca con filtri portabili, ordinamento deterministico e limiti;
- ottiene conteggi essenziali e una generazione deterministica del contenuto
  dallo stesso snapshot;
- valida e pubblica atomicamente uno snapshot sostitutivo completo.

I record delle lesson conservano i campi non conosciuti dall'applicazione
corrente. Il port non espone JSONL, percorsi filesystem, oggetti Pandas, SQL o
transazioni specifiche del backend. La conversione Pandas per ML e analytics
resta un confine applicativo, non parte del contratto storage.

## Backend di compatibilità corrente

La composizione del backend avviene in
`lele_manager.composition.projection_store`. I reader di produzione e i
publisher di snapshot completi richiedono lì il `ProjectionStore` neutrale;
JSONL resta l'adapter di compatibilità predefinito.

`JsonlProjectionStore` è l'adapter predefinito durante la migrazione descritta
da [ADR 0001](../adr/0001-storage-backend.md). Legge i file JSONL UTF-8
esistenti e pubblica JSONL canonico ordinato per ID della lesson. Le chiavi
degli oggetti sono ordinate e Unicode viene emesso direttamente. La
pubblicazione produce byte stabili per contenuti equivalenti. In lettura,
`LessonOrder.SNAPSHOT` espone l'ordine fisico dei record, quindi la generazione
SHA-256 include quell'ordine: un diverso ordine osservabile dello snapshot
produce una diversa generazione. Le righe vuote sono accettate per
compatibilità.

Una lettura valida l'intero file. JSON malformato, record che non sono oggetti,
ID mancanti o vuoti, UTF-8 non valido e ID duplicati sono errori espliciti; non
vengono ignorati silenziosamente. Ogni snapshot costruisce l'indice per ID e le
statistiche essenziali nello stesso passaggio di validazione.

La pubblicazione dell'intero snapshot valida tutto prima di toccare il file
corrente, scrive ed esegue `fsync` su un file temporaneo nella directory di
destinazione, quindi usa una sostituzione atomica. Un errore prima della
sostituzione lascia leggibile lo snapshot precedente e rimuove il file
temporaneo.

La CLI storica `add_lesson` e l'endpoint `POST /lessons` continuano ad
aggiungere record JSONL perché la rimozione di quel comportamento è fuori dallo
scope della issue #92. Questo comportamento è esposto soltanto tramite
`JsonlLegacyAppendFacade`, dal nome esplicito, e non tramite il port di
proiezione comune. Prima della scrittura valida l'intero snapshot esistente e
rifiuta gli ID duplicati.

Si assume che i writer siano serializzati dall'applicazione locale. Non esiste
una transazione o un locking cross-process: publisher simultanei dell'intero
snapshot seguono la regola last-writer-wins, mentre writer simultanei del
legacy append non sono supportati. I rebuild del vault e gli import da
directory usano la pubblicazione atomica dell'intero snapshot. Non è avvenuto
alcun cutover SQLite: SQLite resta un adapter futuro e qui non è né
implementato né selezionato come predefinito.
