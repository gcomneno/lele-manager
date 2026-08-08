# Manuale della GUI di LeLe Manager

[English](../gui-user-guide.md) | [Italiano](gui-user-guide.md)

> Stato: documentazione utente mantenuta
> Issue correlata: [#112](https://github.com/gcomneno/lele-manager/issues/112)

Questa guida documenta la GUI web locale rilasciata. Il record storico di
design resta disponibile in [`../gui-design.md`](../gui-design.md).

## Avviare la GUI

Il normale flusso locale è:

```bash
export LELE_VAULT_DIR="$HOME/LeLeVault"
./scripts/build-gui.sh
./scripts/lele-api-dev.sh
```

Aprire:

```text
http://127.0.0.1:8000/app/
```

Usare `scripts/lele-api-refresh.sh` quando occorre prima importare il vault
Markdown e riaddestrare il modello topic.

## Lingua della GUI

LeLe Manager parte in **inglese** quando non è memorizzata una scelta esplicita
della lingua. Il selettore si trova nella sidebar, immediatamente sopra la
firma GiadaWare. Le lingue mantenute della GUI sono **English** e **Italiano**.

Il cambio di lingua aggiorna immediatamente la GUI senza ricaricare la pagina.
La scelta esplicita viene conservata localmente nel browser con la chiave
`lele-manager.locale`. Valori memorizzati mancanti, malformati o non
supportati ricadono in sicurezza sull'inglese; il rilevamento automatico della
lingua del browser è intenzionalmente assente.

La localizzazione riguarda soltanto la presentazione della GUI. Non traduce né
modifica LeLe scritte dall'utente, contenuto Markdown del vault, valori del
dataset, topic, fonti, percorsi, ID, payload API o identità di navigazione.

## Flusso quotidiano

1. Aprire **Dashboard** per vedere disponibilità dello spazio di lavoro, punti
   che richiedono attenzione e prossima azione utile.
2. Usare **Ops** quando servono diagnostica esplicita, import, training o refresh.
3. Cercare, filtrare e leggere le lesson esistenti.
4. Creare o modificare lesson approvate tramite **Editor**.
5. Revisionare duplicati esatti e near-duplicate tramite **Duplicates**.
6. Ingerire appunti grezzi tramite **TritaLeLe**, mantenendo separate anteprima,
   staging, revisione e approvazione.
7. Usare **Vault**, **Stats** e **Timeline** per controllare la knowledge base.

## Viste della GUI

| Vista | Scopo |
|---|---|
| Dashboard | Disponibilità dello spazio di lavoro, riepiloghi bounded e prossime azioni utili |
| Browse | Ricerca, filtri ed esportazione delle lesson |
| Detail | Lettura di una lesson e similarità spiegata |
| Editor | Creazione o aggiornamento di lesson Markdown canoniche |
| Timeline | Analisi per mese, anno o topic |
| Stats | Conteggi, topic, tag e valori medi |
| TritaLeLe | Anteprima, staging, revisione e approvazione esplicita |
| Vault | Albero Markdown canonico e import della proiezione |
| Duplicates | Revisione non distruttiva di duplicati e near-duplicate |
| Ops | Health, Vault Doctor, import, training e refresh |

## Dashboard e stati di primo avvio

`/app/` apre la Dashboard. Browse resta disponibile direttamente su
`#/browse`.

La Dashboard legge soltanto uno stato bounded dello spazio di lavoro. Distingue
un primo avvio senza vault, un vault vuoto, uno spazio parzialmente pronto, uno
spazio pronto ed errori di caricamento recuperabili. Non avvia automaticamente
la revisione duplicati, Vault Doctor, import, refresh o training del modello.

Il vault Markdown resta la fonte autorevole. Proiezioni dataset, cache e
artefatti del topic model sono derivati e ricostruibili.

## Screenshot

Gli screenshot in [`../images/gui/`](../images/gui/) sono generati dalla
fixture Playwright isolata. Non contengono vault o dati personali.

### Browse e dettaglio della lesson

![Vista Browse con lesson dimostrative isolate](../images/gui/browse.png)

![Dettaglio della lesson con similarità spiegata](../images/gui/detail.png)

### Scrittura e analisi

![Editor con suggerimenti di similarità live](../images/gui/editor.png)

![Dashboard delle statistiche](../images/gui/stats.png)

![Timeline di acquisizione della conoscenza](../images/gui/timeline.png)

### Vault, operazioni e workflow di revisione

![Albero del vault Markdown canonico](../images/gui/vault.png)

![Revisione non distruttiva dei duplicati](../images/gui/duplicates.png)

![Pannello Ops e report sano del Vault Doctor](../images/gui/ops.png)

![Anteprima deterministica di ingestione TritaLeLe](../images/gui/tritalele.png)

## Modello dei dati e percorsi

LeLe Manager separa contenuto autorevole, dati applicativi persistenti e
artefatti ricostruibili.

| Livello | Default o configurazione | Ruolo | Priorità backup |
|---|---|---|---|
| Vault Markdown | `LELE_VAULT_DIR`, default `~/LeLeVault` | Autorità delle lesson approvate | Critica |
| Proiezione lesson | `LELE_DATA_DIR/lessons.jsonl` | Proiezione di lettura ricostruibile | Opzionale |
| Staging candidati | `LELE_DATA_DIR/candidates.json` | Stato TritaLeLe non approvato | Importante con revisioni pendenti |
| Modello topic | `LELE_CACHE_DIR/topic_model.joblib` | Artefatto ML ricostruibile | Opzionale |
| Percorso lesson legacy | `LELE_DATA_PATH` | Override file-level deprecato | Solo migrazione |
| Percorso modello legacy | `LELE_MODEL_PATH` | Override file-level deprecato | Solo migrazione |

Senza override di directory, dati applicativi e cache usano i percorsi del
sistema operativo determinati da `platformdirs`.

### Compatibilità degli script di sviluppo

La configurazione mantenuta usa `LELE_DATA_DIR` e `LELE_CACHE_DIR`. Gli script
di sviluppo attuali impostano ancora le variabili file-level deprecate
`LELE_DATA_PATH=data/lessons.jsonl` e
`LELE_MODEL_PATH=models/topic_model.joblib`, così le esecuzioni di sviluppo
restano locali al repository.

Questo comportamento di compatibilità è temporaneo. Nei servizi, nei launcher
personalizzati e nel packaging futuro vanno preferite le variabili
directory-level. Non impostare contemporaneamente la variabile directory-level
e il corrispondente override file-level legacy, salvo che l’override legacy sia
voluto esplicitamente.

## Backup e ripristino

### Backup minimo sicuro

Salvare:

1. l’intero vault Markdown;
2. `candidates.json` quando occorre conservare candidati e cronologia di review;
3. configurazioni o servizi che definiscono variabili d’ambiente personalizzate.

La proiezione JSONL e il modello topic sono ricostruibili dal vault.

### Ripristino

1. ripristinare il vault Markdown;
2. impostare `LELE_VAULT_DIR` sulla directory ripristinata;
3. ripristinare eventualmente `candidates.json` sotto `LELE_DATA_DIR`;
4. eseguire `lele doctor`;
5. eseguire `scripts/lele-api-refresh.sh`;
6. verificare **Ops**, **Browse** e **Vault** prima di riprendere le modifiche.

Non sostituire mai un vault più recente con una vecchia proiezione JSONL. Vince
il vault Markdown.

## Risoluzione dei problemi

### La GUI restituisce HTTP 503

Manca la build frontend. Eseguire:

```bash
./scripts/build-gui.sh
```

Poi riavviare l’API.

### Vault non trovato

Creare la directory configurata oppure impostare:

```bash
export LELE_VAULT_DIR="/percorso/assoluto/LeLeVault"
```

### Dataset o modello non disponibili

Eseguire il refresh completo:

```bash
./scripts/lele-api-refresh.sh
```

### Vault Doctor segnala errori

Non sovrascrivere la proiezione per aggirare problemi nel Markdown canonico.
Correggere il file indicato, rilanciare Doctor e solo dopo rigenerare i dati
derivati.

### TritaLeLe segnala un refresh parziale

La scrittura canonica potrebbe essere già riuscita. Controllare separatamente
i read-back di lesson e vault mostrati dalla GUI, verificare la destinazione e
ripetere soltanto il refresh derivato. Non riapprovare alla cieca il candidato.

### Duplicate Review non carica il modello

Usare temporaneamente la revisione exact-only oppure rigenerare il modello
topic.

## Decisione sul packaging

LeLe Manager resta un’applicazione web locale FastAPI/Svelte. Vedere
[l’ADR 0002](../adr/0002-gui-packaging.md) per alternative e conseguenze.
