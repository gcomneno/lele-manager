# Contratto package PKPS v1

[English](../pkps-package.md) | [Italiano](pkps-package.md)

Il **Personal Knowledge Publishing System (PKPS)** definisce un piccolo confine
di consegna tra GYTE Study Tools e LeLe Manager. GYTE possiede il proprio
workspace privato e i materiali sorgente; LeLe Manager possiede revisione dei
candidati, approvazione esplicita, Markdown canonico e dati derivati.

## Package

LeLe accetta una directory package la cui root contiene `pkps-manifest.json` e
la lesson dichiarata, oppure uno ZIP con esattamente una directory root che
contiene gli stessi file. Il manifest v1 richiede:

```json
{
  "schema_version": 1,
  "package_id": "stable-producer-identifier",
  "producer": {"name": "gyte-study-tools", "version": "0.1.0"},
  "created_at": "2026-08-06T09:00:00Z",
  "lesson": {"path": "lesson.md", "sha256": "…", "bytes": 123},
  "source": {"type": "youtube", "url": "https://example.invalid/watch"}
}
```

`schema_version` è esattamente `1`; `package_id` e `producer.version` sono
stringhe non vuote; `created_at` è un timestamp UTC; `source.type` è `youtube`
o `article`; e `source.url` è un URL HTTP/HTTPS assoluto. `source.title` e
altri identificatori sorgente sono opzionali e conservati come provenienza. Lo
SHA-256 della lesson è esadecimale minuscolo e il conteggio byte è positivo.

Il path della lesson è un path POSIX relativo normalizzato. Path assoluti, `..`,
symlink, file mancanti, non-file ed escape dalla root del package vengono
rifiutati. Lo ZIP rifiuta inoltre traversal, path assoluti o non normalizzati,
entry duplicate, symlink e root ambigue/multiple.

## Importazione e ciclo di vita

```bash
lele pkps import PACKAGE_PATH
lele pkps import PACKAGE_PATH --json
```

L'importazione valida il package prima di mettere in staging esattamente un
ordinario candidato TritaLeLe. Non scrive nel vault canonico, nella proiezione
JSONL o negli artefatti ML e non aggiorna le proiezioni. Il normale flusso di
review, accept e approvazione esplicita di TritaLeLe rimane l'unica strada verso
il Markdown canonico.

L'identità del package è `package_id`; l'identità del contenuto è
`lesson.sha256`. Una reimportazione con entrambi invariati riusa il candidato
esistente. Riutilizzare lo stesso package ID con un content hash diverso è un
conflitto controllato. Package ID differenti con lo stesso contenuto restano
candidati di revisione separati; l'esistente workflow duplicati di LeLe decide
come procedere.

La provenienza del candidato conserva il manifest normalizzato originale,
l'identità di package e producer, timestamp del package, dati sorgente, digest
e lunghezza del contenuto e timestamp locale di importazione. Tale provenienza
immutabile è mostrata dall'esistente workflow candidati e copiata nella traccia
di approvazione canonica.

Riferimenti di pubblicazione come metadati PDF, EPUB e Kindle possono essere
conservati nel manifest, ma v1 non importa quegli artefatti né trasferisce a
LeLe l'autorità su di essi.

## Limiti di risorse e path

PKPS v1 considera il package un input locale non fidato. Il path del package,
il manifest, la lesson dichiarata e ogni directory intermedia rilevante non
devono essere collegamenti simbolici.

L'importatore applica questi limiti prima di leggere il contenuto completo:

- manifest: 256 KiB;
- lesson Markdown: 16 MiB;
- entry ZIP: 128;
- contenuto ZIP totale non compresso: 32 MiB.

Il contenuto ZIP viene ispezionato senza estrazione. I package che superano
questi limiti falliscono con errori di dominio PKPS controllati.
