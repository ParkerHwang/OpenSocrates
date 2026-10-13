<p align="center">
  <img src="https://raw.githubusercontent.com/ParkerHwang/OpenSocrates/main/docs/assets/opensocrates-banner.jpg" alt="OpenSocrates" width="820">
</p>

# OpenSocrates

**Apoio ao raciocínio para resultados que você pode entender, avaliar e usar.**

OpenSocrates oferece 48 métodos de raciocínio para sintetizar fontes, entender
perspectivas, comparar opções e escrever mensagens úteis. A versão 1.5.2 acrescenta
português (`pt`), francês, alemão, italiano, espanhol e tailandês ao conteúdo em
inglês, coreano, chinês simplificado e japonês. Os dez idiomas incluem 480
procedimentos completos, 3.840 casos canônicos e 1.440 perguntas dirigidas ao
agente, três por método e idioma. A revisão de conteúdo passa a 5: os textos e
valores dos quatro idiomas existentes são preservados, enquanto a identidade
de revisão de cada método muda de 4 para 5. Não são acrescentados métodos
específicos de programação. O código genérico `pt` usa ortografia brasileira;
não há uma promessa de suporte separado a todas as variantes regionais.

[English](README.md) | [한국어](README.ko.md) | [简体中文](README.zh.md) | [日本語](README.ja.md) | [Français](README.fr.md) | [Deutsch](README.de.md) | [Italiano](README.it.md) | [Español](README.es.md) | **Português** | [ไทย](README.th.md)

## Migração nativa v1.6.0

Este ramo é um candidato v1.6.0 ainda não publicado. Preserva os dez idiomas de v1.5.2; os programas Go nativos substituem Python, Node.js e npm. Usuários também não precisam instalar Go. Windows ARM64 usa arquivos nativos próprios. Claude Code nativo continua restrito a macOS ARM64. Assinatura, notarização e publicação exigem evidências separadas. Mudanças nos conteúdos dos métodos ficam para v1.6.1 ou depois.

## Aplicativos e plataformas

