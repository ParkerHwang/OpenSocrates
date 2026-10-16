# OpenSocrates in two public examples: a preserved commitment and a wrong calculation
# OpenSocrates 공개 사례 두 가지: 지켜진 약속의 범위와 틀린 계산

Public-use draft · 15 October 2026 · Maintainer examples, prepared with AI assistance.
공개용 초안 · 2026년 10월 15일 · 제작자 사례를 AI의 도움으로 정리했습니다.

## English

A useful way to inspect an AI answer is to compare its commitments and calculations with the source facts. These two public OpenSocrates examples show why that inspection matters: one generated email preserved the difference between a draft review and final delivery; an older pricing answer gave a materially wrong sales threshold. Both records remain available. They concern different tasks, versions and requested models, so they do not form a comparison of product performance.

### An email that kept the agreed scope

In the [maker's GPTers article][email], the synthetic meeting note agreed to review a draft together on Friday afternoon. The final delivery date and final approver were explicitly undecided. A new client request asked for the final version by Friday. The task was to write a short Korean reply with a subject and body using those facts. No real customer or company material was used.

The maker supplied the complete public **v1.5.2 Korean reader guide manually**. This was a content-guided example, not a test of automatic plugin activation. Codex CLI was asked for `gpt-6.1-sol` at `low` effort, with one response and no favorable rerun. The published input prohibited tools and file reads or changes. The model name describes the request; the actual backend identity was not independently confirmed. The article does not identify a CLI version or operating system. The [public execution handoff][email-record] identifies the released reference as source `9838db16910c5f22d9dcc3c7180350cb406fd236`.

The published email retained the Friday-afternoon draft review, declined to confirm Friday final delivery, kept both the delivery date and approver unresolved, and asked to discuss approval and delivery arrangements. It did not say that this discussion had already happened. These are four observable content checks on that one output; they are not four independent trials. The Korean excerpt below is from the published final email. This English description is an editorial summary, not a separately generated English result.

The author reports exit code 0 and a final email, alongside **one error-type event whose exact message and cause were not retained**. That supports the existence of a final output, not an error-free run or reproducible environment. The event cannot be assigned the cause of a warning from a different experiment. There was no baseline email in this example and no observed customer outcome. A separately proposed three-arm, six-response comparison was [held before any model response][held-study]; its planned cells are not additional results.

This example gives readers a concrete thing to inspect before sending a message: whether a new request has become a promise without approval. It does not show that OpenSocrates improved the answer, activated natively, saved time, or produced a useful result for an independent user.

### A pricing answer with a wrong threshold

The [public pilot record][pilot] fixes three synthetic tasks before six evaluated calls on 13 October 2026: one baseline and one content-guided answer per task, with no quality reruns. It requested `gpt-6-luna` at `medium` effort through Codex CLI `0.162.0-alpha.17.2`. The actual backend identity was not independently reported. Both conditions had tools disabled and the same task and 220-word output instruction. The guided condition received the complete pinned v1.5.0 controller, decision guide, reader guide and one full canonical method; the baseline did not receive that content. The pricing method was `first-principles@3`, at source `cf6634310afcf5d5ce58484e67a73151bb4c5999`.

The pricing task assumed no other cost or capacity changes. Its public figures give the following arithmetic, in US dollars and units per month:

| Item | Source facts or arithmetic from those facts |
| --- | --- |
| Existing price, volume and costs | $50/unit; 1,000 units; $35/unit variable cost; $12,000 fixed cost |
| Existing profit | `1,000 × ($50 − $35) − $12,000 = $3,000` |
| Proposed change | 20% price cut to $40; forecast volume +30% to 1,300 |
| Forecast revenue | `1,300 × $40 = $52,000`, versus $50,000 before |
| Forecast profit | `1,300 × ($40 − $35) − $12,000 = −$5,500` |
| Break-even volume at $40 | `$12,000 ÷ $5 = 2,400` units |
| Volume to preserve $3,000 profit | `($12,000 + $3,000) ÷ $5 = 3,000` units |
| Guided answer's wrong threshold | 1,500 units; those units yield `1,500 × $5 − $12,000 = −$4,500` |

Both answers advised against launching the discount broadly on the forecast alone. The baseline correctly gave 3,000 units to preserve profit and 2,400 to break even. The guided answer correctly computed the forecast loss, then incorrectly claimed that 1,500 units would preserve the existing profit. It carried that wrong threshold into its proposed limited trial. A reasonable headline recommendation therefore coexisted with a material error in the action condition. The complete failure is retained in the pilot and tracked in [issue #114][failure]. The table explains the published numbers; it is not a new model run or a new financial recommendation.

The wider pilot also preserves ties and omissions: both onboarding answers held broad rollout, but the guided answer did not explicitly specify random assignment; both changed-evidence answers made vendor selection conditional, while the guided answer did not explicitly check the temporary workflow's deletion requirement. These are the maker's unblinded checks, not independent judgments or measured product error rates. The pilot separately describes a seventh diagnostic outside the six evaluated answers; that diagnostic did not replace a failed evaluated answer.

### What a reader can conclude

| Evidence | Supported conclusion | Still unestablished |
| --- | --- | --- |
| One v1.5.2 content-guided email | The published output preserved the stated commitment boundaries | Improvement over ordinary prompting, repeatability, native activation, independent use |
| One v1.5.0 pricing pair within an older pilot | This guided output had a wrong threshold; this baseline got it right | Failure frequency, causal mechanism, a reproducible regression, current-version behavior |
| Current v1.5.2 documentation | It documents delivery profiles and evidence boundaries | Universal answer quality, every-turn use, cost or latency improvement |

The examples suggest inspectable checks, not a quality promise: trace an email's commitments to the agreed facts, and recalculate quantities that govern an action. Neither record estimates present-day product efficacy. The historical failure is not proof that it persists in v1.5.2; the newer email is not proof that it was fixed. Installation, content delivery, reading, application and usefulness remain different claims, as the [English][release-en] and [Korean][release-ko] release documentation explains.

## 한국어

AI 답변을 볼 때는 문장이 매끄러운지만 보지 않고, 약속과 계산이 원래 사실에 맞는지 대조할 수 있습니다. 공개된 OpenSocrates 사례 두 개에는 그 이유가 함께 드러납니다. 한 이메일은 초안 검토와 최종 납품을 구분했고, 과거의 가격 계산 답변은 필요한 판매량을 크게 잘못 제시했습니다. 두 기록을 모두 남깁니다. 과제·버전·요청 모델이 달라 제품 성능을 서로 비교하는 자료는 아닙니다.

### 합의한 범위를 지킨 이메일

[제작자의 GPTers 글][email]에 사용한 합성 회의 메모에서는 금요일 오후에 초안을 함께 검토하기로 했습니다. 최종 납품일과 최종 승인자는 명시적으로 정하지 않은 상태였습니다. 여기에 고객이 금요일까지 최종본을 요청한 상황을 더하고, 이 사실만으로 제목과 본문이 있는 짧은 한국어 답장을 작성하도록 했습니다. 실제 고객이나 회사 자료는 사용하지 않았습니다.

제작자는 **v1.5.2의 공개 한국어 독자 지침 전체를 수동으로 제공**했습니다. 콘텐츠를 제공한 사례이며 설치형 플러그인의 자동 활성화 시험이 아닙니다. Codex CLI에서 `gpt-6.1-sol`과 `low` 추론 강도를 요청했고, 응답 1회로 고정해 유리한 답을 얻기 위한 재실행은 하지 않았습니다. 공개 입력에서는 도구 호출과 파일 읽기·수정을 금지했습니다. 요청 모델명과 실제 백엔드의 독립 확인은 다르며, 백엔드 모델은 독립 확인되지 않았습니다. 기사에는 CLI 버전과 운영체제가 명시되지 않았습니다. [공개 실행 인계][email-record]의 배포 기준은 소스 `9838db16910c5f22d9dcc3c7180350cb406fd236`입니다.

공개된 최종 메일에는 다음 문장이 있습니다.

> 최종 납품일과 최종 승인자는 아직 정해지지 않아, 금요일까지 최종본을 전달드릴 수 있다고 확답드리기는 어렵습니다.

본문에서 확인할 수 있는 행동은 네 가지입니다.

1. 금요일 오후의 초안 검토 약속을 유지했습니다.
2. 금요일 최종 납품을 확약하지 않았습니다.
3. 최종 납품일과 최종 승인자를 모두 미정 상태로 남겼습니다.
4. 승인·납품 일정의 협의를 요청했으며, 협의가 끝났다고 쓰지 않았습니다.

한 출력에서 확인한 네 항목입니다. 독립적인 시험 네 번을 뜻하지 않습니다. 위 영어 설명은 이 한국어 결과를 편집해 요약한 것이며, 별도로 생성한 영어 답변이 아닙니다. [원문][email]에서 전체 메일과 공개 합성 입력을 볼 수 있습니다.

실행 한계도 있습니다. 작성자는 종료 코드 0과 최종 메일을 확인했지만, **정확한 메시지와 원인을 보존하지 않은 error 유형 이벤트가 한 개** 있었다고 밝혔습니다. 최종 답변이 나왔다는 기록이며, 오류 없는 실행이나 환경 재현성을 입증하지는 않습니다. 다른 실험에서 나온 경고 원인을 이 이벤트에 붙일 수도 없습니다. 이 예시에는 일반 요청만 사용한 비교 메일이나 실제 고객 성과가 없습니다. 별도로 계획한 세 조건·응답 여섯 개 비교도 [모델 응답 전에 보류][held-study]되었으므로 결과에 더하지 않습니다.

보내기 전 확인할 지점은 구체적입니다. 고객의 새 요청이 승인되지 않은 약속으로 바뀌었는지 메모와 대조하는 것입니다. 이 한 출력으로 OpenSocrates가 답을 개선했거나, 네이티브로 활성화됐거나, 시간을 줄였거나, 독립 사용자에게 유용했다고 결론 낼 수는 없습니다.

### 필요한 판매량을 잘못 계산한 가격 답변

[공개 파일럿][pilot]은 2026년 10월 13일 합성 과제 세 개를 먼저 정하고, 각 과제에서 일반 조건과 콘텐츠 제공 조건을 한 번씩 실행한 기록입니다. 평가 대상 호출은 여섯 번이며 품질에 따른 재실행은 없었습니다. Codex CLI `0.162.0-alpha.17.2`에서 `gpt-6-luna`와 `medium`을 요청했지만, 실제 백엔드 모델은 독립 보고되지 않았습니다. 두 조건 모두 도구를 끄고 같은 과제와 220단어 출력 지시를 사용했습니다. 콘텐츠 제공 조건에는 고정된 v1.5.0 컨트롤러·판단 안내·독자 안내와 정본 방법 하나의 전체 절차를 제공했고, 일반 조건에는 제공하지 않았습니다. 가격 과제의 방법은 `first-principles@3`, 소스는 `cf6634310afcf5d5ce58484e67a73151bb4c5999`입니다.

다른 비용·생산능력 변화가 없다는 가정에서 공개 수치는 다음과 같습니다. 금액은 미국 달러, 판매량은 월 기준입니다.

| 항목 | 원문 사실 또는 그 사실로부터의 계산 |
| --- | --- |
| 기존 가격·판매량·비용 | 개당 $50, 1,000개, 변동비 개당 $35, 고정비 $12,000 |
| 기존 이익 | `1,000 × ($50 − $35) − $12,000 = $3,000` |
| 제안한 변경 | 가격 20% 인하로 $40, 판매량 30% 증가 예상으로 1,300개 |
| 예상 매출 | `1,300 × $40 = $52,000`, 기존 매출 $50,000 |
| 예상 이익 | `1,300 × ($40 − $35) − $12,000 = −$5,500` |
| $40에서 손익분기 판매량 | `$12,000 ÷ $5 = 2,400`개 |
| 기존 이익 $3,000 유지에 필요한 판매량 | `($12,000 + $3,000) ÷ $5 = 3,000`개 |
| 콘텐츠 제공 답변의 틀린 기준 | 1,500개. 실제로는 `1,500 × $5 − $12,000 = −$4,500` |

두 답변 모두 예상 매출만 보고 전면 할인하지 말라고 했습니다. 일반 조건은 이익 유지에 필요한 3,000개와 손익분기 2,400개를 맞혔습니다. 콘텐츠 제공 조건은 예상 손실은 맞게 계산했지만, 기존 이익을 유지할 수 있는 판매량을 1,500개로 틀리게 제시하고 제한 실험의 기준에도 이 값을 사용했습니다. 큰 방향의 권고가 그럴듯해도 실행 조건에는 중요한 오류가 남을 수 있습니다. 전체 실패 답변은 파일럿에 보존되어 있으며 [이슈 #114][failure]에서 추적합니다. 표는 공개 수치를 설명하는 계산이며 새 모델 실행이나 새로운 재무 권고가 아닙니다.

다른 두 과제의 비슷한 결과와 누락도 파일럿에 남아 있습니다. 온보딩에서는 둘 다 전면 출시를 보류했지만, 콘텐츠 제공 답변은 무작위 배정을 명시하지 않았습니다. 근거 변경 과제에서는 둘 다 공급업체 선택에 확인 조건을 붙였지만, 콘텐츠 제공 답변은 임시 업무 방식의 삭제 요건을 명시적으로 점검하지 않았습니다. 이는 제작자가 조건을 알고 수행한 점검이며 독립 평가나 제품 오류율이 아닙니다. 평가 대상 여섯 답변 외에 별도 일곱 번째 진단이 기록되어 있지만, 실패한 평가 답변을 교체하지 않았습니다.

### 이 자료로 말할 수 있는 범위

| 근거 | 뒷받침하는 결론 | 아직 확인하지 못한 것 |
| --- | --- | --- |
| v1.5.2 콘텐츠 제공 이메일 한 개 | 공개 출력이 명시된 약속의 범위를 지켰음 | 일반 요청 대비 개선, 반복성, 네이티브 활성화, 독립 사용 |
| 과거 파일럿의 v1.5.0 가격 답변 한 쌍 | 이 콘텐츠 제공 답변의 판매량 기준은 틀렸고, 이 일반 답변은 맞았음 | 실패 빈도, 인과 기제, 재현되는 회귀, 현재 버전의 행동 |
| 현재 v1.5.2 문서 | 전달 프로필과 근거의 경계를 문서화함 | 보편적 답변 품질, 매 턴 사용, 비용·지연 개선 |

사례에서 가져갈 것은 점검할 수 있는 행동입니다. 이메일의 약속을 합의한 사실에 연결하고, 행동을 좌우하는 수치는 다시 계산합니다. 어느 기록도 현재 제품의 일반 효능을 추정하지 않습니다. 과거 실패가 v1.5.2에도 남아 있다는 증거는 없으며, 새 이메일이 그 실패를 고쳤다는 증거도 없습니다. 설치·콘텐츠 전달·읽기·적용·유용성은 서로 다른 주장입니다. [영어][release-en]·[한국어][release-ko] 배포 문서도 이 구분을 유지합니다.

## Sources and editorial record / 출처와 편집 기록

- Source bodies reviewed on 15 October 2026 UTC. This draft adds **zero model calls** and does not publish or modify the original records. / 2026년 10월 15일 UTC에 본문을 읽었습니다. 이 초안 작성에서 **새 모델 호출은 0회**이며 원래 공개 기록을 게시·수정하지 않았습니다.
- The GPTers body was accessible by a public HTTP GET (200) after the web reader returned an error. The account, synthetic conditions, final email, four checks and error caveat were read from the body, not inferred from its title. No screenshot, raw host log or private conversation was retained. / 웹 읽기 오류 후 공개 HTTP GET(200)으로 GPTers 본문을 읽었습니다. 제목으로 본문을 재구성하지 않았으며 스크린샷·원시 호스트 로그·사적 대화를 보존하지 않았습니다.
- The historical pilot Gist revision read was `1eaa35e6435778f2fa2d3012e45780a2c493f106`; it contains `README.txt`, `protocol.json` and `results.txt`. It reports registration at `2026-10-13T00:56:48Z`; the Gist was created at `2026-10-13T01:01:44Z` and last updated at `2026-10-13T01:01:45Z`. / 읽은 과거 파일럿 Gist의 리비전·파일과 공개 시각입니다. 등록 시각은 프로토콜에 기록된 값입니다.
- [Issue #113][campaign] is the maker's distribution and execution record, not an independent efficacy source. [Issue #114][failure] remained open when read; mechanism and reproducibility are unconfirmed. / #113은 제작자의 배포·실행 기록으로 독립 효능 자료가 아닙니다. 읽은 시점에 #114는 열려 있었으며 기제와 재현성은 미확인입니다.
- Current repository reader guidance was read in [English][reader-en] and [Korean][reader-ko] at draft base `227a528996d93c423851db1d663f9572be534e59`. That base is distinct from both historical source identities above. Reader guidance alone is not a canonical-method application or native receipt. / 초안 기준의 영어·한국어 독자 안내를 읽었으며, 이 기준은 위 두 과거 소스와 별개입니다. 독자 안내만 읽은 것은 정본 방법 적용이나 네이티브 영수증이 아닙니다.

[email]: https://www.gpters.org/ai-writing/post/dont-turn-friday-draft-iZnzhXks0aheqhD
[email-record]: https://github.com/ParkerHwang/OpenSocrates/issues/113#issuecomment-6182771759
[held-study]: https://github.com/ParkerHwang/OpenSocrates/issues/113#issuecomment-6182379616
[pilot]: https://gist.github.com/ParkerHwang/2bc9a2fc97885965b8fa537db4d7d282/1eaa35e6435778f2fa2d3012e45780a2c493f106
[failure]: https://github.com/ParkerHwang/OpenSocrates/issues/114
[campaign]: https://github.com/ParkerHwang/OpenSocrates/issues/113
[release-en]: https://github.com/ParkerHwang/OpenSocrates/blob/9838db16910c5f22d9dcc3c7180350cb406fd236/docs/v1.5.2.md
[release-ko]: https://github.com/ParkerHwang/OpenSocrates/blob/9838db16910c5f22d9dcc3c7180350cb406fd236/docs/v1.5.2.ko.md
[reader-en]: https://github.com/ParkerHwang/OpenSocrates/blob/227a528996d93c423851db1d663f9572be534e59/plugin-src/shared/reader/guide.en.md
[reader-ko]: https://github.com/ParkerHwang/OpenSocrates/blob/227a528996d93c423851db1d663f9572be534e59/plugin-src/shared/reader/guide.ko.md
