<p align="center">
  <img src="https://raw.githubusercontent.com/ParkerHwang/OpenSocrates/main/docs/assets/opensocrates-banner.jpg" alt="OpenSocrates" width="820">
</p>

# OpenSocrates

**Un aiuto al ragionamento per risultati che puoi comprendere, valutare e usare.**

OpenSocrates offre 48 metodi di ragionamento per sintetizzare fonti, comprendere
punti di vista, confrontare opzioni e scrivere messaggi utili. La versione 1.5.2
aggiunge italiano (`it`), francese, tedesco, spagnolo, portoghese e thailandese
ai contenuti inglesi, coreani, cinesi semplificati e giapponesi. Le dieci lingue
comprendono 480 procedure complete, 3.840 casi canonici e 1.440 domande rivolte
all’agente, tre per metodo e lingua. La revisione dei contenuti passa a 5:
testi e valori delle quattro lingue precedenti restano invariati, mentre
l’identificatore di revisione di ciascun metodo passa da 4 a 5. Questa versione
non aggiunge metodi dedicati alla programmazione.

[English](README.md) | [한국어](README.ko.md) | [简体中文](README.zh.md) | [日本語](README.ja.md) | [Français](README.fr.md) | [Deutsch](README.de.md) | **Italiano** | [Español](README.es.md) | [Português](README.pt.md) | [ไทย](README.th.md)

## Applicazioni e piattaforme

| Applicazione | Distribuzione | Piattaforma e attivazione |
| --- | --- | --- |
| Codex | Hook esistenti e runtime nativo di decisione | Mac Apple Silicon e Windows x64; verificare l’attendibilità dei 7 hook in una sessione interattiva |
| Claude Code CLI / Code locale di Desktop | Ingresso nativo senza stato e riferimenti completi | Mac Apple Silicon; CLI Claude, accesso e autorizzazioni per plugin e hook |
| Claude Web / Desktop Chat / Cowork | Skill di account in ZIP senza codice eseguibile | Esportazione su Mac o Windows; caricamento e attivazione separati nell’account |
| Antigravity | Regola e skill modulari | Mac Apple Silicon e Windows x64; ambito di progetto o globale |

Le piattaforme rimangono quelle di v1.5.0. Claude Code nativo su Windows è escluso.
Windows ARM64 e la migrazione a Go appartengono al lavoro separato per v1.6.0.
La skill di account non installa un’integrazione nativa Claude.

## Installazione o aggiornamento

