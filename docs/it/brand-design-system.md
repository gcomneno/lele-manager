# Fondazione del brand e design system di LeLe Manager

[English](../brand-design-system.md) | [Italiano](brand-design-system.md)

## Scopo e promessa del prodotto

LeLe Manager è un workspace open-source e local-first per lesson learned: il Markdown approvato resta autorevole, mentre proiezioni, cache, dati di staging e modelli ML sono artefatti derivati ispezionabili. La sua promessa è **Your local-first lessons learned workspace**. L'interfaccia deve rendere leggibili proprietà e stato operativo, senza mascherare il prodotto locale come SaaS ospitato.

Il pubblico primario comprende professionisti e piccoli team che raccolgono, validano, cercano e riusano conoscenza operativa. La personalità è calda, accurata, tecnicamente credibile e sobriamente sicura. Scrivere in modo chiaro, essere specifici su stato e conseguenze, ed essere cordiali senza battute, hype o urgenza artificiale.

## Principi visivi

- Conoscenza accumulata: usare con moderazione forme di card, record e segnalibro per richiamare l'apprendimento durevole.
- Proprietà locale: mostrare chiaramente stati di API, dati, modello e operazioni; non suggerire sincronizzazione cloud, account o automazione invisibile.
- Chiarezza operativa: gerarchia, contrasto ed etichette hanno precedenza sulla decorazione. Lo stato ha sempre testo oltre al colore.
- Sobrietà curata: marrone e arancio caldi danno riconoscibilità; palette SaaS blu generiche, gradienti gratuiti, stock art e motion decorativo non lo fanno.

La scimmia è solo un riferimento storico di mascotte di supporto. Non è il logo, non dipende da emoji Unicode e non deve competere con le informazioni prodotto.

## Asset di identità e regole

Gli asset SVG di proprietà del repository vivono in `frontend/public/brand/`:

- `lele-manager-lockup.svg` è il lockup completo per documentazione e contesti prodotto spaziosi.
- `lele-manager-mark.svg` è il mark compatto a card di conoscenza usato nella GUI.
- `giadaware-monkey.svg` è la mascotte compatta del produttore GiadaWare, usata soltanto nella firma della sidebar.
- `frontend/public/favicon.svg` è l'icona applicazione piccola.

Il mark combina una card-record, un check di approvazione e un angolo inferiore discretamente simile a una coda. Mantenere uno spazio libero pari ad almeno un quarto della larghezza del mark; non stirarlo, ruotarlo, contornarlo, ricolorare le singole parti o posizionarlo su superfici a basso contrasto. Preferire arancio e marrone documentati o il trattamento `currentColor` del lockup con contrasto adeguato. Tutti gli asset visivi distribuiti sono asset originali del repository, distribuiti secondo i termini di licenza del repository. Non contengono immagini raster incorporate, riferimenti esterni, script o font remoti.

## Tipografia e layout

Usare lo stack sans locale `ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif`. Usare lo stack monospace di sistema soltanto per ID, codice e log tecnici. La dimensione base è 16px, con passi 12px, 14px, 16px, 18px e 22px; usare pesi medium, semibold e bold e altezze riga 1.2/1.5.

I token di spaziatura sono 4, 8, 12, 16, 20, 24 e 32px. I controlli sono alti 40px; i raggi sono 6px, 10px, 14px e pill. Usare un solo livello di elevazione discreto (`0 2px 8px` al 8% marrone) solo per card rialzate. Il contenuto principale è limitato a 1216px e i layout collassano vicino a 800–900px.

## Colore e token

L'implementazione in `frontend/src/app.css` è il contratto dei token semantici. Separa la palette grezza (`--color-brand-*`) dai ruoli: canvas, surface, surface-raised, text, text-muted, border, divider, action, focus e status. L'azione primaria è brand-600 `#b75222`; l'alias accent legacy punta a questo. I ruoli di stato accessibili sono success `#176b3a`, warning `#915500`, danger `#ad261c` e info `#245e8f`, ciascuno con una surface complementare. Canvas è `#f7f4ee`, surface è bianca, text è `#241c16` e border è `#d8d0c3`.

