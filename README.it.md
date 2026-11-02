<p align="center">
  <img src="https://raw.githubusercontent.com/ParkerHwang/OpenSocrates/main/docs/assets/opensocrates-banner.jpg" alt="OpenSocrates" width="320">
</p>

# OpenSocrates

**Metti 48 metodi di ragionamento al servizio delle tue conversazioni con l’AI.**

OpenSocrates offre procedure di ragionamento riutilizzabili in **Claude, Codex e
Antigravity**. Confronta le opzioni, interpreta informazioni contrastanti ed esplora
un piano da un’altra prospettiva. Descrivi il tuo compito con parole tue: i metodi
mettono a disposizione domande, verifiche e passaggi a cui attingere.

[Inizia dalla tua app](#start-with-your-app) · [Guarda un esempio](#see-it-in-a-task) · [Esplora i metodi](#a-method-for-the-question)

**48 metodi · 10 lingue per le istruzioni · Licenza MIT**

[English](README.md) · [한국어](README.ko.md) · [简体中文](README.zh.md) · [日本語](README.ja.md) · [Français](README.fr.md) · [Deutsch](README.de.md) · **Italiano** · [Español](README.es.md) · [Português](README.pt.md) · [ไทย](README.th.md)

## Una cassetta degli attrezzi per il lavoro che hai davanti

- **Parti dal tuo compito.** Le domande e le verifiche sono già scritte in ogni metodo, pronte da riutilizzare in conversazioni diverse.
- **Trova una prospettiva utile.** Attingi a metodi per confrontare opzioni, valutare evidenze, esplorare ipotesi e pianificare.
- **Adattali al tuo lavoro.** Leggi ogni procedura, studia gli esempi e adatta il materiale open source alle tue esigenze.

<a id="see-it-in-a-task"></a>

## Un esempio concreto

Dopo la configurazione, prova una richiesta come questa:

> Stavamo per acquistare uno strumento ospitato nel cloud, ma ora il flusso di lavoro deve funzionare offline.
> Conviene acquistarlo, svilupparne uno nostro o gestire il lavoro manualmente per il momento?

Per una decisione come questa, l’[analisi dei compromessi](content/methods/trade-off-analysis/procedure.it.md)
offre una sequenza riutilizzabile: individuare i requisiti, confrontare le opzioni
praticabili, separare i fatti noti dalle ipotesi e spiegare che cosa cambierebbe
la raccomandazione. Il metodo fornisce questa struttura accanto alla tua richiesta
di tutti i giorni.

<a id="start-with-your-app"></a>

## Inizia dalla tua app

Scegli dove vuoi usare OpenSocrates.
[Scarica v1.5.3](https://github.com/ParkerHwang/OpenSocrates/releases/tag/v1.5.3).

<details>
<summary><strong>Claude Chat & Cowork</strong> — carica una skill e inizia una conversazione</summary>

Per Claude web, Desktop Chat e Cowork:

1. In **Settings → Capabilities**, attiva **Code execution and file creation**. Se l’account è gestito da un’organizzazione, verifica che le sue regole consentano Skills ed esecuzione di codice.
2. Scarica lo [ZIP della skill di account](https://github.com/ParkerHwang/OpenSocrates/releases/download/v1.5.3/opensocrates-1.5.3-claude-chat-skills.zip) e il relativo [file SHA-256](https://github.com/ParkerHwang/OpenSocrates/releases/download/v1.5.3/opensocrates-1.5.3-claude-chat-skills.zip.sha256).
3. Apri **Customize → Skills → + → Create skill → Upload a skill**, carica lo ZIP e attivalo. Salva una copia di una skill OpenSocrates esistente prima di sostituirla.
4. Aggiungi l’[istruzione da impostare una sola volta](docs/setup-guide.md#claude-standing-instructions) a ogni account Claude che usi, conservando le istruzioni già presenti. Avvia una nuova conversazione e descrivi il tuo compito.

Lo ZIP della skill portabile contiene tutti i metodi e gli esempi.
[Guida illustrata alla configurazione](docs/setup-guide.md#2-claude-account-skill-enable-it-and-add-account-instructions) · [Guida di Claude alle Skills](https://support.claude.com/en/articles/12512180-use-skills-in-claude)

</details>

<details>
<summary><strong>Claude Code</strong> — Mac Apple Silicon</summary>

Servono [Node.js 20 o successivo](https://nodejs.org/en/download), la CLI Claude e
un account Claude con accesso effettuato. Funziona con Claude Code nel terminale
e con Code locale in Claude Desktop. Esegui nel **Terminale**:

```sh
npx --yes opensocrates@1.5.3 install --host claude
npx --yes opensocrates@1.5.3 diagnose --host claude
```

Verifica `enabled: true`, `integrity: verified` e `registration: confirmed`.
Esamina eventuali richieste di attendibilità del progetto, poi avvia una nuova sessione locale.
[Guida illustrata alla configurazione](docs/setup-guide.md#3-claude-code-check-the-local-mac-plugin)

</details>

<details>
<summary><strong>Codex</strong> — Mac Apple Silicon o Windows x64</summary>

Servono [Node.js 20 o successivo](https://nodejs.org/en/download) e Codex. Il runtime
nativo è incluso nel pacchetto. Esegui nel **Terminale su Mac** o in **PowerShell su Windows**:

```sh
npx --yes opensocrates@1.5.3 install --host codex
npx --yes opensocrates@1.5.3 status --host codex
```

Apri Codex interattivo e digita `/hooks` nel campo di input. Esamina le sette
definizioni degli hook OpenSocrates e approva quelle di cui ti fidi, poi avvia una nuova conversazione.
[Guida illustrata alla configurazione](docs/setup-guide.md#1-codex-review-and-approve-opensocrates-hooks)

Per aggiornare un’installazione Codex esistente:

```sh
npx --yes opensocrates@1.5.3 update --host codex
```

</details>

<details>
<summary><strong>Antigravity</strong> — Mac Apple Silicon o Windows x64</summary>

Serve [Node.js 20 o successivo](https://nodejs.org/en/download). Scegli una cartella
di lavoro e sostituisci l’esempio con il percorso completo di una cartella già
esistente. Esegui nel **Terminale su Mac** o in **PowerShell su Windows**:

```sh
npx --yes opensocrates@1.5.3 install --host antigravity --workspace "/absolute/path/to/workspace"
```

Su Windows usa un percorso di unità locale tra virgolette, come `"C:\Work\Reading Workshop"`.
Per una configurazione globale, ometti `--workspace`. Per un dato progetto scegli
tra installazione globale e nella cartella di lavoro, poi avvia una nuova conversazione.
[Verifica la skill e la regola](docs/setup-guide.md#4-antigravity-check-both-the-skill-and-rule)

</details>

**Configuri con l’aiuto di un agente?** Usa la [richiesta di configurazione](docs/setup-guide.md#ask-an-agent-to-finish-setup)
o la [guida attuale all’installazione](docs/agent-discovery.md). Seleziona ogni app
con la relativa opzione `--host`; il valore predefinito e `--host all` selezionano Codex.

<a id="a-method-for-the-question"></a>

## Un metodo per la tua domanda

| Il tuo compito | Un metodo da esplorare |
| --- | --- |
| Scegliere tra opzioni con priorità concorrenti | [Analisi dei compromessi](content/methods/trade-off-analysis/procedure.it.md) |
| Capire quali ipotesi un piano dà per scontate | [Mappatura delle ipotesi](content/methods/assumption-mapping/procedure.it.md) |
| Valutare il sostegno a un’affermazione | [Pensiero critico](content/methods/critical-thinking/procedure.it.md) |
| Prepararsi a ciò che potrebbe andare storto in un piano | [Analisi premortem](content/methods/premortem-analysis/procedure.it.md) |

Ogni metodo comprende scopo, condizioni d’uso, procedura completa, esempi e
domande per l’assistente. Esplora il testo, segui i passaggi di ragionamento e
riutilizza i metodi nel tuo lavoro.

[Esplora tutti i 48 metodi](content/methods/)

## Il testo completo dei metodi in dieci lingue

Inglese, coreano, cinese semplificato, giapponese, francese, tedesco, italiano,
spagnolo, portoghese e thailandese. Ogni lingua comprende procedure ed esempi
completi per tutti i 48 metodi.

Sono le lingue del testo dei metodi che legge il tuo assistente.
[Guida alle lingue](docs/v1.5.2.md) · [Impostazioni della lingua delle istruzioni Codex](docs/settings.md)

## Open source, tutto da esplorare

Leggi i metodi completi e il codice sorgente, adattali al tuo lavoro o contribuisci
con un nuovo esempio. OpenSocrates è un progetto indipendente, disponibile con
[licenza MIT](LICENSE).

[Release](https://github.com/ParkerHwang/OpenSocrates/releases) · [Guida alla configurazione](docs/setup-guide.md) · [Riservatezza e sicurezza](SECURITY.md) · [Contribuire](CONTRIBUTING.md) · [Segnalazioni](https://github.com/ParkerHwang/OpenSocrates/issues/new/choose) · [Registro delle modifiche](CHANGELOG.md)
