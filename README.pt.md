<p align="center">
  <img src="https://raw.githubusercontent.com/ParkerHwang/OpenSocrates/main/docs/assets/opensocrates-banner.jpg" alt="OpenSocrates" width="320">
</p>

# OpenSocrates

**Use 48 métodos de raciocínio nas suas conversas com IA.**

OpenSocrates oferece procedimentos de raciocínio reutilizáveis para **Claude,
Codex e Antigravity**. Compare opções, entenda informações conflitantes e examine
um plano por outro ângulo. Descreva sua tarefa com suas próprias palavras; os
métodos oferecem perguntas, verificações e etapas que você pode aproveitar.

[Comece pelo seu aplicativo](#start-with-your-app) · [Veja um exemplo](#see-it-in-a-task) · [Explore os métodos](#a-method-for-the-question)

**48 métodos · Instruções em 10 idiomas · Licença MIT**

[English](README.md) · [한국어](README.ko.md) · [简体中文](README.zh.md) · [日本語](README.ja.md) · [Français](README.fr.md) · [Deutsch](README.de.md) · [Italiano](README.it.md) · [Español](README.es.md) · **Português** · [ไทย](README.th.md)

## Ferramentas para o trabalho que você tem pela frente

- **Comece pela sua tarefa.** Cada método já contém perguntas e verificações, prontas para reutilizar em diferentes conversas.
- **Encontre um ângulo útil.** Use métodos para comparar opções, avaliar evidências, explorar pressupostos e planejar os próximos passos.
- **Adapte ao seu trabalho.** Leia todos os procedimentos, estude os exemplos e adapte o material de código aberto às suas necessidades.

<a id="see-it-in-a-task"></a>

## Veja como usar em uma tarefa

Depois de configurar, experimente um pedido como este:

> Estávamos prestes a contratar uma ferramenta hospedada, mas agora o fluxo de
> trabalho precisa funcionar offline. Devemos contratar, criar nossa própria
> solução ou fazer o trabalho manualmente por enquanto?

Para uma decisão assim, a [análise de compromissos](content/methods/trade-off-analysis/procedure.pt.md)
oferece uma sequência reutilizável: identificar os requisitos, comparar opções
viáveis, separar fatos conhecidos de pressupostos e explicar o que mudaria a
recomendação. O método traz essa estrutura para acompanhar seu pedido habitual.

<a id="start-with-your-app"></a>

## Comece pelo seu aplicativo

Escolha onde você quer usar OpenSocrates.
[Baixe v1.5.2](https://github.com/ParkerHwang/OpenSocrates/releases/tag/v1.5.2).

<details>
<summary><strong>Claude Chat e Cowork</strong> — envie uma skill e comece uma conversa</summary>

Para Claude na web, Desktop Chat e Cowork:

1. Em **Settings → Capabilities**, ative **Code execution and file creation**. Se sua conta for gerenciada por uma organização, confirme que a política da organização permite Skills e execução de código.
2. Baixe o [ZIP da skill de conta](https://github.com/ParkerHwang/OpenSocrates/releases/download/v1.5.2/opensocrates-1.5.2-claude-chat-skills.zip) e seu [arquivo SHA-256](https://github.com/ParkerHwang/OpenSocrates/releases/download/v1.5.2/opensocrates-1.5.2-claude-chat-skills.zip.sha256).
3. Abra **Customize → Skills → + → Create skill → Upload a skill**, envie o ZIP e ative a skill. Faça uma cópia de segurança de uma skill OpenSocrates existente antes de substituí-la.
4. Adicione a [instrução de conta uma única vez](docs/setup-guide.md#claude-standing-instructions) a cada conta Claude que você usa, preservando suas instruções existentes. Comece uma conversa nova e descreva sua tarefa.

O ZIP portátil da skill contém os métodos completos e os exemplos.
[Guia visual de configuração](docs/setup-guide.md#2-claude-account-skill-enable-it-and-add-account-instructions) · [Guia de Skills do Claude](https://support.claude.com/en/articles/12512180-use-skills-in-claude)

</details>

<details>
<summary><strong>Claude Code</strong> — Mac Apple Silicon</summary>

Você precisa de [Node.js 20+](https://nodejs.org/en/download), da CLI do Claude e
de uma conta Claude conectada. Funciona com Claude Code no terminal e Code local
no Claude Desktop. Execute no **Terminal**:

```sh
npx --yes opensocrates@1.5.2 install --host claude
npx --yes opensocrates@1.5.2 diagnose --host claude
```

Confirme `enabled: true`, `integrity: verified` e `registration: confirmed`.
Confira qualquer solicitação de confiança do projeto e comece uma nova sessão local.
[Guia visual de configuração](docs/setup-guide.md#3-claude-code-check-the-local-mac-plugin)

</details>

<details>
<summary><strong>Codex</strong> — Mac Apple Silicon ou Windows x64</summary>

Você precisa de [Node.js 20+](https://nodejs.org/en/download) e Codex. O runtime
nativo vem no pacote. Execute no **Terminal no Mac** ou **PowerShell no Windows**:

```sh
npx --yes opensocrates@1.5.2 install --host codex
npx --yes opensocrates@1.5.2 status --host codex
```

Abra Codex no modo interativo e digite `/hooks` no campo de entrada. Confira e
aprove as sete definições de hooks do OpenSocrates em que você confia; depois,
comece uma conversa nova.
[Guia visual de configuração](docs/setup-guide.md#1-codex-review-and-approve-opensocrates-hooks)

Para atualizar uma instalação existente de Codex:

```sh
npx --yes opensocrates@1.5.2 update --host codex
```

</details>

<details>
<summary><strong>Antigravity</strong> — Mac Apple Silicon ou Windows x64</summary>

Você precisa de [Node.js 20+](https://nodejs.org/en/download). Escolha um espaço
de trabalho e substitua o exemplo pelo caminho completo de uma pasta que já
existe. Execute no **Terminal no Mac** ou **PowerShell no Windows**:

```sh
npx --yes opensocrates@1.5.2 install --host antigravity --workspace "/absolute/path/to/workspace"
```

No Windows, use um caminho de unidade local entre aspas, como
`"C:\Work\Reading Workshop"`. Para uma configuração global, omita `--workspace`.
Escolha a instalação global ou no espaço de trabalho para cada projeto e
comece uma conversa nova.
[Confirme a skill e a regra](docs/setup-guide.md#4-antigravity-check-both-the-skill-and-rule)

</details>

**Vai configurar com a ajuda de um agente?** Use o [pedido de configuração](docs/setup-guide.md#ask-an-agent-to-finish-setup)
ou o [guia de instalação atual](docs/agent-discovery.md). Selecione cada aplicativo
com sua opção `--host` pelo nome; o padrão e `--host all` selecionam Codex.

<a id="a-method-for-the-question"></a>

## Um método para cada pergunta

| Seu trabalho | Um método para explorar |
| --- | --- |
| Escolher entre opções com prioridades concorrentes | [Análise de compromissos](content/methods/trade-off-analysis/procedure.pt.md) |
| Entender o que um plano toma como certo | [Mapeamento de pressupostos](content/methods/assumption-mapping/procedure.pt.md) |
| Avaliar o suporte de uma afirmação | [Pensamento crítico](content/methods/critical-thinking/procedure.pt.md) |
| Preparar-se para o que pode dar errado em um plano | [Análise pré-mortem](content/methods/premortem-analysis/procedure.pt.md) |

Cada método inclui seu propósito, condições de uso, procedimento completo,
exemplos e perguntas para o assistente. Explore os textos, siga as etapas de
raciocínio e reutilize os métodos em seu trabalho.

[Explore os 48 métodos](content/methods/)

## Textos completos dos métodos em dez idiomas

Inglês, coreano, chinês simplificado, japonês, francês, alemão, italiano,
espanhol, português e tailandês. Todos os idiomas incluem os procedimentos
completos e os exemplos dos 48 métodos.

Esses são os idiomas dos textos de métodos que seu assistente lê.
[Guia de idiomas](docs/v1.5.2.md) · [Configurações do idioma das instruções no Codex](docs/settings.md)

## Código aberto, pronto para explorar

Leia os métodos completos e o código-fonte, adapte-os ao seu trabalho ou contribua
com um novo exemplo. OpenSocrates é um projeto independente, disponível sob a
[licença MIT](LICENSE).

[Versões](https://github.com/ParkerHwang/OpenSocrates/releases) · [Guia de configuração](docs/setup-guide.md) · [Privacidade e segurança](SECURITY.md) · [Como contribuir](CONTRIBUTING.md) · [Problemas](https://github.com/ParkerHwang/OpenSocrates/issues/new/choose) · [Histórico de mudanças](CHANGELOG.md)
