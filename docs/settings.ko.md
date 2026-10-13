# 사고 지시문 언어 선호

[English](settings.md) · [v1.5.2 언어와 플랫폼 범위](v1.5.2.ko.md)

네이티브 런타임은 정해진 언어 선호를 받습니다. 유지되는 선택기의 지시문 언어에
적용하며 npm 설치기 옵션·답변 언어·호스트 화면 설정·자동 스킬 사용 보장은 아닙니다.

| 코드 | 정본 지시문 언어 |
| --- | --- |
| `en` | 영어 |
| `ko` | 한국어 |
| `zh` | 간체 중국어 |
| `ja` | 일본어 |
| `fr` | 프랑스어 |
| `de` | 독일어 |
| `it` | 이탈리아어 |
| `es` | 스페인어 |
| `pt` | 일반 코드 아래 브라질식 철자를 쓰는 포르투갈어 |
| `th` | 태국어 |
| `follow` | 저장한 선호를 지우고 현재 입력 문자 판별 따르기 |

Mac의 설치된 Codex 패키지 루트에서 실행합니다.

```sh
bin/launch.sh locale codex get
bin/launch.sh locale codex set fr
bin/launch.sh locale codex set th
bin/launch.sh locale codex set follow
bin/launch.sh locale codex reset
```

Windows x64의 Codex 패키지 루트에서는 다음을 사용합니다.

```powershell
node bin/launch.mjs locale codex get
node bin/launch.mjs locale codex set pt
node bin/launch.mjs locale codex reset
```

저장소의 고정된 소스 개발 환경에서는 다음 진입을 사용합니다.

```sh
uv run --locked python -m opensocrates locale get
uv run --locked python -m opensocrates locale set de
uv run --locked python -m opensocrates locale reset
```

`set`은 `en|ko|zh|ja|fr|de|it|es|pt|th|follow` 중 정확히 한 값을 받습니다.
`get`·`reset`은 언어 인자를 받지 않습니다. 지원하지 않는 값과 추가 인자는
거부합니다. 임의의 언어나 설치기 `--locale` 옵션은 없습니다. `follow`·`reset`은
기존 설정 변경 경로로 `locale_preference`만 해제합니다. 다른 설정과 선호는
기존 정규화·저장 계약을 따릅니다.

신뢰된 요청 선호가 저장 선호보다 우선합니다. 둘 다 없으면 인식하는 가나가
있을 때 일본어를 선택합니다. 그 외에는 태국 문자·한글·한자 중 우세한 문자에
따라 태국어·한국어·중국어를 선택합니다. 빈 입력·동률·알 수 없는 문자는
영어입니다. 라틴 문자를 공유하는 프랑스어·독일어·이탈리아어·스페인어·
포르투갈어에는 명시적 또는 저장한 선택이 필요합니다. 한자만 있는 일본어는
모호하므로 `ja`를 명시하세요. 문자 판별은 단어가 아닌 문자를 세며 모든
혼합 입력의 언어를 알아내는 기능이 아닙니다.

상태 없는 `decision` 요청은 정본 열 언어 코드 중 하나를 JSON `locale`에
명시해야 하며 `follow`를 받거나 저장 설정을 읽지 않습니다. Mac은
`bin/launch.sh decision codex`, Windows는 `node bin/launch.mjs decision codex`,
Mac Claude 패키지는 `bin/launch.sh decision claude`를 사용합니다. 설치된
`skills/opensocrates/references/decision/request.json`의 요청 형식과 라우팅 계약을
따르고 임의의 `--locale` 옵션을 전달하지 마세요.

기존 SDK 선택기는 Windows에서 사용할 수 없습니다. 계정 스킬·Antigravity
콘텐츠는 이 선호 저장소 없이 언어 안내·참조를 사용합니다. 네이티브 선호를
설정해도 Claude 계정 스킬을 업로드·활성화·설정하지 않습니다. 기존 두 언어·
네 언어 콘텐츠는 과거 버전으로 유지하며 오래된 패키지에서는 그 패키지에
제공되는 언어만 선택하세요.
