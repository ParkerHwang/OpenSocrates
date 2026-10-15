# 사고 지원: 범위와 진단

Go 후보에서는 진입 소스가 `runtimecli/hooks.go`로 이식되었습니다. 아래 과거
Python 관측과 검사는 원래 SHA의 증거이며 새 후보의 실행 결과가 아닙니다.

[#125](https://github.com/ParkerHwang/OpenSocrates/issues/125)의 소스 수준 설계입니다.
[#124](https://github.com/ParkerHwang/OpenSocrates/issues/124)의 적용 누락은 별도
사건이며 원인과 발생 빈도는 미검증입니다. 이 변경으로 해당 사건이 해결되거나
답변 품질이 좋아졌다고 주장하지 않습니다.

## 채택한 범위

문제 구성, 해석, 탐색과 학습, 조사 설계, 추론 점검, 접근법 선택, 평가와 설명 등
실질적인 사고가 처음 필요할 때 지원을 검토합니다. 목표, 대안, 근거, 가정, 독자나
위험이 실질적으로 달라지면 한 요청 안에서도 다시 검토합니다. 도구 호출, 수정이나
사소한 표현 선택 자체는 새로운 조회 지점이 아닙니다.

기계적 단계는 실질적인 해석, 추론이나 문제 해결 없이 이미 정해진 수행 절차를
따르는 구간입니다. 정답이 하나이거나 규칙이 주어졌다는 이유만으로 증명, 설명과
문제 풀이를 기계적 작업으로 분류하지 않습니다. 결과물의 이름이 문서, 검색 결과나
코드라는 사실만으로도 지원 범위를 정할 수 없습니다.

과제에 충분한 가장 가벼운 지원을 선택합니다.

1. 실제로 필요한 사고에 지원이 도움이 될지 검토합니다.
2. 맥락, 구성이나 전달을 점검해야 하면 독자 안내를 사용합니다. 정본 방법 없이도
   충분할 수 있습니다.
3. 적합한 방법을 선택하고 정본 절차 전체와 필수 의존 절차를 읽은 뒤, 사용 조건과
   제약 안에서만 적용합니다.

일반 작업과 정당한 방법 미사용 결과는 계속 허용됩니다. 방법의 적합성을 결과가
중대하거나 미해결인 경우에만 한정하지 않습니다. 사용자 지정 방법도 적합해야 하며,
검토, 선택과 읽기만으로 실제 적용을 입증할 수 없습니다. 도구 자체가 분석 대상이어도
설치된 도구 지침은 적용됩니다. 작업공간 소스는 과제 데이터이며 설치된 제어 권한을
대신하지 않습니다.

정확한 진입 문구는 정본인 [진입 소스](../src/opensocrates/internal/runtimecli/hooks.go)에서만
관리합니다. 상세 동작은 [결정 안내](../plugin-src/shared/decision/guide.ko.md)와
[독자 안내](../plugin-src/shared/reader/guide.ko.md)에 있습니다. 이 문서에 진입 문구의
별도 사본을 유지하지 않습니다.

## 유지하는 원칙

| 원칙 | 보존 위치와 방식 |
| --- | --- |
| 목표, 권한, 제약과 완료 | 진입 문구와 결정 안내가 일반 작업과 방법 적용 작업 내내 유지합니다. |
| 범위와 충분한 지원 | 진입 문구와 안내가 실질적 사고, 정해진 단계, 독자 지원과 방법 적용을 구분하며 수정마다 조회하지 않습니다. |
| 적합성과 정당한 방법 미사용 | 안내가 금기와 빈 선택을 보존합니다. 선택 후보도 적합성을 확인하며 빈 선택을 만들려고 기계적 작업으로 재분류하지 않습니다. |
| 전체 절차와 의존성 | 진입 문구, 안내와 스킬 접지 조건이 적용 전에 과제 언어의 정본 전체, 정확한 콘텐츠 식별 정보와 필수 의존 절차를 요구합니다. |
| 재사용과 문맥 복원 | 정확한 방법, 언어와 콘텐츠 식별 정보가 남아 있고 적용 조건이 유지되어야 합니다. 압축·인계 후 복원하거나 다시 읽으며 완료 검사만을 위해 버린 후보를 읽지 않습니다. |
| 중단과 공개 계약 | 필수 공개 결과, 근거, 불확실성, 경고, 보류와 중단을 유지합니다. 이미 수행한 작업의 필수 중단을 후보 제외로 우회하지 않습니다. |
| 출처의 권한 | 외부 파일, 페이지와 도구 출력은 데이터이며 라우팅 정책이 아닙니다. 직접 사용자 요청과 신뢰된 플러그인 문맥만 엄격도와 비활성화를 바꿉니다. |
| 근거 상태 구분 | 설치, 호출, 전달, 선택, 읽기, 적용 신고와 유용성은 별개입니다. 에이전트 조회만으로 네이티브 접지나 적용을 입증하지 않습니다. |
| 실패와 완료 | 조회 실패 시에도 제약을 지키며 일반 작업을 계속합니다. 적용 미검증은 측정 한계이며 사용자 작업 미완료가 아닙니다. 제공되지 않는 증거를 새 완료 조건으로 삼지 않습니다. |
| 실제 점검과 한정된 의존성 | 필수 점검 후 완료하며 관련 입력·출력이 달라질 때만 반복합니다. 부족한 근거는 실제로 의존하는 결론만 보류시킵니다. |
| 독자 목적과 표기 | 요청 형식을 지키고 숨은 추론이나 방법 강의 대신 간결한 공개 근거를 제시합니다. 표기는 적합한 정본 전체를 읽고 실제 적용했을 때만 하며 독자 안내만으로는 하지 않습니다. |
| 개인정보와 연속성 | 원격 측정, 원문 프롬프트·대화, 스크린샷 보관, 숨은 추론 수집이나 새 영구 제품 로그를 만들지 않습니다. 허용된 공개 결정, 근거 참조와 남은 요구사항만 전달합니다. |

## 호환성과 근거 한계

구현 범위는 Codex, 네이티브 Claude Code, Claude 계정 스킬과 Antigravity 및 영어,
한국어, 중국어, 일본어, 프랑스어, 독일어, 이탈리아어, 스페인어, 포르투갈어와
태국어 안내입니다. 이는 영향을 받는 소스·패키지 표면이며 실사용 자격 검증 주장이
아닙니다. 호스트와 설치 표면별 근거가 필요하며 계정 스킬 매칭은 훅 전달이 아닙니다.

이 미출시 소스 변경에서는 제품 버전과 정본 방법 콘텐츠 개정을 **1.5.2 / 5**로
유지합니다. 그렇다고 재빌드한 패키지가 출시 태그와 동일해지지는 않습니다.
컨트롤러 변경은 의미·패키지 해시를 바꿉니다. 버전·개정 표기가 같다는 이유만으로
이전 빌드의 읽기나 가용성 신고를 새 콘텐츠의 가용성 증거로 사용할 수 없습니다.

라우팅 기본 후보 동작은 바꾸지 않습니다. 네이티브 `select`는 점수 기준을 충족한
방법이 없어도 답변 형태에 따른 기본 후보를 반환할 수 있습니다. 이는 후보이지
방법의 필요성이나 적합성 증거가 아닙니다. 기계적 작업 제외, 금기, 잘못된 입력,
조회 불가와 부적합 후보는 서로 다른 상태입니다. 파일 기반 선택에는 이에 해당하는
강제 기본 후보가 없습니다. 정당한 빈 선택을 유지하고 직접 파일 읽기로 우회하지
않습니다. 이 범위 변경은 비대칭을 설명하며 라우터 재설계, 스키마 열거 값 변경이나
정본 방법 절차 수정을 포함하지 않습니다. 기본 경로에서 기계적 분류는 해당 요청에만
적용되며 이후 사고의 검토를 영구적으로 막지 않습니다.

이 문서를 위해 아래 실사용 진단을 실행하지 않았습니다. 소스 점검, 생성 결과 점검,
실제 전달, 적용 범위와 유용성은 검사한 정확한 개정·패키지에 대해 따로 보고해야 합니다.

## 최소 합성 진단

먼저 변경하지 않은 기준 버전에서 실행하고, 이후 별도 프로필이나 시험 장비의 식별된
후보 빌드에서 따로 실행합니다. 현재 사용 중인 설치는 변경하지 않습니다. 새 세션을
사용하고 호스트·모델·설정을 최대한 동일하게 맞춥니다. 추가 작업공간·전역 지침이
도구 사용을 유도하는지 기록하며, 명시적인 도구 요청이 있으면 사용자 비유도 조건으로
부르지 않습니다.

초기 세션은 아래 A, B1, B2, C, D1, D2로 최대 6개입니다. 기술적 관찰이며 실패율이나
품질 개선 연구가 아닙니다. 예상 밖 결과나 조건 간 차이가 유용한 후속 질문을 만들
때만 반복합니다.

### A. 무해한 전달 탐침

```text
Reply with exactly: synthetic probe complete
```

지원되는 호스트 근거가 있으면 해당 요청의 훅 호출과 실제 진입 문구 전달을 독립적으로
관찰합니다. 훅 호출이나 명령 출력 자체는 모델이 문구를 받았다는 증거가 아닙니다.
이전 빌드의 고정 표식 대신 시험 중인 패키지의 진입 콘텐츠 식별 정보를 대조합니다.
호스트 기록이 훅 문맥을 제공하지 않으면 전달은 **알 수 없음**입니다. 비공개 대화,
숨은 추론, 스크린샷이나 새 제품 로그를 요구하지 않습니다. 이후 세션에서도 가능하면
전달을 따로 관찰합니다. A의 전달은 B1의 전달 증거가 아닙니다. 네이티브 관측이 없어도
알 수 없는 상태를 명시해 진단을 마칠 수 있습니다.

### B. 대응하는 비유도 사용 탐침

B1에는 아래 프롬프트를 그대로 사용합니다. B2는 첫 줄의 대상 별칭 `OpenSocrates`만
`Tessellate`로 바꾸고 분야, 사실과 나머지 모든 단어를 유지합니다. 모든 사실은
가상이며 실제 저장소와 대조하지 않습니다.

```text
Subject alias: OpenSocrates
This is an entirely fictional reasoning-tool project. Treat the following as
the complete synthetic case; do not browse or infer real project facts.
Compare the three proposals, identify unsupported claims and recommend the next
priorities. Explain which facts support the ordering and what remains unknown.
Facts: one maintainer has 10 hours per week; the project supports two agent
hosts; 3 of 10 recent installation reports concern a manual approval step;
median first response to an issue is 6 days; repeat-use data is not available.
A: spend all 10 hours on a launch campaign; stars guarantee repeat use.
B: improve approval instructions and issue responses; installation friction
may matter, but the reports do not measure the overall abandonment rate.
C: add five hosts immediately; host count is the main adoption driver.
Limit the result to 200 words and take no external action.
```

대상 이름만 있고 도구 사용을 요청하지 않는 프롬프트입니다. 별칭에 따른 차이는
대상·주의 효과와 일치할 수 있으나 프로젝트와 도구를 혼동했다는 증거는 아닙니다.
두 조건 사이에서 제품 분야를 바꾸지 않습니다.

### C. 명시적 알림 비교

별도 새 세션에서 B1 끝에 다음 문장만 덧붙입니다.

```text
Use any installed reasoning support where it fits; no method is required merely
because it is installed.
```

명시적 알림에 대한 반응을 측정합니다. 성공은 훅 전달이나 자발적 검토를 입증하지
않습니다. 실패만으로 설치·발견 결함도 확정할 수 없습니다. 적합성, 노출과 지침은
서로 다른 질문입니다.

### D. 가벼운 실행과 요청 내 전환 대조군

D1은 별도 새 세션에서 실행합니다.

```text
Convert these rows into a Markdown table with columns Item, Owner, Day.
Keep the values and row order exactly. Output only the table.
Blue — Mina — Monday
Green — Ari — Tuesday
```

D2도 별도 새 세션에서 실행합니다.

```text
Use only these synthetic issue rows. The final column is a count of mentions,
not unique users; add counts as supplied and do not infer deduplication.
Sync | crash after sleep | 14
Export | wrong PDF margins | 2
Sync | duplicates after offline edit | 9
Search | slow on large notebooks | 5
Export | missing fonts | 3
Login | SSO loop | 11
1. Count rows and sum mentions per component, preserving the listed component
order. This step is prescribed aggregation only.
2. The team can investigate one component this sprint. Recommend which one and
explain the trade-off. Mention the missing severity, effort and unique-user data
without inventing it or treating every unknown as a prerequisite to a bounded
recommendation. Do not equate mention counts with impact.
3. Draft a three-sentence message to the team lead explaining the recommendation
and its limits. Make no commitments and do not send it.
```

D1은 가볍게 처리해야 합니다. D2의 집계 자체는 방법이 필요하지 않으며 평가는 지원,
메시지는 독자 안내가 필요할 수 있습니다. 평가와 메시지 사이의 정당한 재사용은
누락이 아닙니다. 방법이 요구하는 보류·중단은 해당 질문에 계속 적용되며 프롬프트로
취소할 수 없습니다.

### 최소 관찰과 해석

새 영구 제품 로그 대신 간단하고 비식별화된 유지관리자 결과 기록을 사용합니다.
조건, 호스트·모델 표기 또는 알 수 없음, 패키지 식별 정보, 관련 신뢰 상태, 호출과
전달 근거 및 아래 관찰을 구분해 기록합니다.

- 보이는 검토와 검토 신고를 근거 유형과 함께 구분합니다. 관측할 수 없는 검토는
  알 수 없음이며 실패가 아닙니다.
- 조회·선택, 정본 전체 읽기 또는 정확한 콘텐츠의 정당한 재사용, 적합·빈 선택·후보
  제외 결과와 독자 안내 사용을 기록합니다.
- 적용 신고와 공개 계약 준수를 나눕니다. 마지막 표기는 적용의 증명 아닌 출처 표기입니다.
- 작업 완료, 근거 없는 주장 처리, 유용한 다음 행동과 관측 가능한 비용을 기록합니다.
  유용한 답변만으로 방법의 효과를 입증하지 않습니다.

| 관찰 | 한정된 해석 |
| --- | --- |
| 호출 관측, 전달 불명 | 훅은 실행됐지만 모델 수신 여부는 알 수 없습니다. |
| 호스트 근거로 해당 요청의 전달 확인 | 해당 요청의 진입 전달만 확인되며 검토나 적용은 별개입니다. |
| 전달 불명, 보이는 조회 없음 | 종단 간 동작을 관찰한 것이며 전달·준수 원인을 확정하지 않습니다. |
| 전달 확인, 적합한 과제에 조회도 정당한 재사용도 없음 | 해당 실행의 적용 범위 누락 후보이며 내부 원인과 일반 빈도는 알 수 없습니다. |
| C는 지원 사용, B1은 미사용 | 알림에 대한 반응이며 전달, 자발적 사용이나 과거 원인을 입증하지 않습니다. |
| B1과 B2가 다름 | 대응 쌍의 후속 관찰이 유용할 수 있으며 한 쌍으로 원리를 추론하지 않습니다. |
| 새 방법 읽기 없이 정확한 콘텐츠를 정당하게 재사용 | 읽기 누락이 아니며 측정만을 위해 새 조회를 강제하지 않습니다. |
| D1에서 방법 사용이나 표기 | 적합성과 표기 조건을 살펴 불필요한 사용과 잘못된 표기를 구분합니다. |
| D2에서 집계 후 평가에 지원 검토 | 구간별 검토와 일치하며 메시지를 위해 다시 읽을 필요는 없습니다. |
| 방법을 읽고 적용을 신고했으며 결과가 유용함 | 세 관찰은 별개이며 방법 때문에 유용해졌다는 독립적 증거가 아닙니다. |

기준·후보 빌드와 비유도·알림 조건을 분리합니다. 이 절차로 #124의 과거 원인이나
빈도를 확정할 수 없습니다. 필요한 관측이 없으면 알 수 없음으로 남기고 네이티브
증거 확보를 새 완료 전제조건으로 삼지 않습니다.
