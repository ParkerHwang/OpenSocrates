# S088 — 채널 적격성·중복·충돌 우선순위 지도

작성 기준: **2026-10-15 05:30 UTC / 14:30 KST**. 용도는 S090의 기존 자산 식별과 S001의 중복 방지 판단이다. 이 문서는 게시·예약·계정 작업의 실행 지시나 적격성 재인증이 아니다.

배정 기준과 조회 당시 원격 `main`은 모두 `227a528996d93c423851db1d663f9572be534e59`였다. 제품 설명은 [출시된 v1.5.2](https://github.com/ParkerHwang/OpenSocrates/releases/tag/v1.5.2), 출시 소스 `9838db16910c5f22d9dcc3c7180350cb406fd236`, 콘텐츠 리비전 5를 기준으로 한다. 48개 방법·열 언어의 지시문과 기존 호스트 범위는 [영문](https://github.com/ParkerHwang/OpenSocrates/blob/v1.5.2/docs/v1.5.2.md)·[한국어 출시 문서](https://github.com/ParkerHwang/OpenSocrates/blob/v1.5.2/docs/v1.5.2.ko.md)에 따른다. v1.6·Windows ARM64나 main의 변경을 출시 기능으로 소개하지 않는다.

## 적용 범위와 판정값

- 이번 작업은 공개 GitHub 읽기와 기존 로컬 운영 자산의 제한적 읽기만 수행했다. 소셜 계정·피드·알림·브라우저·게시자 포털은 열지 않았다. 플랫폼 규칙은 #113의 날짜 있는 기록을 승계하며, 이번에 각 사이트의 현행 정책을 다시 확인했다고 주장하지 않는다.
- `보존/조건부 유지`는 기존 글에서 실제 새 요청이나 필요한 사실 정정을 처리할 수 있는 후보라는 뜻이다. 매 실행의 현행 규칙·계정·정확한 대화 맥락 확인은 별도다. **이번 표에서 무조건 `eligible`인 채널은 없다.**
- `hold`는 해당 자동 작업·권한·계정 관문이 해소되지 않았다는 뜻이다. 모든 AI 글·사람의 수동 이용·플랫폼 전체를 금지한다는 뜻으로 넓히지 않는다.
- `owner final click`은 기존 원고와 예약을 보존하는 경계다. 이 작업은 새 composer, 재예약, 최종 전송, 신규 가입, 새 자동화, 비용 집행을 하지 않는다. 예약 원장은 S001 소유이며 아래 식별자는 읽기용 별칭이다.

## 우선순위

| 순서 | 할 일 | 실행을 바꾸는 근거 | 하지 않을 일 |
| --- | --- | --- | --- |
| 1 | 실제 새 독자·편집자 요청을 **원래 대화**에서 응대하도록 준비 | 새 질문의 permalink와 전체 관련 맥락, 허용된 접근 경로. Reddit F001/F002·기존 큐레이션 PR·중국 편집 제안·izanami·Q&A의 새 응답이 해당한다. | 새 요청이 확인되지 않았는데 답변을 만들거나 완료된 인사에 반복 답장하지 않는다. |
| 2 | 이미 공개된 글·제안·설정 안내와 owner 예약 자산을 보존 | 정확한 공개 URL, 버전, 기존 파일·해시, 실제 변경 요청. 최신 공개 확인은 오래된 pending 표시를 대체한다. | 재소개, removed 글 재게시, 두 번째 moderator 요청, curator bump, 같은 파일 덮어쓰기·새 큐를 만들지 않는다. |
| 3 | 앞의 작업을 처리한 뒤 검증된 적격 기회만 검토 | 해당 채널의 현재 전체 규칙·정상 계정 권한·관련 사례·중복 범위·한 가지 구체적 독자 과제. | 채널 수 확대 자체를 성과로 삼거나 미확인 채널을 적격으로 승격하지 않는다. 신규 가입·허가 우회는 실행하지 않는다. |

**현재의 실제 요청 상태:** 아래 두 큐레이션 PR은 이번 GitHub 조회에서 모두 open/unmerged, conversation comments 0, review comments 0, reviews `[]`였다. #113의 최신 독자 응대 인계는 새 미응답 질문이 보이지 않았다고 기록한다. 이것은 소셜 inbox 전체에 요청이 없다는 증거가 아니다. 질문이 없는 상태에서는 보존이 다음 행동이다.

## 핵심 채널 충돌표

행동 열은 후속 담당자의 준비 범위를 설명한다. S088은 외부 변경을 하지 않는다. 근거 번호는 아래의 공개 인계 링크다.

| 채널·언어 | 허용 준비 / 현재 hold | 기존 글·예약 자산 | 중복·충돌 경계 | 재개 조건·근거 |
| --- | --- | --- | --- | --- |
| X · **영어만**: 본문·답글·미디어 글자 포함 | 기존 영문 자산 보존. website scripting·자동 게시·AI 자동 답글은 hold. 공식 intent의 최종 Post는 owner. | `X-CSV-20261013`은 **이미 공개**. 별도 과거 owner 게시 보고는 URL 미확인. | CSV 글을 pending으로 다시 만들지 않는다. 서울 날짜와 rolling 24시간 각각 원글 ≤3, 통상 ≥6시간 간격은 상한이며 할당량이 아니다. 오래된 조회로 현재 여유를 계산하지 않는다. | CSV는 재개할 게시 작업이 없다. 별도 새 글은 실제 owner 기록·간격·기존 예약 대조 및 허용 경로가 필요. 자동화 hold는 적용 가능한 공식 허가/워크플로 근거가 있을 때만 재검토. [E1], [E5]. |
| Threads · **한국어만** | 기존 소개 보존. 새 회의 메모 팁은 owner final 게시 예약 유지. 자동 feed·알림 작업은 재개하지 않는다. | `TH-INTRO-Deb_uxREibV` 공개. `TH-MEMO-20261013T2253Z`는 발행·저장 상태 미확인. | 소개 재게시 금지. 팁이 표시된 profile에 없다는 사실은 미게시·초안 소실 확정이 아니다. 재생성·덮어쓰기 금지. | owner의 실제 permalink/처리 보고 또는 허용된 범위의 기존 자산 확인으로만 갱신. 확인 전 기존 reservation 유지. [E1], [E4]. |
| Reddit r/claudeskills · 영어 | F001 평가 질문·F002 feature 제안의 **실제 새 맥락** 우선. 개인 계정 scripted 로그인·조작은 hold. | [기존 소개](https://www.reddit.com/r/claudeskills/comments/1x43pc9/opensocrates_a_free_claude_skill_for_checking_the/), [F001 기존 답변](https://www.reddit.com/r/claudeskills/comments/1x43pc9/comment/pge84xw/), [F002 acknowledgment](https://www.reddit.com/r/claudeskills/comments/1x43pc9/comment/pge4ufu/). | 이미 한 평가 답변·feature 수락을 반복하지 않는다. GuideThread 수락/감사는 공개 feature·독립 추천·사용을 뜻하지 않는다. | 허용된 경로로 새 질문과 전체 관련 문맥 확보. 개인 계정 자동화를 위한 적격 workflow 근거 없이는 자동 조작 재개 불가. [E3], [E6]. |
| Reddit r/SideProject · 영어 | 기존 removed 상태와 한 번 보낸 moderator 요청 보존. | [기존 filtered 글](https://www.reddit.com/r/SideProject/comments/1x438j0/i_built_a_free_claudecodex_plugin_for_asking_what/). | removed 글 재게시·두 번째 moderator 요청·대체 계정 금지. | 실제 moderator 결과와 허용 경로가 생길 때만 기존 항목 갱신. [E3], [E14]. |
| Reddit r/ClaudeAI·r/opensource, 후순위 r/ClaudeCode·r/PromptEngineering · 영어 | 내부 brief만 존재. 각 community 전체 규칙·계정·중복이 미확인이고 개인 계정 자동화 hold도 공통 적용. | 새 공개 글 없음이 마지막 기록이며 이번에 조회하지 않음. | 기존 claudeskills 소개 번역·복제나 새 app/account로 hold를 우회하지 않는다. | 실제 독자 과제와 채널별 전제 확인 전 `unverified`; 신규 가입 제안·실행 없음. [E3], #113 현재 본문. |
| LinkedIn · 영어 | 자동 account access·작성·공유 hold. 기존 원고는 owner가 직접 수동 게시. | [초기 공개 소개](https://www.linkedin.com/feed/update/urn:li:activity:7515412587652526080/)와 별도 `LI-EMAIL-20261015` 미게시 원고. | 초기 소개를 새 원고와 혼동하지 않는다. 14일 원고와 15일 worksheet 링크 추가본은 **동일 계보**이며 둘 다 새 예약하지 않는다. | owner가 현재 원고를 수동 게시한 뒤 실제 URL 제공. 허가 없는 account 자동화는 별도 hold 유지. [E2], [E6], [E14]. |
| Product Hunt · 영어 | 기존 launch 보존. 댓글·Maker reply는 **owner가 직접 작성**; 생성 초안도 만들지 않는다. | [단일 제품/launch](https://www.producthunt.com/products/opensocrates?launch=opensocrates). 14일 live/Launching today가 인계에 기록됨. | 오래된 Scheduled 상태를 신규 launch 과제로 쓰지 않는다. 새 launch·동일 listing·generated comments 금지. 홈페이지 feature/노출은 미확인. | 실제 reader 질문은 owner의 직접 참여로 연결. 등록 사실과 댓글 규칙은 별도. [E4], [E6], [E7]. |
| Anthropic Skills Show and tell · 영어 | 기존 showcase 보존·새 질문이 있을 때 맥락별 준비. | [#2023](https://github.com/anthropics/skills/discussions/2023), 15일 worksheet 링크 보완 완료. | 회의 이메일 사례·worksheet를 새 소개로 복제하지 않는다. | 실제 새 질문 또는 필요한 사실 정정. [E2], [E8]. |
| Anthropic Skills Q&A · 영어 | 실제 usage 질문의 응답 준비. 제품 버그/사용 보고로 재분류하지 않는다. | [#1987](https://github.com/anthropics/skills/discussions/1987), [기존 답글](https://github.com/anthropics/skills/discussions/1987#discussioncomment-18926639). | 앱 확인·가상 사례 요청을 반복하지 않는다. 무관한 제품 링크·star 요청 없음. | 독자가 자발적으로 앱/예시를 추가한 새 맥락. 15일 인계에서는 새 요청이 보이지 않았음. [E2], [E9]. |
| Claude skills curated PR · 영어 | 동일 제안 유지, 실제 maintainer 요청 우선. | [#912](https://github.com/BehiSecc/awesome-claude-skills/pull/912), head `9246a5c5974e0dd3420cb13c6077cf7cdac7d5d6`. | 새 PR·bump 금지. README 한 줄과 14일 v1.5.2 본문 appendix는 이미 반영됨. | 실제 요청·구체적 정정 사항 또는 PR 상태 변경. 현재 open/unmerged, 댓글/리뷰 없음. 수락된 curation 아님. [P1]. |
| Codex CLI curated PR · 영어 | 동일 제안 유지, 실제 maintainer 요청 우선. | [#415](https://github.com/RoggeOhta/awesome-codex-cli/pull/415), head `62efb59da75b34289d56a6c05f11a6953dad93ea`. | 새 PR·bump 금지. 기존 Plugins 항목·badge·v1.5.2 appendix 보존. | 실제 요청·구체적 정정 사항 또는 PR 상태 변경. 현재 open/unmerged, 댓글/리뷰 없음. 설치·승인·적용 증거 아님. [P2]. |
| GPTers · 한국어 | 두 서로 다른 기존 사례의 실제 질문 우선. | [이전 수치 pilot 사례](https://www.gpters.org/chatbot/post/hwalseonghwayuli-15-eseo-21-ro-olrassneunde-baro-culsihaedo-doelggayo-0V61H1kBI4ZOb3y), [15일 업무 이메일 사례](https://www.gpters.org/ai-writing/post/dont-turn-friday-draft-iZnzhXks0aheqhD). | 이메일 글은 이미 공개. 두 사례의 실험·버전 정체성을 합치지 않는다. 최신 글의 세 URL은 copyable plain text; clickable anchors로 주장하지 않는다. | 실제 새 질문/필요한 정정. 변하지 않은 hyperlink 형식 재시도나 새 복제 글은 하지 않는다. [E1], #113 현재 본문. |
| Disquiet · 한국어 | 기존 제출 보존. | [기존 제품 제출](https://disquiet.io/products/opensocrates); 마지막 native 기록은 pending approval. | pending을 승인·directory 노출로 바꾸지 않는다. 재제출 금지. | 실제 심사 결과·편집 요청. 이번에 계정 상태 재확인 없음. [E10], [E14]. |
| OKKY · 한국어 | 자동 게시/내용 변경에 동의 필요하다는 기록으로 hold. | 한 번의 기존 허가 문의; 게시/가입 완료 근거 없음. | 재문의·동의 추정·대체 경로 금지. 개인정보나 문의 원문을 표에 복사하지 않는다. | 실제 운영자 응답과 그 조건. 마지막 기록은 outgoing 문의만 확인. [E10], [E11]. |
| Qiita · 일본어 | 두 기존 기술 글·실제 질문 우선. | [언어/설정 글](https://qiita.com/parkerhwang/items/3bcb34bf30e51f9a657d), [account ZIP와 native 차이 글](https://qiita.com/parkerhwang/items/882693a190fafcd85c5a). | packaging 글은 이미 공개. 내부 lifecycle/라우팅 brief를 완성된 새 글로 취급하지 않는다. | 새 질문 또는 새 주제의 현행 규칙·태그·중복·원천 근거가 모두 확보될 때 조건부 검토. 조회수/외부 daily list는 사용/추천 아님. [E6], #113 현재 본문. |
| izanami · 일본어 | 기존 소개·TSUTSU의 실제 후속 질문 우선. | [기존 제품](https://izanami.dev/post/6d7ae738-3151-48f9-87b2-dba9a48ef2de), [review #578](https://izanami.dev/post/6d7ae738-3151-48f9-87b2-dba9a48ef2de#578), [기존 답글 #587](https://izanami.dev/post/6d7ae738-3151-48f9-87b2-dba9a48ef2de#587). | 관심/개념 평가는 첫 사용·독립 추천 아님. 기존 이메일 과제 답글 반복 금지. | 실제 새 질문. 15일 인계는 새 요청이 보이지 않았다고 기록. [E2], [E10]. |
| ruanyf weekly·HelloGitHub · 간체 중국어 | 기존 편집 제안 유지·실제 편집 요청 우선. | [weekly #12309](https://github.com/ruanyf/weekly/issues/12309), [HelloGitHub #3948](https://github.com/521xueweihan/HelloGitHub/issues/3948). | 원 v1.5.1과 날짜 있는 v1.5.2 appendix 보존. 새 nomination·comment bump 금지. | 실제 편집 결과/요청. pending은 선정·추천 아님. [E12], #113 현재 본문. |
| Diolinux Plus · 포르투갈어 | 실제 기존 own-project 질문 우선. | [단일 topic #84673](https://plus.diolinux.com.br/t/opensocrates-comparar-opcoes-e-conferir-fontes-com-instrucoes-em-portugues/84673). | 새 소개·번역 crosspost 금지. native Linux 지원을 암시하지 않는다. | 새 질문과 허용 맥락. 마지막 무응답 관찰을 현재 전체 inbox 상태로 확대하지 않는다. #113 현재 본문, [E6]. |
| DevHunt · 영어 | 기존 페이지 보존, 공개 정확성 유지. | [기존 tool page](https://devhunt.org/tool/opensocrates). 생성 Fact sheet는 숨김 처리됐다는 기록. | 새 listing·동일 소개 금지. 저장된 generated claims를 수정 완료로 주장하지 않는다. 별도 weekly 날짜 2030-11-19는 과거 기록이며 새 발행 예약 아님. | 실제 질문·지원되는 사실 정정 필요. 숨긴 Fact sheet의 공개 노출 해소와 생성 동작 수정은 별개. [E4], [E10]. |

## 제외·미확인·접근 관문

| 채널·언어 | 상태와 보존 자산 | 현재 재개 조건 / 중복 경계 | 근거 |
| --- | --- | --- | --- |
| HN · 영어 | 이 캠페인의 AI/자동 홍보에서 **제외**. | 구체적 적용 가능한 공식 규칙·허용 workflow 변경 없이는 제외 유지. 우회 게시·새 계정 없음. | [E14]. |
| DEV · 영어 | 자체 프로그램 홍보·AI 생성 댓글에서 **제외**. | 일부 AI 글 허용 예외를 이번 홍보/댓글의 허가로 쓰지 않는다. 기존 제한을 바꾸는 구체적 공식 근거만 재검토. | [E13]. |
| HackerNoon·Hashnode·Hugging Face forum · 영어 | 각각 자동 access, 자동 browser publication, forum 자동 access/monitoring hold. | 임의 API/MCP 우회·가입·주기적 재감사 없음. 해당 행위에 적용되는 공식 허가/workflow·실제 규칙 변경이 필요. | [E9], [E15], [E16]. |
| Google AI Developers Forum Antigravity · 영어 | 내부 source-reference 원고만 존재; account/action 경로와 충분한 중복 확인 미해결. | 카테고리 존재·공개 read 가능을 로그인/게시 허가로 바꾸지 않는다. 현행 전제 확보 전 `unverified`. | 로컬 portfolio·culture card; 공개 category는 https://discuss.ai.google.dev/c/antigravity/64 . 이번 native 확인 없음. |
| GeekNews·Dotnetdev·SkillJam · 한국어 | GeekNews 로그인/새 계정 1주 링크 관문, Dotnetdev TL2 topic/TL1 reply 관문, SkillJam 전체 규칙/권한 미확인. | 정상 기존 계정·게시 권한·완전한 규칙·중복 증거만으로 재검토. 가입·참여 제조·우회 없음. | #113 현재 본문; 마지막 두 채널의 현행 상태는 미확인. |
| V2EX·OSCHINA · 간체 중국어 | 기존 원고 보존. V2EX human auth/CAPTCHA, OSCHINA 과거 Gitee 500 및 form/example 확인 미완료. | 실제 정상 인증/서비스 복구 후 정확한 기존 계보에서 전제 확인. 반복 callback·새 계정·중복 원고 없음. | #113 현재 본문, [E5]. |
| Zenn · 일본어 | 기존 autonomous promotion 범위에서 제외. | scraps로 재분류하거나 가입해 우회하지 않는다. 실제 적용 가능한 규칙 변경이 있을 때만 재검토. | #113 현재 본문. |
| ForumIA·Zeste de Savoir·LinuxFr · 프랑스어 | ForumIA terms 미확인, Zeste는 홍보만을 위한 가입 금지 기록, LinuxFr는 광고/중복/사소한 버전 공지 제한 및 계정·AI workflow 미확인. | 실제 적격 community 맥락·독자 질문 및 각 미해결 전제 필요. 참여를 제조하거나 같은 gate를 반복 감사하지 않는다. | #113 현재 본문; 로컬 portfolio/culture cards. |
| PromptPlay·Entwickler-Ecke · 독일어 | 작은 reserve/부분 확인. PromptPlay 10명 표시는 대표 청중 규모 아님; 대표 사례/중복 미완료. Entwickler의 전역 AI/account·제품 범위 미해결. | 실제 관련 독자 맥락과 누락된 전제 확인 전 `unverified`. 계정 생성·게시 없음. | #113 현재 본문; 로컬 portfolio/culture cards. |
| iProgrammatori·HTML.it·IAI portal/ForumFree·Inforge · 이탈리아어 | 각 missing/security block/403·서비스 종료·작은 reserve 등 부분 조사. | 접근 방해 우회·반복 실패 감사·대규모 reach 주장 없음. 현재 규칙과 해당 경로가 미확인인 채널은 `unverified`. | #113 현재 본문; 로컬 portfolio. |
| Foro IA·Foros del Web·elhacker.net · 스페인어 | Foro IA 기존 등록 handoff는 owner password/hCaptcha 관문; 나머지는 적절한 board/전역 규칙 불완전. | Foro IA는 실제 계정 완료 보고 후 account·맥락·전역 중복 확인 필요. 등록·게이트 재요청·번역 재게시 없음. | #113 현재 본문; [E6]의 기존 no_action 조정 기록. |
| Blognone · 태국어 | 기존 등록 admin approval 대기와 내부 Thai Press Release 보존. | 실제 approval이 생기면 기존 계정·form·native duplicate 확인. 새 등록·반복 알림·무관한 comment 홍보 없음. | [E17], 로컬 portfolio/culture card. |
| OpenAI directory · 기존 영문 metadata | **기존** `1.5.1-preview.2` draft. 마지막 접근은 인증 무효화; Terms/scan/editor/intake/현재 공개 상태 미확인. | owner 정상 로그인 완료 후 **같은 draft/version** 상태만 재확인. 로그인 자체가 제출 허가가 아니며 중복 upload·publisher verification 재요청 없음. v1.5.2 공개 제품과 이 draft 버전을 합치지 않는다. | [E18]. |
| Claude archive marketplace·기타 agent catalog | 내부 archive candidate; managed ownership #121 미해결. 기존 GitHub/npm·계정 ZIP 경로 보존. | [#121](https://github.com/ParkerHwang/OpenSocrates/issues/121)의 소유권/disabled/coexistence/update/remove/rollback 범위 해결 전 새 public install 안내 없음. | [E19]. |
| Indie Hackers·ProductShip·OpenAlternative·travisvn list·Hashgraph catalog | 기존 posting gate/반복 제출 오류/제품 유형 또는 기여 요건 불일치로 미게시·제외. | 실제 전제 변경만 검토. 기존 오류 반복, 제품 구조 변경을 통한 listing 우회, 새 계정·중복 제출 없음. | [E14], [E20]. |

## S090이 사용할 자산 식별자

아래 `S088/...`는 **문서 내 조회 별칭**이며 전역 reservation ID나 새 queue item이 아니다. `기존 ID/파일`과 공개 URL을 함께 대조한다. 로컬 경로의 공통 루트 `O`는 비기계별 표기 `<maintainer-local-outreach-root>`다. 파일 내용은 복제하지 않았고 기존 자산은 수정하지 않았다.

| 조회 별칭 | 기존 ID/파일 또는 공개 ID | 확정/미확정 상태 | S090 처리와 공개 근거 |
| --- | --- | --- | --- |
| `S088/X-CSV-20261013` | `2026-10-13T2055Z-x-task-example`; `O/operating-system/cycles/2026-10-13T2055Z-x-task-example/reviewed-final.en.txt` | 2026-10-13 22:57:21Z / 14일 07:57:21 KST 게시; 15일 01:52:33Z 관찰이라는 최신 기록. | `DO_NOT_REQUEUE_PUBLISHED`. [실제 글](https://x.com/ParkerHwang/status/2110142877187871110), [E1]. |
| `S088/X-PRIOR-OWNER-REPORT` | `O/operating-system/human-publish/x-owner-reported-prior-2026-10-13.json` | 별도 13일 13:29:50Z owner 게시 보고. permalink null. | `PRESERVE_REPORTED_UNKNOWN_URL`. CSV와 합치거나 미게시로 되돌리지 않는다. [E4]. |
| `S088/TH-INTRO-Deb_uxREibV` | `Deb_uxREibV`; `O/operating-system/human-publish/threads-owner-published-2026-10-13.json` | owner가 편집·게시한 소개; 15일 01:54:01Z profile 확인 기록으로 재확인. | `DO_NOT_REQUEUE_PUBLISHED`. [기존 글](https://www.threads.com/@theparkerhwang/post/Deb_uxREibV), [E1], [E4]. |
| `S088/TH-MEMO-20261013T2253Z` | `2026-10-13T2253Z-threads-meeting-note`; `O/operating-system/cycles/2026-10-13T2253Z-threads-meeting-note/approved-body.ko.txt` | `pending_human_item=true`; 게시와 saved draft는 미확인. 최신 관찰은 표시된 profile에 팁이 보이지 않았다는 범위뿐. | `KEEP_EXISTING_OWNER_RESERVATION`. 새 composer/교체/재예약 없음. [E1], [#113 본문](https://github.com/ParkerHwang/OpenSocrates/issues/113). |
| `S088/LI-EMAIL-20261015` | `O/operating-system/cycles/2026-10-15-immediate-execution/linkedin-owner-ready.en.txt`; 이전 계보 `2026-10-14T1124Z-promotion-plan-execution/materials/linkedin-human-post.en.txt` | 기존 영문 meeting-email 원고에 public worksheet 링크 추가; 미게시·미staging. | `OWNER_MANUAL_ONLY_SAME_LINEAGE`. 같은 원고의 두 버전을 별도 slot에 넣지 않는다. [E2], [E6]. |
| `S088/FIRST-USE-WORKSHEET` | Gist `d814da73fb445f7123eb5d637e912cd5` | 영어/한국어 자료는 이미 공개. 공개 synthetic 연습이며 비교실험/사용 성과 아님. | `REUSE_LINK_NO_NEW_GIST`. [공개 자료](https://gist.github.com/ParkerHwang/d814da73fb445f7123eb5d637e912cd5), [E6]. |
| `S088/CLAUDE-SHOWCASE-2023` | `anthropics/skills#2023` | 단일 소개 공개, worksheet 보완 완료. | `PRESERVE_EXISTING_THREAD`. [showcase](https://github.com/anthropics/skills/discussions/2023), [E2], [E8]. |
| `S088/PH-OPENSOCRATES` | 제품 slug `opensocrates`; launch query `opensocrates` | 기존 launch의 live 기록. 이번 상태 재확인 없음. | `NO_SECOND_LAUNCH_OWNER_COMMENTS_ONLY`. [기존 launch](https://www.producthunt.com/products/opensocrates?launch=opensocrates), [E4], [E6], [E8]. |
| `S088/CLAUDE-PR912` | PR #912, head `9246a5c5974e0dd3420cb13c6077cf7cdac7d5d6` | open/unmerged, 댓글/리뷰 없음. | `EXISTING_PROPOSAL_ONLY`. [P1]. |
| `S088/CODEX-PR415` | PR #415, head `62efb59da75b34289d56a6c05f11a6953dad93ea` | open/unmerged, 댓글/리뷰 없음. | `EXISTING_PROPOSAL_ONLY`. [P2]. |
| `S088/OPENAI-DRAFT-PREVIEW2` | 기존 package version `1.5.1-preview.2`; local handoff ID `openai-reauth-2026-10-14T1336Z` | 과거 draft/upload는 존재, 현재 인증·검사·접수 상태 unknown. | `SAME_DRAFT_NO_UPLOAD`. 로그인/게시자 내부 URL·인증 관련 내용은 여기 복사하지 않는다. [E18]. |

기존 본문 파일의 이번 읽기에서 얻은 SHA-256: X reviewed final `1c6d9f9718893fa3a3d8ec7d6ef90e8caabbe6e6dc3c0a3d269b18fd24c1df6b`; Threads memo `81224555c0bbb9c2fc703741bb8317b83797c3507a5a3471c055c0b6441deb1e`; LinkedIn 최신 원고 `5cfd257d2f0abe5b8fd2ecbdaf3201838fd84c2c54a138427a1481e26e0a89e7`이다. 해시는 로컬 기존 파일을 식별할 뿐, 현재 composer·공개 글과 byte 일치 또는 게시 권한을 증명하지 않는다.

### 오래된 상태와 충돌할 때

1. #113 [최신 공개 확인 E1][E1]의 정확한 자산·URL·시각을 우선한다. CSV는 공개 확인됨, Threads 소개는 공개 확인됨, memo tip은 미확인이다.
2. `O/operating-system/human-publish/ready-posts.json`은 15일 02:10:28Z에 갱신됐으며 `x_status.state=published_render_verified`, `x_status.pending_human_item=false`를 가진다. 그런데 공통 `published:false`와 과거 nested 설명도 남아 있다. 공통 boolean 하나로 모든 채널을 pending 처리하지 않는다.
3. 과거 `x-threads-focus.json`, 14일 `social-queue-status.json`, 원 `human-composer-receipt.json`의 `awaiting_human_click`은 역사적 준비 근거다. 최신 CSV 공개 확인을 덮어쓰지 않는다. Threads memo의 reservation은 여전히 보존한다.
4. 원고·소개·단순 관심·실제 사용을 별도 사건으로 유지한다. 새 URL/owner 보고가 없으면 unknown은 unknown으로 남긴다. S090은 이 지도와 기존 식별자를 S001 원장에 대조하도록 제안하며, S088은 원장을 쓰지 않는다.

## 공개 근거와 읽기 경계

다음은 이번에 공개 GitHub API로 읽은 기록이다. **인계 작성자의 과거 native 관찰**과 **이번의 GitHub 기록 조회**를 구분한다. 로컬 portfolio·culture cards는 이전 조사 요약이며 독립 정책 검증이 아니다. 다른 플랫폼의 현재 상태는 이번에 관찰하지 않았다.

- [#113 현재 본문](https://github.com/ParkerHwang/OpenSocrates/issues/113): 기존 채널·지역별 제약과 제품 설명 기준.
- [E1 — 15일 공개 GPTers 사례 및 X/Threads 정정](https://github.com/ParkerHwang/OpenSocrates/issues/113#issuecomment-6182771759): 2026-10-15 02:08:10Z 작성. X/Threads native 관찰은 각각 01:52:33Z·01:54:01Z, GPTers 마지막 관찰은 02:03:52Z.
- [E2 — 15일 즉시 실행 인계](https://github.com/ParkerHwang/OpenSocrates/issues/113#issuecomment-6182379616): 01:36:56Z 작성. showcase·Q&A·izanami·LinkedIn 원고 및 예약 보존.
- [E3 — Reddit 개인계정 자동화 hold와 F001 구분](https://github.com/ParkerHwang/OpenSocrates/issues/113#issuecomment-6139776901).
- [E4 — 기존 Threads 공개 정정·DevHunt Fact sheet 숨김·Product Hunt 단일 예약](https://github.com/ParkerHwang/OpenSocrates/issues/113#issuecomment-6147787737): 작성 13일 14:24:46Z, 갱신 17:09:24Z. 이후 live 상태는 E6/E8이 대체.
- [E5 — X hold·OSCHINA 관문](https://github.com/ParkerHwang/OpenSocrates/issues/113#issuecomment-6139607865).
- [E6 — 14일 계획 실행·worksheet·소셜 경계](https://github.com/ParkerHwang/OpenSocrates/issues/113#issuecomment-6167547384).
- [E7 — Product Hunt 댓글 규칙 구분](https://github.com/ParkerHwang/OpenSocrates/issues/113#issuecomment-6139420523).
- [E8 — 단일 Claude showcase 공개](https://github.com/ParkerHwang/OpenSocrates/issues/113#issuecomment-6169073809).
- [E9 — Q&A 답글·HackerNoon hold](https://github.com/ParkerHwang/OpenSocrates/issues/113#issuecomment-6171574512).
- [E10 — izanami 실제 답글·Disquiet/OKKY 관찰](https://github.com/ParkerHwang/OpenSocrates/issues/113#issuecomment-6168100380).
- [E11 — OKKY 단일 허가 문의](https://github.com/ParkerHwang/OpenSocrates/issues/113#issuecomment-6138356442).
- [E12 — 기존 중국 weekly appendix 보완](https://github.com/ParkerHwang/OpenSocrates/issues/113#issuecomment-6169473477).
- [E13 — DEV의 제한된 행위별 제외](https://github.com/ParkerHwang/OpenSocrates/issues/113#issuecomment-6174090202).
- [E14 — 최초 배포·removed/제외/권한 관문](https://github.com/ParkerHwang/OpenSocrates/issues/113#issuecomment-6126829091).
- [E15 — Hashnode 자동 browser publication hold](https://github.com/ParkerHwang/OpenSocrates/issues/113#issuecomment-6172993649).
- [E16 — Hugging Face forum 자동 access/monitoring hold](https://github.com/ParkerHwang/OpenSocrates/issues/113#issuecomment-6175406026).
- [E17 — 기존 채널 유지·Blognone 승인 관문](https://github.com/ParkerHwang/OpenSocrates/issues/113#issuecomment-6145286172).
- [E18 — 기존 OpenAI draft 인증·Terms/intake 구분](https://github.com/ParkerHwang/OpenSocrates/issues/113#issuecomment-6170094056).
- [E19 — archive catalog 소유권 선행 범위](https://github.com/ParkerHwang/OpenSocrates/issues/113#issuecomment-6143458460).
- [E20 — OpenAlternative 제출 요건 불일치](https://github.com/ParkerHwang/OpenSocrates/issues/113#issuecomment-6143277357).
- [E21 — F001 기존 답변·F002 수락 후 acknowledgment](https://github.com/ParkerHwang/OpenSocrates/issues/113#issuecomment-6136149001). Threads memo의 준비·미확인 상태는 #113 현재 본문과 E1을 사용한다.
- [P1 — Claude PR #912](https://github.com/BehiSecc/awesome-claude-skills/pull/912), [P2 — Codex PR #415](https://github.com/RoggeOhta/awesome-codex-cli/pull/415): 이번 API 조회에서 위 head와 open/unmerged·댓글/리뷰 없는 상태를 직접 확인. 각 PR body의 원 v1.5.0 설명과 v1.5.2 appendix는 함께 보존돼 있다.

## 미확인 사항과 다음 인계

S090은 `S088/...` 별칭을 기존 자산 ID·공개 URL에 연결해 **새 자산 생성 없이** S001에게 중복 경계와 미확인 상태를 넘길 수 있다. 공개 확인된 CSV/Threads 소개/GPTers 이메일/showcase/worksheet는 재발행 대상으로 넣지 않는다. Threads memo는 기존 owner reservation, LinkedIn 원고는 동일 계보의 owner 수동 게시 후보다. 즉시 응대할 새 질문을 확인한 채널이 없다고 해서 새 소개를 강제하지 않는다.

현재 social notifications, 실제 saved draft/composer, 현재 Product Hunt/Disquiet/OpenAI 포털 상태, 공개 자료의 현재 독자 반응은 확인하지 않았다. 적격 workflow와 실제 새 맥락이 생기면 그 행만 갱신한다. 전 채널 재감사나 변하지 않은 로그인/승인 알림은 필요하지 않다.

제작자 synthetic 사례, 직접 reader guidance를 제공한 답변, 관심 표명, 노출·다운로드·stars, 실제 첫 사용·반복 사용·독립 추천을 서로 바꾸지 않는다. 이 작업은 모델 호출·효과 실험·설치·활성화·신규 계정·게시·예약·원장 변경을 수행하지 않았다. 제품 코드 변경은 `NO_CHANGE`이며 문서 한 파일만 통합 후보로 제공한다. 최종 후보 검사·원격 공개 인계는 통합 책임자의 동결/권한 절차에 남겨 둔다.

[E1]: https://github.com/ParkerHwang/OpenSocrates/issues/113#issuecomment-6182771759
[E2]: https://github.com/ParkerHwang/OpenSocrates/issues/113#issuecomment-6182379616
[E3]: https://github.com/ParkerHwang/OpenSocrates/issues/113#issuecomment-6139776901
[E4]: https://github.com/ParkerHwang/OpenSocrates/issues/113#issuecomment-6147787737
[E5]: https://github.com/ParkerHwang/OpenSocrates/issues/113#issuecomment-6139607865
[E6]: https://github.com/ParkerHwang/OpenSocrates/issues/113#issuecomment-6167547384
[E7]: https://github.com/ParkerHwang/OpenSocrates/issues/113#issuecomment-6139420523
[E8]: https://github.com/ParkerHwang/OpenSocrates/issues/113#issuecomment-6169073809
[E9]: https://github.com/ParkerHwang/OpenSocrates/issues/113#issuecomment-6171574512
[E10]: https://github.com/ParkerHwang/OpenSocrates/issues/113#issuecomment-6168100380
[E11]: https://github.com/ParkerHwang/OpenSocrates/issues/113#issuecomment-6138356442
[E12]: https://github.com/ParkerHwang/OpenSocrates/issues/113#issuecomment-6169473477
[E13]: https://github.com/ParkerHwang/OpenSocrates/issues/113#issuecomment-6174090202
[E14]: https://github.com/ParkerHwang/OpenSocrates/issues/113#issuecomment-6126829091
[E15]: https://github.com/ParkerHwang/OpenSocrates/issues/113#issuecomment-6172993649
[E16]: https://github.com/ParkerHwang/OpenSocrates/issues/113#issuecomment-6175406026
[E17]: https://github.com/ParkerHwang/OpenSocrates/issues/113#issuecomment-6145286172
[E18]: https://github.com/ParkerHwang/OpenSocrates/issues/113#issuecomment-6170094056
[E19]: https://github.com/ParkerHwang/OpenSocrates/issues/113#issuecomment-6143458460
[E20]: https://github.com/ParkerHwang/OpenSocrates/issues/113#issuecomment-6143277357
[E21]: https://github.com/ParkerHwang/OpenSocrates/issues/113#issuecomment-6136149001
[P1]: https://github.com/BehiSecc/awesome-claude-skills/pull/912
[P2]: https://github.com/RoggeOhta/awesome-codex-cli/pull/415
