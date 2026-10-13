<p align="center">
  <img src="https://raw.githubusercontent.com/ParkerHwang/OpenSocrates/main/docs/assets/opensocrates-banner.jpg" alt="OpenSocrates" width="320">
</p>

# OpenSocrates

**在 AI 对话中运用 48 种推理方法。**

OpenSocrates 为 **Claude、Codex 和 Antigravity** 提供可重复使用的推理流程。
比较方案，理清相互矛盾的信息，从另一个角度审视计划。
用自己的话描述任务即可；每种方法都提供可参考的问题、检查项和步骤。

[从你使用的应用开始](#start-with-your-app) · [查看使用示例](#see-it-in-a-task) · [探索推理方法](#a-method-for-the-question)

**48 种方法 · 10 种指令语言 · MIT 许可证**

[English](README.md) · [한국어](README.ko.md) · **简体中文** · [日本語](README.ja.md) · [Français](README.fr.md) · [Deutsch](README.de.md) · [Italiano](README.it.md) · [Español](README.es.md) · [Português](README.pt.md) · [ไทย](README.th.md)

## 为手头的工作准备的推理工具

- **从你的任务开始。** 每种方法都预先写好了问题和检查项，可以在不同对话中重复使用。
- **找到有用的角度。** 运用相应的方法比较方案、评估证据、探索假设和提前规划。
- **按自己的需要使用。** 阅读每种方法的完整步骤，研究其中的案例，将开源内容调整为适合你工作的形式。

<a id="see-it-in-a-task"></a>

## 看看如何用于实际任务

设置完成后，可以这样提问：

> 我们原本打算购买一个托管工具，但现在工作流程必须离线运行。
> 应该购买、自己开发，还是暂时用手工处理？

对于这样的决策，[权衡分析](content/methods/trade-off-analysis/procedure.zh.md)
提供了一套可重复使用的步骤：确定要求，比较可行方案，区分已知事实与假设，
并说明什么会改变建议。这种方法为你平常提出的请求提供了相应的思考结构。

<a id="start-with-your-app"></a>

## 从你使用的应用开始

选择你想使用 OpenSocrates 的应用。
[获取 v1.5.2](https://github.com/ParkerHwang/OpenSocrates/releases/tag/v1.5.2)。

<details>
<summary><strong>Claude Chat 和 Cowork</strong> — 上传技能并开始对话</summary>

适用于 Claude 网页版、Desktop Chat 和 Cowork：

1. 在 **Settings → Capabilities** 中启用 **Code execution and file creation**。如果账户由组织管理，请确认组织政策允许 Skills 和代码执行。
2. 下载[账户技能 ZIP](https://github.com/ParkerHwang/OpenSocrates/releases/download/v1.5.2/opensocrates-1.5.2-claude-chat-skills.zip)及其 [SHA-256 文件](https://github.com/ParkerHwang/OpenSocrates/releases/download/v1.5.2/opensocrates-1.5.2-claude-chat-skills.zip.sha256)。
3. 打开 **Customize → Skills → + → Create skill → Upload a skill**，上传 ZIP 并启用。在替换已有的 OpenSocrates 技能前，先进行备份。
4. 保留已有指令，在你使用的每个 Claude 账户中添加[一次性账户指令](docs/setup-guide.md#claude-standing-instructions)。开始新对话并描述你的任务。

便携式技能 ZIP 包含完整方法和案例。
[图解设置指南](docs/setup-guide.md#2-claude-account-skill-enable-it-and-add-account-instructions) · [Claude Skills 指南](https://support.claude.com/en/articles/12512180-use-skills-in-claude)

</details>

<details>
<summary><strong>Claude Code</strong> — Apple Silicon Mac</summary>

你需要 [Node.js 20 或更高版本](https://nodejs.org/en/download)、Claude CLI
和已登录的 Claude 账户。适用于终端中的 Claude Code 和 Claude Desktop 中的本地 Code。
在**终端**中运行：

```sh
npx --yes opensocrates@1.5.2 install --host claude
npx --yes opensocrates@1.5.2 diagnose --host claude
```

确认 `enabled: true`、`integrity: verified` 和 `registration: confirmed`。
检查出现的项目信任提示，然后开始新的本地会话。
[图解设置指南](docs/setup-guide.md#3-claude-code-check-the-local-mac-plugin)

</details>

<details>
<summary><strong>Codex</strong> — Apple Silicon Mac 或 Windows x64</summary>

你需要 [Node.js 20 或更高版本](https://nodejs.org/en/download)和 Codex。
原生运行时已包含在包中。在 **Mac 的终端**或 **Windows 的 PowerShell** 中运行：

```sh
npx --yes opensocrates@1.5.2 install --host codex
npx --yes opensocrates@1.5.2 status --host codex
```

打开交互式 Codex，在输入框中输入 `/hooks`。检查 OpenSocrates 的七个钩子定义，
批准你信任的定义，然后开始新对话。
[图解设置指南](docs/setup-guide.md#1-codex-review-and-approve-opensocrates-hooks)

更新已有的 Codex 安装：

```sh
npx --yes opensocrates@1.5.2 update --host codex
```

</details>

<details>
<summary><strong>Antigravity</strong> — Apple Silicon Mac 或 Windows x64</summary>

你需要 [Node.js 20 或更高版本](https://nodejs.org/en/download)。选择一个工作区，
将示例路径替换为已存在文件夹的完整路径。
在 **Mac 的终端**或 **Windows 的 PowerShell** 中运行：

```sh
npx --yes opensocrates@1.5.2 install --host antigravity --workspace "/absolute/path/to/workspace"
```

在 Windows 中，使用带引号的本地驱动器路径，例如 `"C:\Work\Reading Workshop"`。
要进行全局设置，省略 `--workspace`。为同一个项目选择全局或工作区安装，
然后开始新对话。
[确认技能和规则](docs/setup-guide.md#4-antigravity-check-both-the-skill-and-rule)

</details>

**想让代理协助设置？** 使用[设置请求](docs/setup-guide.md#ask-an-agent-to-finish-setup)
或[当前安装指南](docs/agent-discovery.md)。用对应名称的 `--host` 选项选择各个应用；
默认选项和 `--host all` 选择 Codex。

<a id="a-method-for-the-question"></a>

## 为问题选择相应的方法

| 你正在处理的工作 | 可以探索的方法 |
| --- | --- |
| 根据相互竞争的优先事项比较方案 | [权衡分析](content/methods/trade-off-analysis/procedure.zh.md) |
| 理解计划中被视为理所当然的假设 | [假设映射](content/methods/assumption-mapping/procedure.zh.md) |
| 评估支持某项主张的依据 | [批判性思维](content/methods/critical-thinking/procedure.zh.md) |
| 为计划可能出现的问题做准备 | [事前验尸分析](content/methods/premortem-analysis/procedure.zh.md) |

每种方法都包含目的、使用条件、完整步骤、案例以及供助手思考的问题。
阅读内容，了解推理步骤，并在不同工作中重复使用这些方法。

[浏览全部 48 种方法](content/methods/)

## 十种语言的完整方法内容

英语、韩语、简体中文、日语、法语、德语、意大利语、西班牙语、葡萄牙语和泰语。
每种语言都包含全部 48 种方法的完整步骤和案例。

这些是助手读取的方法正文所使用的语言。
[语言指南](docs/v1.5.2.md) · [Codex 指令语言设置](docs/settings.md)

## 开源，欢迎探索

阅读完整方法和源码，将其调整为适合你的工作，或贡献新的案例。
OpenSocrates 是采用 [MIT 许可证](LICENSE)的独立项目。

[发布版本](https://github.com/ParkerHwang/OpenSocrates/releases) · [设置指南](docs/setup-guide.md) · [隐私与安全](SECURITY.md) · [贡献指南](CONTRIBUTING.md) · [问题反馈](https://github.com/ParkerHwang/OpenSocrates/issues/new/choose) · [更新日志](CHANGELOG.md)