Gli alias esistenti (`--bg`, `--surface`, `--border`, `--text`, `--muted`, `--accent`, `--ok`, `--warn`, `--err` e i relativi token sidebar/radius/shadow) sono nomi temporanei per compatibilità di migrazione. Il nuovo lavoro deve usare ruoli semantici `--color-*`; gli alias devono sparire dopo la migrazione dei componenti interessati.

## Componenti e feedback

Usare `.btn` con `btn-primary`, `btn-secondary`, `btn-ghost` o `btn-destructive`; tutti hanno comportamento hover, active, focus-visible, disabled e busy. Input, select e textarea nativi condividono stati border, hover e focus; lo stile invalid è esplicito tramite `aria-invalid="true"` o `.is-invalid`, così i controlli required non ancora usati non sembrano errati. `.card`/`.panel`, `.tag`/`.badge`, `.status`, `.empty-state` e le classi feedback (`feedback-success`, `feedback-warning`, `feedback-info`, `feedback-error`) sono primitive riusabili. Le etichette runtime esistenti restano in italiano; questo sistema non introduce i18n runtime.

Usare una parola o un messaggio di stato conciso accanto a ogni colore di stato. I controlli busy devono mantenere visibile lo scopo e usare un'etichetta di progresso come “Saving…”. Le azioni distruttive richiedono il trattamento distruttivo e una superficie di conferma esistente quando il flusso la offre; questa issue non aggiunge nuovi dialog.

## Icone, accessibilità e motion

Preferire SVG inline originali o asset SVG del repository; le icone comunicano una sola azione nota e non devono essere l'unica etichetta di un'azione non familiare. Gli SVG decorativi sono nascosti alle tecnologie assistive; gli SVG significativi includono titolo e descrizione. Non viene usata alcuna libreria di icone, font CDN o asset runtime remoto.

Il focus da tastiera usa un anello blu visibile di 3px, inclusi controlli, navigazione e summary disclosure. Testo e controlli usano ruoli documentati ad alto contrasto; lo stato non è mai solo colore. Le transizioni sono limitate a feedback di 120ms/180ms e sono praticamente disabilitate da `prefers-reduced-motion`. Queste regole supportano un uso accessibile ma non dichiarano conformità formale senza una misurazione separata.

## Regole brand e dettagli implementativi

Questo documento definisce il contratto brand mantenuto: promessa prodotto, personalità, ruoli semantici, proprietà degli asset, principi di accessibilità e comportamento dei componenti. Struttura DOM esatta, spaziatura route-specific, alias CSS temporanei e hash di build sono dettagli implementativi e possono cambiare senza cambiare il brand. I documenti GUI storici restano record storici e non vengono riscritti retroattivamente con questo linguaggio.

## Linguaggio di prodotto e navigazione

Le etichette di navigazione descrivono la destinazione o l'attività disponibile
alla persona, non il nome del modulo implementativo sottostante. Il linguaggio
runtime del prodotto è attualmente italiano. Gli identificatori interni esatti
delle route (per esempio `browse`, `timeline`, `tritalele` e `ops`) restano
dettagli implementativi: preservano i contratti di route e API, ma non
determinano il testo mostrato nel prodotto.

## Non-obiettivi espliciti

Questa fondazione non introduce dark mode, redesign della navigazione, dashboard, route Settings o About, comandi lifecycle, account ospitati, telemetria, storage cloud, font o asset remoti, librerie esterne di icone, generazione raster o decorazioni animate. Non modifica autorevolezza del Markdown, contratti API/route o comportamento business.

## Firma del prodotto

Su desktop, la sidebar termina con una firma discreta del produttore
GiadaWare: la scimmietta SVG del repository accanto a “GiadaWare™” e
“Software open source”. La sidebar è agganciata al viewport, così la firma
rimane visibile nelle pagine corte e in quelle lunghe.

La tagline runtime è esattamente “Lo spazio locale per le tue 'Lessons
Learned'”. Spaziatura e interlinea esplicite evitano sovrapposizioni nella
colonna stretta del marchio.

L’azione primaria conserva il nome accessibile “Nuova LeLe”. Visivamente
mostra “+ Nuova”, seguito dalla scimmietta GiadaWare e da un piccolo fumetto
con la scritta “LeLe”. La mascotte resta subordinata al mark di LeLe Manager.