Prepara Node.js 20 o successivo e accedi all’applicazione scelta. I runtime
nativi sono inclusi e l’installazione non richiede Python. Archivi e file SHA-256
sono disponibili nella [release v1.5.2](https://github.com/ParkerHwang/OpenSocrates/releases/tag/v1.5.2).

```sh
npx --yes opensocrates@1.5.2 install --host codex
npx --yes opensocrates@1.5.2 status --host codex
npx --yes opensocrates@1.5.2 update --host codex
```

Per un’installazione già presente usa `update` invece di `install`.
Apri `/hooks` in Codex interattivo, esamina i 7 hook OpenSocrates e concedi le
approvazioni necessarie attraverso il meccanismo di attendibilità dell’host.
Avvia poi una nuova conversazione. `status` descrive installazione e integrità,
non dimostra l’approvazione degli hook o l’applicazione effettiva.

Su Mac Apple Silicon usa `install --host claude` per Claude Code.
Per Antigravity scegli una cartella di lavoro esistente con percorso assoluto;
senza `--workspace` l’ambito è globale. Evita copie attive duplicate per lo
stesso lavoro. Su Windows usa un percorso di unità locale tra virgolette,
per esempio `"C:\Work\Reading Workshop"`.

```sh
npx --yes opensocrates@1.5.2 install --host claude
npx --yes opensocrates@1.5.2 install --host antigravity --workspace /absolute/path/to/workspace
npx --yes opensocrates@1.5.2 export --host claude-chat --output /absolute/path/to/opensocrates-1.5.2-account.zip
```

Esporta la skill di account in un file ZIP con percorso assoluto in una cartella
esistente, poi caricala e attivala in Claude, **Customize → Skills**. Prima di
sostituire una skill OpenSocrates, salva una copia del file e del suo stato di
attivazione. L’esportazione non dimostra caricamento, attivazione o selezione
automatica. Aggiungi questa istruzione in **Settings → General → Instructions for
Claude**, conservando quelle già presenti:

```text
Per richieste che richiedono interpretazione o giudizio, come sintetizzare
fonti, confrontare opzioni, prendere decisioni o scrivere messaggi, carica la
skill OpenSocrates attivata e segui le sue istruzioni anche se non la nomino.
Prima di applicare un metodo, leggi la procedura completa e verifica le condizioni
di applicabilità. Non aggiungere procedure inutili a lavori meccanici come
la formattazione.
```

Nelle vecchie interfacce Cowork usa **Settings → Cowork → Global instructions**.
Se Web e Desktop usano account diversi, configura ciascuno e avvia una nuova
conversazione. La scelta dipende dal modello e può essere omessa: non introduce
hook nativi o uso garantito a ogni messaggio. Il valore predefinito e `--host all`
continuano a selezionare solo Codex.

## Scegliere la lingua delle istruzioni

L’alfabeto latino non identifica in modo affidabile l’italiano rispetto alle
altre lingue supportate. Usa quindi una preferenza esplicita o salvata. Dalla
cartella principale del pacchetto Codex installato su Mac:

```sh
bin/launch.sh locale codex set it
bin/launch.sh locale codex get
bin/launch.sh locale codex reset
```

Su Windows usa `node bin/launch.mjs locale codex set it`.
`set follow` o `reset` elimina solo la preferenza di lingua. La preferenza riguarda
il selettore mantenuto; le richieste di decisione senza stato richiedono il campo
JSON esplicito `locale` e non leggono le impostazioni. I pacchetti di account o
contenuto usano la guida e i riferimenti della lingua corrispondente.

L’ordine è: lingua esplicita attendibile, preferenza salvata, poi caratteri
dell’input corrente. I kana selezionano prima il giapponese; altrimenti i caratteri
thailandesi, hangul o han dominanti selezionano thailandese, coreano o cinese.
Parità, input vuoto e scritture sconosciute tornano all’inglese. Il giapponese
senza kana è ambiguo e richiede `ja`. Il portoghese usa l’ortografia brasiliana
con il codice generico `pt`, senza dichiarare supporto distinto per ogni variante.
Lingua delle istruzioni, risposta, interfaccia e messaggi npm sono separate.
L’installatore npm non ha un’opzione `--locale`.

## Attribuzione, riservatezza e limiti

La riga finale esatta `Powered by OpenSocrates` compare solo dopo la lettura
integrale e l’applicazione effettiva di un metodo canonico idoneo alla risposta.
La sola guida alla lettura e le attività meccaniche non bastano. L’attribuzione
non prova applicazione nativa o risultati migliori.

Il percorso di decisione predefinito non chiama un modello di selezione aggiuntivo
e non conserva prompt grezzi, conversazioni, schermate o ragionamenti nascosti.
L’ingresso nativo Claude non legge conversazioni e non inizializza database.
Le normali richieste seguono autenticazione, autorizzazioni, conservazione e
condizioni dell’host. Installazione, caricamento, lettura completa, applicazione
e utilità restano prove distinte. Non si affermano miglioramenti universali
di qualità, costo o velocità.

Consulta [lingue e ambito](docs/v1.5.2.md), [impostazioni](docs/settings.md),
[guida alla configurazione](docs/setup-guide.md) e [sicurezza](SECURITY.md).
Le guide [Mac](docs/macos-v1.5.md) e [Windows](docs/windows-v1.5.md) conservano le
osservazioni storiche; usa qui i comandi attuali per 1.5.2.

OpenSocrates è indipendente, con [licenza MIT](LICENSE), e non è affiliato né
approvato da OpenAI, Anthropic o Google. [Registro delle modifiche](CHANGELOG.md).