[v1.5.2](https://github.com/ParkerHwang/OpenSocrates/releases/tag/v1.5.2) · [v1.6.0](docs/native-v1.6.md) · [Setup](docs/setup-guide.md) · [Security](SECURITY.md)

| Aplicativo | Distribuição | Plataforma e ativação |
| --- | --- | --- |
| Codex | Hooks existentes e ambiente nativo de decisão | Mac Apple Silicon e Windows x64/ARM64; conferir a confiança dos 7 hooks em sessão interativa |
| Claude Code CLI / Code local do Desktop | Entrada nativa sem estado e referências completas | Mac Apple Silicon; CLI Claude, login e permissões de plugin/hooks |
| Claude Web / Desktop Chat / Cowork | Skill de conta em ZIP sem código executável | Exportação no Mac ou Windows; envio e ativação separados na conta |
| Antigravity | Regra e skill modulares | Mac Apple Silicon e Windows x64/ARM64; escopo de projeto ou global |

## Instalar ou atualizar

Baixe o executável nativo e o pacote correspondente de uma versão aprovada. Antes da publicação, os pacotes do candidato são compilações locais. Para transferir uma instalação v1.5 gerenciada por npm, use explicitamente `adopt`, preservando configurações, permissões e integrações desativadas. Depois use `update` com um pacote verificado.

```text
./opensocrates install --host codex --package /absolute/path/to/bundle.zip
./opensocrates status --host codex
./opensocrates update --host codex --package /absolute/path/to/bundle.zip
```

```text
./opensocrates adopt --host codex --package /absolute/path/to/bundle.zip
```

Abra `/hooks` no Codex interativo, revise os 7 hooks OpenSocrates e conceda as
aprovações necessárias pelo mecanismo de confiança do aplicativo. Depois, inicie
uma conversa nova. `status` informa instalação e integridade; não comprova
aprovação de hooks ou aplicação efetiva.

Instalações antigas com vários hosts não são adotadas nem apagadas silenciosamente.
Antes de instalar um novo perfil, confirme a origem exata e a titularidade da
instalação existente.

No Mac Apple Silicon, use `install --host claude` para Claude Code.
No Antigravity, escolha uma pasta de trabalho existente com caminho absoluto;
sem `--workspace`, o escopo é global. Evite cópias ativas duplicadas para o mesmo
trabalho. No Windows, use um caminho de unidade local entre aspas, como
`"C:\Work\Reading Workshop"`.

```text
./opensocrates install --host claude --package /absolute/path/to/claude-bundle.zip
./opensocrates install --host antigravity --package /absolute/path/to/antigravity-bundle.zip --workspace /absolute/path/to/workspace
./opensocrates export --host claude-chat --package /absolute/path/to/account.zip --output /absolute/path/to/opensocrates-account.zip
```

Exporte a skill de conta para um caminho absoluto de arquivo ZIP em uma pasta
existente, depois envie e ative o arquivo no Claude, em **Customize → Skills**.
Antes de substituir uma skill OpenSocrates, faça backup do arquivo e registre
seu estado de ativação. Exportar não significa enviar, ativar ou selecionar
automaticamente. Acrescente a instrução abaixo em **Settings → General →
Instructions for Claude**, preservando as instruções existentes:

```text
Em pedidos que exijam interpretação ou julgamento, como sintetizar fontes,
comparar opções, tomar decisões ou escrever mensagens, carregue a skill
OpenSocrates ativada e siga suas instruções mesmo quando eu não mencionar o nome.
Antes de aplicar um método, leia o procedimento completo e verifique as condições
de uso. Não acrescente procedimentos desnecessários a tarefas mecânicas como
formatação.
```

Em interfaces antigas do Cowork, use **Settings → Cowork → Global instructions**.
Se Web e Desktop usarem contas diferentes, configure cada uma e inicie uma
conversa nova. A seleção depende do modelo e pode não ocorrer; não acrescenta
hooks nativos nem uso garantido a cada mensagem. O padrão e `--host all`
continuam selecionando apenas Codex.

## Escolher o idioma das instruções

Com o executável nativo no Mac:

```text
./opensocrates locale set pt
./opensocrates locale get
./opensocrates locale reset
```

No Windows x64/ARM64, use `.\opensocrates.exe`. Os comandos `locale` não recebem argumento de aplicativo.
`set follow` ou `reset` apaga apenas a preferência de idioma. Ela se aplica ao
seletor mantido; pedidos de decisão sem estado exigem o campo JSON explícito
`locale` e não leem configurações. Pacotes de conta ou conteúdo usam o guia e
as referências do idioma correspondente.

A ordem é: idioma explícito confiável, preferência salva e caracteres da entrada
atual. Kana seleciona japonês primeiro; caso contrário, o predomínio de caracteres
tailandeses, hangul ou han seleciona tailandês, coreano ou chinês. Empates,
entradas vazias e escritas desconhecidas usam inglês. Japonês sem kana é ambíguo
e precisa de `ja`. Idioma das instruções, da resposta, da interface e das
mensagens de gerenciamento são coisas separadas. O instalador não tem opção `--locale`.

## Atribuição, privacidade e limites

A linha final exata `Powered by OpenSocrates` só aparece depois da leitura
integral e aplicação efetiva de um método canônico elegível à resposta. Orientação
de leitura isolada e tarefas mecânicas não atendem à condição. A atribuição não
comprova aplicação nativa nem melhoria do resultado.

O caminho padrão de decisão não chama um modelo seletor adicional nem armazena
prompts brutos, conversas, capturas de tela ou raciocínio oculto. A entrada nativa
Claude não lê conversas nem inicializa um banco de dados. Pedidos normais seguem
a autenticação, permissões, retenção e termos do aplicativo. Instalação,
carregamento, leitura completa, aplicação e utilidade são evidências diferentes.
Não se afirmam ganhos universais de qualidade, custo ou velocidade.

O [guia nativo](docs/native-v1.6.md) descreve atualizações automáticas, recuperação e evidências pendentes. As instruções v1.5.2 e npm pertencem ao canal de manutenção publicado.

OpenSocrates é um projeto independente sob a [licença MIT](LICENSE), sem vínculo
ou endosso de OpenAI, Anthropic ou Google. [Histórico de mudanças](CHANGELOG.md).
