# Setup guide screenshots / 설정 가이드 캡처

[English guide](../../setup-guide.md) · [한국어 안내](../../setup-guide.ko.md)

## Scope / 범위

Captured on **2026-10-10**, on macOS, from **Claude Desktop 2.31226.1** and
**Antigravity 2.22.0**. These are native computer-use (CUA) screenshot outputs,
used without pixel edits. Privacy was handled before capture by collapsing
conversation sidebars and temporarily adjusting the window layout; those
layout changes were reversible. The images show the relevant settings and
installed entries, not model application, answer quality or Windows behavior.

**2026-10-10**, macOS의 **Claude Desktop 2.31226.1**·**Antigravity 2.22.0**에서
컴퓨터 유즈(CUA)로 캡처한 원본 화면입니다. 픽셀을 수정하지 않았습니다.
캡처 전에 대화 사이드바를 접고 창 배치를 일시적으로 조정해 개인정보 노출을
줄였으며 배치 변경은 되돌릴 수 있습니다. 필요한 설정·설치 항목을 보여주며,
모델의 실제 적용·답변 품질·Windows 동작을 증명하지 않습니다.

| Figure / 그림 | File / 파일 | Captured state / 캡처한 상태 |
| --- | --- | --- |
| 1 | `claude-capabilities.jpg` | Cloud code execution and file creation enabled / 코드 실행·파일 생성 켜짐 |
| 2 | `claude-replace-menu.jpg` | Existing skill's Download and Replace menu / 기존 스킬의 백업·교체 메뉴 |
| 3 | `claude-upload-form.jpg` | Existing skill replacement form before selecting a file / 파일 선택 전 기존 스킬 교체 화면 |
| 4 | `claude-skill-enabled.jpg` | Account skill enabled; account revision `v4` / 계정 스킬 켜짐·계정 수정 회차 `v4` |
| 5 | `claude-code-plugin.jpg` | Native Mac plugin `opensocrates-macos · 1.5.0` enabled / Mac 네이티브 플러그인 켜짐 |
| 6 | `antigravity-installed.jpg` | Global skill and always-on rule visible together / 전역 스킬·상시 규칙 함께 표시 |

Figure 1's **Cloud code execution and file creation** setting is required for
Claude Skills. Its existing **Allow network egress** and **All domains** values
are incidental to the capture, not OpenSocrates setup requirements. Figure 4's
`v4` is an account skill revision, not the OpenSocrates product version.

그림 1의 **Cloud code execution and file creation**은 Claude Skills에 필요한
기능입니다. 아래의 **Allow network egress**·**All domains**는 캡처 당시의 기존
설정이며 OpenSocrates 설치 요구사항이 아닙니다. 그림 4의 `v4`는 계정 스킬의
수정 회차이며 OpenSocrates 제품 버전이 아닙니다.

## Capture gaps / 캡처하지 못한 화면

Codex CLI **0.145.0** commands and the official `/hooks` route were inspected.
Computer-use safety controls blocked screenshot access to Codex desktop and
Terminal, so this guide includes no capture of either app's approval screen.
No approval screenshot is supplied for Codex.

Codex CLI **0.145.0**의 명령과 공식 `/hooks` 경로를 확인했습니다. 컴퓨터 유즈의
안전 제한으로 Codex 데스크톱·Terminal 화면을 캡처할 수 없어 해당 앱의 승인
화면 캡처는 포함하지 않았습니다.

## Official sources / 공식 출처

- [OpenAI: Hooks](https://learn.chatgpt.com/docs/hooks)
- [Claude: Use Skills in Claude](https://support.claude.com/en/articles/12512180-use-skills-in-claude)
- [Claude Code: Install plugins](https://code.claude.com/docs/en/plugins/install)
- [Claude Code: Hooks](https://code.claude.com/docs/en/hooks)
- [Antigravity: Rules](https://antigravity.google/docs/rules)
- [Antigravity: Skills](https://antigravity.google/docs/skills)

Menus and permissions may change with app version, locale or organization
policy. Use the host's actual approval controls; these screenshots are guidance,
not approval records or a substitute for login or administrator authorization.

메뉴·권한은 앱 버전·언어·조직 정책에 따라 달라질 수 있습니다. 실제 호스트의
승인 기능을 사용하세요. 캡처는 안내 자료이며 승인 기록이나 로그인·관리자
권한을 대신하지 않습니다.
