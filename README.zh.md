<p align="center">
  <img src="https://raw.githubusercontent.com/ParkerHwang/OpenSocrates/main/docs/assets/opensocrates-banner.jpg" alt="OpenSocrates" width="820">
</p>

# OpenSocrates

**帮助你得到能够理解、评估并使用的推理结果。**

OpenSocrates 为资料综合、观点理解、方案比较和消息撰写提供 48 种完整的推理
方法。v1.5.1 新增简体中文（`zh`）和日语（`ja`），并保留原有英文、韩文方法
正文。四种语言共有 192 份完整步骤文件；每种方法每种语言有 3 个面向代理的
教师问题，共 576 个。内容修订号为 4。此版本不新增编程专用方法。

[English](README.md) | [한국어](README.ko.md) | **简体中文** | [日本語](README.ja.md)

## 支持的平台与应用

| 应用 | 交付方式 | 平台与启用要求 |
| --- | --- | --- |
| Codex | 现有钩子、控制器和原生判断运行时 | Apple Silicon Mac、Windows x64；在交互会话中检查 7 个钩子的信任状态 |
| Claude Code CLI / Desktop 本地 Code | 无状态原生入口及完整本地参考文件 | Apple Silicon Mac；需要 Claude CLI、登录及插件和钩子权限 |
| Claude 网页版 / Desktop Chat / Cowork | 不含可执行代码的账户技能 ZIP | 在 Mac 或 Windows 导出后，另行上传、启用并保存账户指令 |
| Antigravity 对话应用 | 模块化规则与技能 | Apple Silicon Mac、Windows x64；选择工作区或全局范围 |

平台范围沿用 v1.5.0。Windows 原生 Claude Code 不在此版本范围内；Windows
ARM64 支持属于独立的 v1.6.0 工作。账户技能不会安装原生 Claude 集成。

## 安装或更新

准备 Node.js 20 或更高版本，安装并登录所需应用。安装包内含原生运行时，
无需另装 Python。从 [v1.5.1 发布页](https://github.com/ParkerHwang/OpenSocrates/releases/tag/v1.5.1)
获取归档和 SHA-256 校验文件，或使用版本固定的 npm 安装器。

```sh
npx --yes opensocrates@1.5.1 install --host codex
npx --yes opensocrates@1.5.1 status --host codex
# 更新现有 Codex 安装：
npx --yes opensocrates@1.5.1 update --host codex
```

在交互式 Codex 中输入 `/hooks`，检查 OpenSocrates 的 7 个钩子，按应用提供的
信任流程完成必要审批，然后开始新对话。`status` 说明安装及完整性状态，不能
证明钩子已被信任或指令已在真实任务中应用。

在 Apple Silicon Mac 安装 Claude Code 集成：

```sh
npx --yes opensocrates@1.5.1 install --host claude
npx --yes opensocrates@1.5.1 status --host claude
```

为 Antigravity 指定已存在的工作区绝对路径；省略 `--workspace` 则选择全局范围。
同一任务避免同时使用工作区和全局副本。

```sh
npx --yes opensocrates@1.5.1 install --host antigravity --workspace /absolute/path/to/workspace
```

Windows 使用本地驱动器绝对路径并加引号，例如 `"C:\Work\Reading Workshop"`。
Claude 账户技能需导出到已存在文件夹内的绝对 ZIP 路径：

```sh
npx --yes opensocrates@1.5.1 export --host claude-chat --output /absolute/path/to/opensocrates-1.5.1-account.zip
```

随后在 Claude 的 **Customize → Skills** 上传并启用。替换已有 OpenSocrates
技能前，下载备份并记录其启用状态。导出成功不等于上传、启用或自动选择成功。
在 **Settings → General → Instructions for Claude** 追加以下指令，保留原有
指令；旧版 Cowork 可使用 **Settings → Cowork → Global instructions**。
网页版和 Desktop 若使用不同账户，应分别设置。

```text
对于需要解释或判断的任务，例如综合资料、比较方案、作出决策或撰写消息，
即使我没有提到名称，也请加载已启用的 OpenSocrates 技能并遵循其指令。
应用推理方法前，先完整阅读其步骤并确认适用条件。对于格式转换等机械性
工作，不要增加不必要的推理步骤。
```

保存后开始新对话。账户技能由应用模型选择，可能遗漏；它不新增原生钩子，也
不保证每条消息都会调用。默认安装和 `--host all` 仍只选择 Codex，其他应用
必须显式指定。新集成不新增 purge、信任重置或自动更新操作。
[设置指南（英文）](docs/setup-guide.md)说明后续界面步骤；
[Mac 指南](docs/macos-v1.5.md)和 [Windows 指南](docs/windows-v1.5.md)保留
v1.5.0 的安装与恢复基线，当前命令请使用上述 1.5.1 版本。

## 指令语言

优先使用明确指定的语言，其次使用已保存的语言偏好，再根据当前输入的文字
判断。含平假名或片假名时选择日语；否则韩文占优时选择韩语，汉字占优时
选择中文。只有汉字的输入无法可靠区分中文与日语，默认使用中文，需要日语
时应明确指定。空输入、只有拉丁字符或字符数量持平时回退到英文。

推理指令语言与 npm 安装器的命令输出、应用界面语言分开。本次更新不承诺
翻译每条安装器消息。关于运行时 `locale` 偏好命令和显式 JSON 请求，请参阅
[语言与范围指南（英文）](docs/v1.5.1.md)。

## 使用标注与隐私

只有完整读取并实际应用了适用的正典方法，最终答案才以完全相同的英文行
`Powered by OpenSocrates` 结尾。仅使用阅读指导或完成机械性工作不满足条件。
该行是来源标注，不能证明原生应用成功或答案质量提升。

默认判断路径不额外调用选择模型，不保存原始提示、对话、截图或隐藏推理。
Claude 原生入口不读取对话，也不初始化数据库；账户技能不含可执行代码。
应用本身的认证、权限、留存设置及条款仍适用于正常对话。
[安全政策](SECURITY.md)说明相关边界。安装、加载、完整阅读、实际应用和结果
是否有用属于不同的证据；本项目不宣称普遍的质量、成本或速度提升。

- [方法正文](content/methods/) · [判断点约定](docs/decision-points.md)
- [版本变更](CHANGELOG.md) · [贡献指南](CONTRIBUTING.md) · [行为准则](CODE_OF_CONDUCT.md)

OpenSocrates 采用 [MIT 许可证](LICENSE)，是独立项目，不隶属于 OpenAI、
Anthropic 或 Google，也未获其背书。
