<p align="center">
  <img src="https://raw.githubusercontent.com/ParkerHwang/OpenSocrates/main/docs/assets/opensocrates-banner.jpg" alt="OpenSocrates" width="820">
</p>

# OpenSocrates

**理解し、評価し、使える結果を得るための思考支援。**

資料の統合、関係者の視点の理解、選択肢の比較、メッセージ作成を支える
48 種類の思考法を提供します。現在の内容はリリース済み v1.5.1 が基準です。
英語、韓国語、簡体字中国語（`zh`）、日本語（`ja`）に対応し、完全な手順は
192 個、教師向けの問いは 576 個、コンテンツリビジョンは 4 です。元の英語・
韓国語の方法本文は維持します。方法本文の改善は v1.6.1 以降の別作業で、
プログラミング専用機能は今回の対象外です。

[English](README.md) | [한국어](README.ko.md) | [简体中文](README.zh.md) | **日本語**

## v1.6.0 ネイティブ移行候補

このブランチは**未公開の v1.6.0 実装候補**です。Go ランタイム、管理ツール、
インストーラー、更新ツール、開発ツールが Python・JavaScript・npm の既存経路を
置き換えます。利用者は Go、Python、Node.js、npm をインストールする必要は
ありません。正式な配布先は [GitHub Releases](https://github.com/ParkerHwang/OpenSocrates/releases)
です。本番署名、更新の信頼ルート、ネイティブリリース検証の条件を満たしてから
公開します。現在の公開版は [v1.5.1](https://github.com/ParkerHwang/OpenSocrates/releases/tag/v1.5.1)
です。進行中の v1.5.2 はフランス語、ドイツ語、イタリア語、スペイン語、
ポルトガル語、タイ語を追加する計画ですが、この候補の現時点の基準には
含めません。v1.6.0 公開前に再度照合します。

| アプリ | 提供方式 | 環境と有効化 |
| --- | --- | --- |
| Codex CLI / Desktop | ネイティブフック、コントローラー、Go 判断ランタイム | macOS ARM64、Windows x64/ARM64（既定 PowerShell）。7 個のフックを確認後、新しいセッション |
| Claude Code CLI / Desktop のローカル Code | 状態を保持しない入口と完全なローカル参照 | macOS ARM64。Claude CLI、ログイン、プラグインとフックの権限が必要 |
| Claude Web / Desktop Chat / Cowork | 実行コードを含まないアカウント用 ZIP | 全対応対象で検証・エクスポート後、別途アップロードして有効化 |
| Antigravity 会話アプリ | 所有範囲が明確なルールとスキル | macOS ARM64、Windows x64/ARM64。ワークスペースまたはグローバルを明示 |

既定値と `--host all` は Codex だけを選択します。他のアプリは明示的に指定します。
Windows ネイティブ Claude Code、Linux、macOS Intel、WSL、リモート環境の検証は
対象外です。Windows ARM64 は独自の実行ファイル、アーカイブ、更新補助プログラムを
使用します。x64 エミュレーションでの実行は ARM64 ネイティブの証拠に代えられません。
ネイティブ CI、実際のアプリへの読み込み、クリーン環境での検証は別の証拠です。

## インストール、既存導入の引き継ぎ、更新

承認済みリリースから実行ファイルと対応するアーカイブを取得し、実行前に
配布元と署名の説明を確認します。公開前の候補アーカイブはローカルビルドの成果物です。

```text
./opensocrates install --host codex --package /absolute/path/to/bundle.zip
./opensocrates status --host codex
./opensocrates update --host codex --package /absolute/path/to/new-bundle.zip
```

Windows ではネイティブ `opensocrates.exe` と引用符で囲んだローカルドライブの
絶対パスを使用します。

```text
.\opensocrates.exe install --host codex --package "C:\Downloads\bundle.zip"
.\opensocrates.exe status --host codex
```

ARM64 では `opensocrates-v1.6.0-windows-arm64.exe` と対応する
`opensocrates-v1.6.0-windows-arm64.zip` を選びます。例の実行ファイル名は実際の
ダウンロード名に置き換えるか、アーカイブの `bin/` から展開したものを使用します。

所有権を確認済みの v1.5 npm 導入は、次の明示的な操作で一度だけ引き継げます。

```text
./opensocrates adopt --host codex --package /absolute/path/to/bundle.zip
```

旧更新ツールと調整し、設定、登録、信頼、無効状態を維持します。npm パッケージを
広範囲に削除したり、利用者データを消したりしません。不明なファイルや変更済みの
ファイルは競合として維持します。`verify`、`manage diagnose`、`remove` は同じ
アプリと範囲を指定します。Claude と Antigravity の `enable`、`disable` も同様です。
Codex の有効状態はアプリ自身で管理します。

Mac Claude は `--host claude`、Antigravity は `--host antigravity` を指定します。
`--workspace /absolute/path/to/existing/workspace` は任意で、省略するとグローバルです。
アカウント用スキルは別途エクスポートします。

```text
./opensocrates export --host claude-chat --package /absolute/path/to/account.zip --output /absolute/path/to/opensocrates-account.zip
```

既存スキルの置換前にファイルと有効状態をバックアップし、正しい Claude アカウントの
**Customize → Skills** でアップロードして有効化します。必要なアカウント機能、
アップロード、有効化をそれぞれ確認します。**Settings → General → Instructions for Claude** に
次の指示を追加し、既存の指示を維持します。旧 Cowork は **Settings → Cowork → Global
instructions** です。アカウントが異なる場合はそれぞれ設定します。

```text
資料の統合、選択肢の比較、判断、メッセージの作成など、解釈や判断が必要な
依頼では、私が名前を挙げなくても有効な OpenSocrates スキルを読み込み、
その指示に従ってください。思考法を適用する前に手順全体を読み、適用条件を
確認してください。書式変換などの機械的な作業に不要な手順を追加しないでください。
```

保存後に新しい会話を始めます。スキルはモデルが選択し、毎メッセージの呼び出しは
保証しません。Codex は対話セッションで 7 個のフックを信頼手順に沿って確認します。
未承認フックは実行されない場合があります。引き継ぎや更新は無効状態を維持します。
`status` はローカル導入と整合性を示し、進行中の会話への読み込みや適用を証明しません。

## 自動更新

Codex の管理ツールは `auto-update enable`、`status`、`run`、`disable` を提供します。
選択して有効化するとフックの外で `stable` を 24 時間ごとに確認し、ログイン時の
確認には遅延を設けます。Mac は利用者 LaunchAgent、Windows はタスクスケジューラを
使用します。署名メタデータ、期限、巻き戻し防止、プラットフォーム整合性、互換性を
適用前に確認します。メジャー版や互換性を壊すスキーマ変更は自動適用しません。
オフラインでは現行版を維持し、開始済みのプロセスは元のアーカイブを保持します。
必要に応じてアプリの再読み込みや新しい会話を開始します。アカウントは手動アップロード、
他の連携は現時点で予約更新の対象外です。本番更新の信頼ルートと署名サービスは
未整備で、条件を満たすまでは利用不可と報告します。

## 思考指示の言語

現在の対応言語は `en`、`ko`、`zh`、`ja` です。任意の旧セレクターは明示的な
設定、保存した設定、現在の入力の文字判定の順に選びます。仮名があれば日本語、
それ以外はハングルが優勢なら韓国語、漢字が優勢なら中国語です。漢字のみの
日本語は明示的に指定します。空入力、ラテン文字のみ、同数の場合は英語です。

```text
./opensocrates locale get
./opensocrates locale set en
./opensocrates locale set ko
./opensocrates locale set zh
./opensocrates locale set ja
./opensocrates locale set follow
./opensocrates locale reset
```

ホスト引数は不要です。Windows は `.\opensocrates.exe` を使用します。`follow` と
`reset` はこの設定だけを解除します。設定は任意の旧セレクターに作用し、状態を
保持しない判断要求やアカウント用スキルを設定しません。判断 JSON には明示的な
`locale` が必要です。ネイティブ Claude 入口は保存した設定を読みません。
アカウントスキルと Antigravity は各言語のガイドと完全な参照を使用します。
指示の言語、回答の言語、アプリ UI、管理ツール出力は別です。全メッセージの翻訳は
約束せず、方法 ID、JSON キー、出典行は変更しません。

## 出典、プライバシー、証拠

適切な正典方法を完全に読み、実際に適用した回答だけが、正確に同じ最終行
`Powered by OpenSocrates` を使います。読者ガイドだけの利用や機械的な作業は
該当せず、この行だけでは適用や品質改善の証明になりません。通常の判断経路は
追加の選択モデルや認証呼び出しを行わず、生のプロンプト、会話、スクリーンショット、
隠れた推論を保存しません。Claude ネイティブ入口は会話を読まず DB を初期化しません。
アカウント用スキルに実行コードはありません。アプリ自身の認証、権限、保管方針は
通常の会話に引き続き適用されます。

導入、読み込み、完全な読解、実際の適用、結果の有用性は別の証拠です。旧候補の
署名・公証記録は v1.5.1 統合後の新しいファイルを検証しません。公開済みや全アプリ
有効化済みとも主張しません。一般的な品質、費用、速度の改善は保証しません。

- [ネイティブ導入・移行と証拠の説明（英語）](docs/native-v1.6.md)
- [導入後の設定（英語）](docs/setup-guide.md) · [セキュリティ](SECURITY.md)
- [方法本文](content/methods/) · [変更履歴](CHANGELOG.md) · [貢献ガイド](CONTRIBUTING.md)

OpenSocrates は [MIT ライセンス](LICENSE) の独立プロジェクトで、OpenAI、
Anthropic、Google の公式製品ではなく、各社からの承認も受けていません。
