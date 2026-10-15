<p align="center">
  <img src="https://raw.githubusercontent.com/ParkerHwang/OpenSocrates/main/docs/assets/opensocrates-banner.jpg" alt="OpenSocrates" width="320">
</p>

# OpenSocrates

**AI との会話に、48 種類の思考法を。**

OpenSocrates は、**Claude、Codex、Antigravity** で繰り返し使える思考の手順を
提供します。選択肢を比較し、食い違う情報を整理し、計画を別の角度から
見直してみましょう。課題は普段の言葉で説明してください。各方法には、
活用できる問い、確認項目、段階ごとの手順が用意されています。

[使うアプリから始める](#start-with-your-app) · [使用例を見る](#see-it-in-a-task) · [思考法を探す](#a-method-for-the-question)

**48 種類の思考法 · 10 言語の指示文 · MIT ライセンス**

[English](README.md) · [한국어](README.ko.md) · [简体中文](README.zh.md) · **日本語** · [Français](README.fr.md) · [Deutsch](README.de.md) · [Italiano](README.it.md) · [Español](README.es.md) · [Português](README.pt.md) · [ไทย](README.th.md)

## 今取り組んでいる課題に使える思考の道具

- **まず、課題を説明しましょう。** 各方法には問いと確認項目があらかじめ書かれており、さまざまな会話で再利用できます。
- **役立つ切り口を見つけましょう。** 選択肢の比較、根拠の評価、仮定の検討、今後の計画に合った方法を活用できます。
- **自分の仕事に合わせて使いましょう。** すべての手順と事例を読み、公開されたオープンソースの内容を自分の課題に合わせて応用できます。

<a id="see-it-in-a-task"></a>

## こんな課題で使ってみる

設定を終えたら、たとえば次のように依頼してみてください。

> クラウドのツールを購入するつもりでしたが、今度は作業をオフラインで行う必要があります。
> 購入するか、自分たちで作るか、当面は手作業で対応するか、一緒に検討してください。

このような判断に使える
[トレードオフ分析](content/methods/trade-off-analysis/procedure.ja.md)には、
必要な条件を特定し、実行可能な選択肢を比較し、既知の事実と仮定を分け、
何が変われば推奨を見直すかを説明する手順が用意されています。
いつもの依頼とともに使える思考の枠組みです。

<a id="start-with-your-app"></a>

## 使うアプリから始める

OpenSocrates を使いたいアプリを選んでください。
[v1.5.3 を入手する](https://github.com/ParkerHwang/OpenSocrates/releases/tag/v1.5.3)

<details>
<summary><strong>Claude Chat・Cowork</strong> — スキルをアップロードして会話を始める</summary>

Claude Web、Desktop Chat、Cowork での設定：

1. **Settings → Capabilities** で **Code execution and file creation** を有効にします。組織で管理されているアカウントの場合は、組織のポリシーで Skills とコード実行が許可されていることを確認してください。
2. [アカウント用スキル ZIP](https://github.com/ParkerHwang/OpenSocrates/releases/download/v1.5.3/opensocrates-1.5.3-claude-chat-skills.zip) と [SHA-256 ファイル](https://github.com/ParkerHwang/OpenSocrates/releases/download/v1.5.3/opensocrates-1.5.3-claude-chat-skills.zip.sha256) をダウンロードします。
3. **Customize → Skills → + → Create skill → Upload a skill** を開き、ZIP をアップロードして有効にします。既存の OpenSocrates スキルを置き換える場合は、先にバックアップしてください。
4. 使う Claude アカウントごとに、既存の指示を維持しながら[アカウント用の指示を一度追加](docs/setup-guide.md#claude-standing-instructions)します。新しい会話を開き、課題を説明してください。

持ち運べるスキル ZIP に、すべての方法と事例が含まれています。
[画面で見る設定ガイド](docs/setup-guide.md#2-claude-account-skill-enable-it-and-add-account-instructions) · [Claude 公式 Skills ガイド](https://support.claude.com/en/articles/12512180-use-skills-in-claude)

</details>

<details>
<summary><strong>Claude Code</strong> — Apple Silicon Mac</summary>

[Node.js 20 以降](https://nodejs.org/en/download)、Claude CLI、ログイン済みの
Claude アカウントが必要です。ターミナルの Claude Code と Claude Desktop の
ローカル Code で使えます。**ターミナル**で実行してください。

```sh
npx --yes opensocrates@1.5.3 install --host claude
npx --yes opensocrates@1.5.3 diagnose --host claude
```

`enabled: true`、`integrity: verified`、`registration: confirmed` を確認してください。
プロジェクトの信頼確認が表示された場合は内容を確認し、新しいローカルセッションを始めます。
[画面で見る設定ガイド](docs/setup-guide.md#3-claude-code-check-the-local-mac-plugin)

</details>

<details>
<summary><strong>Codex</strong> — Apple Silicon Mac または Windows x64</summary>

[Node.js 20 以降](https://nodejs.org/en/download) と Codex が必要です。
ネイティブランタイムはパッケージに含まれています。
**Mac のターミナル**または **Windows の PowerShell** で実行してください。

```sh
npx --yes opensocrates@1.5.3 install --host codex
npx --yes opensocrates@1.5.3 status --host codex
```

対話型 Codex の入力欄に `/hooks` を入力します。OpenSocrates の 7 個のフック定義を
確認し、信頼できるものを承認してから、新しい会話を始めてください。
[画面で見る設定ガイド](docs/setup-guide.md#1-codex-review-and-approve-opensocrates-hooks)

既存の Codex インストールを更新する場合：

```sh
npx --yes opensocrates@1.5.3 update --host codex
```

</details>

<details>
<summary><strong>Antigravity</strong> — Apple Silicon Mac または Windows x64</summary>

[Node.js 20 以降](https://nodejs.org/en/download) が必要です。ワークスペースを選び、
例のパスを既存フォルダーの絶対パスに置き換えてください。
**Mac のターミナル**または **Windows の PowerShell** で実行します。

```sh
npx --yes opensocrates@1.5.3 install --host antigravity --workspace "/absolute/path/to/workspace"
```

Windows では `"C:\Work\Reading Workshop"` のように引用符で囲んだローカルドライブの
パスを使います。グローバルに設定する場合は `--workspace` を省略してください。
同じプロジェクトではグローバルかワークスペースのどちらかを選び、新しい会話を始めます。
[スキルとルールを確認する](docs/setup-guide.md#4-antigravity-check-both-the-skill-and-rule)

</details>

**エージェントに設定を依頼する場合は、**[設定用の依頼文](docs/setup-guide.md#ask-an-agent-to-finish-setup)
または[現行版のインストールガイド](docs/agent-discovery.md)を使ってください。
各アプリは名前付きの `--host` オプションで選びます。既定値と `--host all` は Codex を選択します。

<a id="a-method-for-the-question"></a>

## 問いに合った思考法

| 今取り組んでいること | 検討できる思考法 |
| --- | --- |
| 競合する優先事項のもとで選択肢を比較する | [トレードオフ分析](content/methods/trade-off-analysis/procedure.ja.md) |
| 計画が当然としている仮定を理解する | [仮定マッピング](content/methods/assumption-mapping/procedure.ja.md) |
| 主張を支える根拠を評価する | [批判的思考](content/methods/critical-thinking/procedure.ja.md) |
| 計画で起こり得る問題に備える | [プレモーテム分析](content/methods/premortem-analysis/procedure.ja.md) |

各方法には目的、適用条件、完全な手順、事例、AI が確認する問いが含まれています。
本文を読み、思考の流れをたどり、さまざまな課題に再利用できます。

[48 種類の思考法をすべて見る](content/methods/)

## 思考法の全文を 10 言語で

英語、韓国語、簡体字中国語、日本語、フランス語、ドイツ語、イタリア語、
スペイン語、ポルトガル語、タイ語に対応しています。すべての言語に、
48 種類の方法の完全な手順と事例が含まれています。

これらは、AI が読む思考法の本文の言語です。
[言語ガイド](docs/v1.5.2.md) · [Codex の指示言語設定](docs/settings.md)

## 読み、使い、応用できるオープンソース

すべての方法とソースを読み、自分の仕事に合わせて応用したり、新しい事例を
追加したりできます。OpenSocrates は [MIT ライセンス](LICENSE)で公開された
独立したプロジェクトです。

[リリース](https://github.com/ParkerHwang/OpenSocrates/releases) · [設定ガイド](docs/setup-guide.md) · [プライバシーとセキュリティ](SECURITY.md) · [貢献ガイド](CONTRIBUTING.md) · [問題を報告する](https://github.com/ParkerHwang/OpenSocrates/issues/new/choose) · [変更履歴](CHANGELOG.md)
