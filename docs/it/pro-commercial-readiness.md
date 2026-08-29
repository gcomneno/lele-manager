# Readiness commerciale di LeLe Manager Pro

[English](../pro-commercial-readiness.md) | [Italiano](pro-commercial-readiness.md)

> Stato: documentazione prodotto mantenuta
> Epic correlata: [#238](https://github.com/gcomneno/lele-manager/issues/238)

## Promessa di prodotto

LeLe Manager Pro si fonda su una promessa di conoscenza mantenuta:

> **LeLe Manager — La memoria tecnica che non si limita ad accumulare: si mantiene.**

Il differenziatore del prodotto a pagamento non è il generic note-taking,
Markdown locale, ricerca semantica, AI chat o automazione opaca.

È la capacità di mantenere conoscenza tecnica approvata affinché resti
revisionabile, correlata, recuperabile, spiegabile e governata esplicitamente
mentre evolve.

## Flusso della conoscenza mantenuta

Il contratto di prodotto mantenuto è:

```text
Capture
  -> Validate
    -> Approve
      -> Relate
        -> Reuse
          -> Review
            -> Supersede
```

Questi stadi rappresentano responsabilità complementari e non un'escalation
automatica di autorità.

- **Capture** raccoglie conoscenza grezza tramite i flussi supportati di
  authoring e ingestion.
- **Validate** verifica struttura, identità, riferimenti e contratti mantenuti
  del Vault.
- **Approve** mantiene i candidati staged separati dalla conoscenza canonica
  finché un essere umano non li pubblica esplicitamente.
- **Relate** collega le lesson tramite relazioni tipizzate esplicite e metadati
  canonici di supersession.
- **Reuse** recupera conoscenza mantenuta tramite segnali lessicali, semantici e
  di metadati spiegabili.
- **Review** espone evidenze di freshness e potenziale contraddizione senza
  dichiarare i segnali derivati come verità.
- **Supersede** registra esplicitamente l'evoluzione della conoscenza
  preservando storia e identità della conoscenza sostituita.

Il Vault Markdown canonico resta autorevole durante l'intero flusso.
Proiezioni, indici di ricerca, modelli di similarità, segnali di freshness e
candidati a contraddizione restano derivati o consultivi secondo i rispettivi
contratti mantenuti.

## Gate di readiness Pro

La prima milestone di readiness commerciale Pro richiede tutti e quattro i gate
di conoscenza mantenuta definiti dall'epic #238:

- **#215 — Revisione delle potenziali contraddizioni**
  - espone candidati a conflitto spiegabili per la revisione umana;
  - non riscrive, depreca o elimina silenziosamente conoscenza canonica.

- **#216 — Segnali di freshness e review-needed**
  - spiega perché una conoscenza può meritare revisione;
  - tratta la freshness come evidenza di prioritizzazione, non come verdetto
    fattuale.

- **#217 — Relazioni tipizzate esplicite**
  - fornisce relazioni canoniche e portabili tra LeLe;
  - preserva semantiche di relazione e supersession esplicite e controllate
    dall'utente.

- **#219 — Ricerca ibrida spiegabile**
  - combina evidenze lessicali, semantiche e di metadati attraverso un unico
    boundary di retrieval mantenuto;
  - protegge le evidenze lessicali forti, supporta assistenza semantica bounded
    e spiega perché i risultati sono rilevanti.

Tutti e quattro i gate sono implementati e integrati nel prodotto mantenuto.

## Autorità e spiegabilità

La readiness commerciale non modifica il modello di autorità di LeLe Manager.

Nessuna euristica, modello di similarità, algoritmo di ranking, calcolo di
freshness o detector di contraddizioni può modificare silenziosamente la
conoscenza canonica.

Le capability derivate forniscono evidenze e raccomandazioni. Le modifiche
canoniche conseguenti richiedono ancora il flusso applicativo esplicito e
l'autorità umana definiti per quell'operazione.

Questo è particolarmente importante per la promessa Pro: conoscenza mantenuta
non significa conoscenza riscritta automaticamente da un'AI. Significa
conoscenza la cui evoluzione resta ispezionabile e accountable.

## Boundary local-first

LeLe Manager resta local-first.

La promessa Pro di conoscenza mantenuta non richiede:

- un account hosted;
- storage cloud della knowledge base;
- telemetria;
- upload nascosti;
- un provider AI remoto;
- comportamento da chatbot generico.

Le capability semantiche opzionali completano il comportamento locale
deterministico e non diventano autorità canonica.

## Significato di questa milestone

Il completamento dell'epic #238 significa che il prodotto può sostenere
correttamente la promessa di conoscenza mantenuta:

> **La memoria tecnica che non si limita ad accumulare: si mantiene.**

Significa che le capability minime necessarie alla prima offerta Pro a pagamento
sono integrate coerentemente.

Non definisce invece, da sola:

- i confini funzionali Community versus Pro;
- il prezzo;
- meccanismi di licensing o attivazione;
- livelli di supporto;
- policy commerciali o di onboarding;
- versione di release o data di pubblicazione.

Queste decisioni commerciali restano lavoro successivo e separato.

## Capability rinviate

La prima offerta Pro non dipende dal trasformare LeLe Manager in un prodotto
AI-chat.

Funzionalità come Context Packs, export assistant-ready, Ask this Vault,
verifica fattuale supportata da evidenze, integrazioni provider più ricche e
chat generica potranno rafforzare release successive, ma non sono richieste da
questa milestone di readiness.

Il prodotto resta centrato sulla conoscenza tecnica mantenuta e non
sull'ampiezza di un chatbot.
