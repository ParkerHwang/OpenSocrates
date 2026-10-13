<p align="center">
  <img src="https://raw.githubusercontent.com/ParkerHwang/OpenSocrates/main/docs/assets/opensocrates-banner.jpg" alt="OpenSocrates" width="820">
</p>

**供代理参考：** [选择已发布的软件包并验证设置](docs/agent-discovery.md)。Go 候选版请使用下文和原生指南。

# OpenSocrates

**帮助你得到能够理解、评估并使用的推理结果。**

OpenSocrates 提供 48 种完整推理方法，帮助综合资料、理解观点、比较方案和撰写消息。
当前基线为已发布的 v1.5.2：英文、韩文、简体中文、日语、法语、德语、意大利语、
西班牙语、葡萄牙语和泰语，共 480 份完整步骤、3,840 个标准案例和 1,440 个教师
问题，内容修订号为 5。葡萄牙语使用通用 `pt` 代码和巴西拼写。原有四种语言的
步骤和案例正文、元数据和问题值保持不变；方法修订标识从 4 升至 5。方法正文
升级另行安排在 v1.6.1 或之后，编程专用功能不在本次范围内。

[English](README.md) | [한국어](README.ko.md) | **简体中文** | [日本語](README.ja.md) | [Français](README.fr.md) | [Deutsch](README.de.md) | [Italiano](README.it.md) | [Español](README.es.md) | [Português](README.pt.md) | [ไทย](README.th.md)

## v1.6.0 原生迁移候选

