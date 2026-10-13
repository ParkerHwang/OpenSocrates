<p align="center">
  <img src="https://raw.githubusercontent.com/ParkerHwang/OpenSocrates/main/docs/assets/opensocrates-banner.jpg" alt="OpenSocrates" width="820">
</p>

# OpenSocrates

**理解し、評価し、使える結果を得るための思考支援。**

OpenSocrates は、資料の統合、関係者の視点の理解、選択肢の比較、メッセージの
作成を支える 48 種類の思考法を提供します。v1.5.1 では簡体字中国語（`zh`）と
日本語（`ja`）を追加し、既存の英語・韓国語の方法本文を維持します。4 言語で
完全な手順ファイルは 192 個、各方法・言語にエージェント向けの問いが 3 個ずつ、
合計 576 個あります。コンテンツリビジョンは 4 です。プログラミング専用の
方法は今回の更新には含みません。

[English](README.md) | [한국어](README.ko.md) | [简体中文](README.zh.md) | **日本語**

## 対応環境とアプリ

| アプリ | 提供方式 | 環境と有効化 |
| --- | --- | --- |
| Codex | 既存のフック、コントローラー、ネイティブ判断ランタイム | Apple Silicon Mac、Windows x64。対話セッションで 7 個のフックの信頼状態を確認 |
| Claude Code CLI / Desktop のローカル Code | 状態を保持しないネイティブ入口と完全なローカル参照 | Apple Silicon Mac。Claude CLI、ログイン、プラグインとフックの権限が必要 |
| Claude Web / Desktop Chat / Cowork | 実行コードを含まないアカウント用スキル ZIP | Mac または Windows でエクスポート後、別途アップロード、有効化、アカウント指示を設定 |
| Antigravity の会話アプリ | モジュール形式のルールとスキル | Apple Silicon Mac、Windows x64。ワークスペースまたはグローバルを選択 |

対応環境は v1.5.0 を引き継ぎます。Windows のネイティブ Claude Code は対象外
です。Windows ARM64 対応は別の v1.6.0 作業に属します。アカウント用スキルの
導入でネイティブ Claude 連携がインストールされるわけではありません。

## インストールと更新

Node.js 20 以降を用意し、利用するアプリをインストールしてログインします。
ネイティブランタイムは同梱されており、Python の追加インストールは不要です。
[v1.5.1 リリース](https://github.com/ParkerHwang/OpenSocrates/releases/tag/v1.5.1)から
アーカイブと SHA-256 ファイルを取得するか、次のバージョン固定コマンドを使います。

```sh
npx --yes opensocrates@1.5.1 install --host codex
npx --yes opensocrates@1.5.1 status --host codex
# 既存の Codex インストールを更新：
npx --yes opensocrates@1.5.1 update --host codex
```

対話型 Codex で `/hooks` を入力し、OpenSocrates の 7 個のフックを確認して、
アプリの信頼手順に従い必要な承認を行います。その後、新しい会話を始めます。
`status` はインストールと整合性の状態を示します。フックの承認や実際の課題への
適用を証明するものではありません。

Apple Silicon Mac で Claude Code 連携を導入する場合：

```sh
npx --yes opensocrates@1.5.1 install --host claude
npx --yes opensocrates@1.5.1 status --host claude
```

Antigravity のワークスペースには、既存ディレクトリの絶対パスを指定します。
`--workspace` を省略するとグローバル範囲になります。同じ課題に両方の副本を
重複して適用しないようにします。

```sh
npx --yes opensocrates@1.5.1 install --host antigravity --workspace /absolute/path/to/workspace
```

Windows では `"C:\Work\Reading Workshop"` のようなローカルドライブの絶対パスを
引用符で囲みます。Claude アカウント用スキルは、既存フォルダー内の絶対 ZIP
パスにエクスポートします。

```sh
npx --yes opensocrates@1.5.1 export --host claude-chat --output /absolute/path/to/opensocrates-1.5.1-account.zip
```

その後 Claude の **Customize → Skills** でアップロードして有効化します。
既存の OpenSocrates スキルを置き換える前にダウンロードしてバックアップし、
有効状態を記録します。エクスポート成功とアップロード、有効化、自動選択は
別の状態です。次の指示を **Settings → General → Instructions for Claude** に
追加し、既存の指示を維持します。旧 Cowork では **Settings → Cowork → Global
instructions** を使います。Web と Desktop のアカウントが異なる場合は、それぞれ
設定します。

```text
資料の統合、選択肢の比較、判断、メッセージの作成など、解釈や判断が必要な
依頼では、私が名前を挙げなくても有効な OpenSocrates スキルを読み込み、
その指示に従ってください。思考法を適用する前に手順全体を読み、適用条件を
確認してください。書式変換などの機械的な作業に不要な手順を追加しないでください。
```

保存後に新しい会話を始めます。アカウント用スキルの選択はアプリのモデルが行う
ため、選択されない場合があります。ネイティブフックや毎メッセージの強制適用は
追加されません。既定値と `--host all` は引き続き Codex だけを選択します。
他のアプリは明示的に指定します。新しい連携には purge、信頼状態のリセット、
自動更新の機能はありません。
[設定ガイド（英語）](docs/setup-guide.md)で画面上の手順を確認できます。
[Mac ガイド](docs/macos-v1.5.md)と [Windows ガイド](docs/windows-v1.5.md)は
v1.5.0 の導入・復旧の基準を保持しています。現在のコマンドには上記の 1.5.1 を使います。

## 指示の言語

明示的に指定した言語、保存した言語設定、現在の入力の文字判定の順に選びます。
ひらがな・カタカナが含まれる場合は日本語を選びます。それ以外はハングルが
優勢なら韓国語、漢字が優勢なら中国語です。漢字だけの入力では中国語と日本語を
確実に区別できず、中国語が既定になります。日本語が必要な場合は明示的に指定
してください。空の入力、ラテン文字だけの入力、判定が同数の場合は英語になります。

思考指示の言語は、npm インストーラーのコマンド出力やアプリの表示言語とは
別です。今回の更新はすべてのインストーラーメッセージの翻訳を約束するものでは
ありません。ランタイムの `locale` 設定コマンドと明示的な JSON リクエストは
[言語と対応範囲のガイド（英語）](docs/v1.5.1.md)を参照してください。

## 出典表示とプライバシー

適用条件を満たす正典の思考法の手順全体を読み、実際に回答へ適用した場合に限り、
最終回答の末尾に同じ英語の行 `Powered by OpenSocrates` を付けます。読者向けの
案内だけを使った場合や機械的な作業では表示しません。この行は出典表示であり、
ネイティブ適用の成功や回答品質の向上を証明するものではありません。

既定の判断経路は追加の選択モデルを呼び出さず、生のプロンプト、会話、画像、
隠れた推論を保存しません。Claude のネイティブ入口は会話を読まず、データベースを
初期化しません。アカウント用スキルには実行コードがありません。通常の会話には
アプリ自身の認証、権限、保存設定、利用規約が適用されます。
[セキュリティ方針](SECURITY.md)に境界を記載しています。インストール、読み込み、
全体の読了、適用、結果の有用性は別々の証拠です。一般的な品質、費用、速度の
改善は主張していません。

- [方法の本文](content/methods/) · [判断点の契約](docs/decision-points.md)
- [変更履歴](CHANGELOG.md) · [貢献ガイド](CONTRIBUTING.md) · [行動規範](CODE_OF_CONDUCT.md)

OpenSocrates は [MIT ライセンス](LICENSE)の独立したプロジェクトです。
OpenAI、Anthropic、Google の公式製品ではなく、各社の推奨や保証を受けていません。
