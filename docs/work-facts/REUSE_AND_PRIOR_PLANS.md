# 기존 자산과 이전 기획 대조

기준 main `d6b8ff1dc0dc7a51ebd5896a395ac39236e77d1c`. 이 표의 코드는 현재 업무 사실 라이브러리의 구현이 아니며 재사용은 설계·보안 검토 후 결정한다.

| 기존 자산 | 현재의 확인된 역할 | 새 제품에서의 후보와 비어 있는 부분 |
| --- | --- | --- |
| [`src/opensocrates/hosts/claude/native.py`](../../src/opensocrates/hosts/claude/native.py), [`adapter.py`](../../src/opensocrates/hosts/claude/adapter.py), [`events.py`](../../src/opensocrates/hosts/claude/events.py) | Claude Code native 경계의 입력 정규화·고정 안내·이벤트 분리. 입력에서 업무 프롬프트·대화를 보관하지 않음. | 제한 입력, 안전한 경계, fail-open 패턴은 후보. **업무 사실 추출·선별·영구 저장이나 Claude 일반 대화 자동 동작을 제공하지 않는다.** |
| [`plugin-src/claude/README.md.tmpl`](../../plugin-src/claude/README.md.tmpl), [`plugin-src/claude-chat/README.md.tmpl`](../../plugin-src/claude-chat/README.md.tmpl) | native Claude Code entry와 content-only 계정 패키지의 서로 다른 배포 계약. native Stop/SessionEnd는 no-op. | 자동 저장 신호와 사용자 대화 프로필은 새로 검토. 계정용 콘텐츠의 특성을 프로젝트 전체에 일반화하지 않는다. |
| [`src/opensocrates/selector/entry.py`](../../src/opensocrates/selector/entry.py), [`src/opensocrates/hooks/dispatcher.py`](../../src/opensocrates/hooks/dispatcher.py) | bounded discovery와 임시 세션 수명 관리 | 사용 시점 선별·전달 아이디어 참고. 현재 업무 안건을 검색하거나 사실 주입을 하지 않는다. |
| [`src/opensocrates/persistence/atomic.py`](../../src/opensocrates/persistence/atomic.py), [`paths.py`](../../src/opensocrates/persistence/paths.py) | 소유·경로 제한과 원자적 파일 갱신 보조 | 저장 안전성 검토 후보. 암호화·다중 사용자 권한·비밀 데이터 보관 솔루션이 아님. |
| [`src/opensocrates/persistence/task_store.py`](../../src/opensocrates/persistence/task_store.py), [`domain/record_event.py`](../../src/opensocrates/domain/record_event.py), [`application/delete_records.py`](../../src/opensocrates/application/delete_records.py) | 닫힌 공개 판단 이벤트, 순서/동시성 및 삭제 패턴 | 계약과 원자성 패턴만 검토. 기존 `JudgmentEvent`를 업무 사실의 스키마나 기존 삭제 처리의 업무 데이터 삭제 보장으로 취급하지 않는다. |
| [`installer/managed-hosts.mjs`](../../installer/managed-hosts.mjs) | 관리되는 호스트의 소유·충돌·설치 및 롤백 경계 | 신규 구성요소의 설치·업그레이드 패턴 후보. 기존 설치에서 업무 사실 저장 자동 활성화를 뜻하지 않는다. |

현재 공개 정책과 신규 업무 사실 보관의 충돌은 [정책 제안](PRIVACY_PROPOSAL.md)에서 다룬다. 기존 Claude account·Antigravity의 content-only 배포와 Codex native/legacy 런타임, ChatGPT 대화·Claude Code를 각각 구분한다.

## 이전 2.0 준비안

[Draft PR #137](https://github.com/ParkerHwang/OpenSocrates/pull/137)의 head `10b5311b047c7d8025d96b1c13c269a8900432a0`은 문서 준비안이며 구현·출시가 아니다. 해당 안의 working memory/history, bounded retrieval, 설치·업데이트, 평가 내용은 참고할 수 있으나 사용자가 새로 정한 **작업 전 사실 전달 + 작업 후 자동 사실 기록**의 구체 계약과 동일하지 않다. 특히 48개 방법·10개 언어·여러 봇·광범위한 배포를 첫 제품 범위에 자동으로 상속하지 않는다. 어떤 문서를 유지·수정·대체할지 후속으로 결정한다. 이 패키지는 기존 PR을 변경·닫거나 그 결정을 대신하지 않는다.

[PR #135](https://github.com/ParkerHwang/OpenSocrates/pull/135)는 별도의 사무업무 평가 도구이다. 패키징, 오프라인 테스트, 설치나 스킬 선택을 실제 모델의 사실 선별·적용 또는 업무 개선으로 세지 않는다. [평가 계획](EVALUATION.md)은 이 새 제품의 목표에 맞는 비교 관찰을 별도로 정의한다.

저장소 계약에 따라 철회된 PR #95의 코드와 가이드는 복사·병합·체리픽하지 않는다. 이 문서 작성은 구현·실제 Claude 시험·제품 효과 평가를 수행하지 않았다.