本分支是**尚未发布的 v1.6.0 实现候选**。Go 运行时、管理工具、安装器、更新器
和开发工具替代原有 Python、JavaScript、npm 路径。用户无需安装 Go、Python、
Node.js 或 npm。正式资产通过 [GitHub Releases](https://github.com/ParkerHwang/OpenSocrates/releases)
分发；生产签名、更新信任根和原生发布验证仍须满足对应发布条件。
当前已发布版本为 [v1.5.2](https://github.com/ParkerHwang/OpenSocrates/releases/tag/v1.5.2)。
此候选已同步十种语言的内容和语言设置契约；npm 命令属于独立维护渠道。

| 应用 | 交付方式 | 平台与启用要求 |
| --- | --- | --- |
| Codex CLI / Desktop | 原生钩子、控制器和 Go 判断运行时 | macOS ARM64、Windows x64/ARM64（默认 PowerShell）；检查 7 个钩子后开始新会话 |
| Claude Code CLI / Desktop 本地 Code | 无状态原生入口及完整本地参考 | macOS ARM64；需要 Claude CLI、登录及插件和钩子权限 |
| Claude 网页版 / Desktop Chat / Cowork | 不含可执行代码的账户技能 ZIP | 在所有支持目标验证、导出后，另行上传并启用 |
| Antigravity 对话应用 | 具有明确归属范围的规则与技能 | macOS ARM64、Windows x64/ARM64；明确选择工作区或全局范围 |

默认值和 `--host all` 只选择 Codex。其他应用必须显式指定。Windows 原生
Claude Code、Linux、macOS Intel、WSL 和远程应用验证不在本次范围内。
Windows ARM64 使用独立原生可执行文件、归档和更新辅助程序；x64 仿真运行
不能代替 ARM64 原生证据。原生 CI、实际应用加载、干净机器验证是不同证据。

## 安装、接管与更新

从经过批准的发布下载原生可执行文件和匹配的平台归档，执行前核对发布的来源
与签名说明。发布之前，本候选归档属于本地构建资产。

```text
./opensocrates install --host codex --package /absolute/path/to/bundle.zip
./opensocrates status --host codex
./opensocrates update --host codex --package /absolute/path/to/new-bundle.zip
```

Windows 使用原生 `opensocrates.exe` 和加引号的本地驱动器绝对路径：

```text
.\opensocrates.exe install --host codex --package "C:\Downloads\bundle.zip"
.\opensocrates.exe status --host codex
```

ARM64 选择 `opensocrates-v1.6.0-windows-arm64.exe` 和匹配的
`opensocrates-v1.6.0-windows-arm64.zip`。示例中的可执行文件名称应替换为实际
下载名称，或使用从归档 `bin/` 解出的文件。

已核实归属的 v1.5 npm 安装可以显式接管一次：

```text
./opensocrates adopt --host codex --package /absolute/path/to/bundle.zip
```

接管协调旧更新器并保留设置、注册、信任和禁用状态。它不会广泛卸载 npm 包
或删除用户数据。未知或已修改文件作为冲突保留。`verify`、`manage diagnose`
和 `remove` 使用同一应用与范围；Claude 和 Antigravity 的 `enable`、`disable`
也使用该范围。Codex 启用状态由应用本身控制。

Mac Claude 使用 `--host claude`。Antigravity 使用 `--host antigravity`，可选
`--workspace /absolute/path/to/existing/workspace`；省略则选择全局范围。
账户技能需单独导出：

```text
./opensocrates export --host claude-chat --package /absolute/path/to/account.zip --output /absolute/path/to/opensocrates-account.zip
```

替换现有账户技能前，备份其文件与启用状态；随后在正确 Claude 账户的
**Customize → Skills** 上传并启用。需要的账户功能、上传与启用都应单独确认。
在 **Settings → General → Instructions for Claude** 追加下列内容并保留原有
指令；旧 Cowork 使用 **Settings → Cowork → Global instructions**。不同账户
分别设置。

```text
对于需要解释或判断的任务，例如综合资料、比较方案、作出决策或撰写消息，
即使我没有提到名称，也请加载已启用的 OpenSocrates 技能并遵循其指令。
应用推理方法前，先完整阅读其步骤并确认适用条件。对于格式转换等机械性
工作，不要增加不必要的推理步骤。
```

保存后开始新会话。账户技能由应用模型选择，不保证每条消息都调用。
Codex 必须在交互会话中检查 7 个钩子的信任流程；未获信任的钩子可能被跳过。
接管或更新保留禁用状态。`status` 只检查本地安装和完整性，不证明运行中的
会话已加载或实际应用了新内容。

## 自动更新

Codex 的原生管理工具提供 `auto-update enable`、`status`、`run`、`disable`。
用户选择启用后，在钩子之外每 24 小时检查 `stable`，登录检查有延迟；Mac
使用用户 LaunchAgent，Windows 使用任务计划程序。签名元数据、期限、回退
保护、平台完整性及兼容性均在应用更新前检查。主版本或破坏兼容性的模式
变化不自动更新。离线保留现有版本，启动过的进程保留其归档；必要时重新
加载应用或开始新会话。账户技能仍需手动上传，其他应用暂不参与计划更新。
生产更新信任根和签名服务尚未就绪，满足发布条件前报告不可用。

## 推理指令语言

当前支持 `en`、`ko`、`zh`、`ja`、`fr`、`de`、`it`、`es`、`pt`、`th`。
可选旧选择器按明确偏好、保存偏好、当前文字判别的顺序选择。假名优先选日语，
否则占优势的泰文、韩文或汉字选择泰语、韩语或中文。拉丁字母的欧洲语言需要
明确或保存的偏好。只有汉字的日语需明确 `ja`；空输入、同票或未知文字回退英文。

```text
./opensocrates locale get
./opensocrates locale set en
./opensocrates locale set ko
./opensocrates locale set zh
./opensocrates locale set ja
./opensocrates locale set fr
./opensocrates locale set de
./opensocrates locale set it
./opensocrates locale set es
./opensocrates locale set pt
./opensocrates locale set th
./opensocrates locale set follow
./opensocrates locale reset
```

这些命令不带应用参数；Windows 使用 `.\opensocrates.exe`。`follow` 和 `reset`
只清除这项偏好。设置只影响可选旧选择器，不配置无状态判断请求或账户技能。
无状态判断 JSON 要求明确的 `locale`；原生 Claude 入口不读取保存的偏好。
账户技能和 Antigravity 使用各语言指南及完整参考。指令语言与答复语言、应用
界面及管理工具输出分开，不承诺翻译每条消息。方法 ID、JSON 键和署名行不变。

## 署名、隐私与证据

只有完整读取并实际应用适用的正典方法时，答案末行才使用完全相同的
`Powered by OpenSocrates`。阅读指南或机械任务不满足条件；署名不证明实际
应用或质量提升。通常判断路径无额外选择模型或认证调用，不保存原始提示、
对话、截图或隐藏推理。原生 Claude 不读取对话或初始化数据库；账户技能无
可执行代码。正常会话仍受应用自身认证、权限和数据保留政策约束。

安装、加载、完整阅读、实际应用和结果有用性属于不同证据。旧候选的签名或
公证凭据不验证合并 v1.5.2 后的新文件，也不证明此候选已发布或所有应用都
已启用。本项目不宣称普遍的质量、费用或速度改善。

- [原生安装、接管和证据说明（英文）](docs/native-v1.6.md)
- [安装后设置（英文）](docs/setup-guide.md) · [安全政策](SECURITY.md)
- [方法正文](content/methods/) · [版本变更](CHANGELOG.md) · [贡献指南](CONTRIBUTING.md)

OpenSocrates 采用 [MIT 许可证](LICENSE)，是独立项目，不隶属于 OpenAI、
Anthropic 或 Google，也未获其背书。
