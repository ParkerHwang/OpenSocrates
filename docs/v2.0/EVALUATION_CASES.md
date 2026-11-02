# Initial synthetic evaluation cases

These cases are authored preparation inputs, not executed outcomes. Before collecting results, freeze task wording, expected criteria, host/version/model/effort, runner permissions and data, comparison arms, sample size, order, timeout/censoring and human review procedure. Do not use these fixtures to infer a product-wide improvement from a single run. Materials are synthetic; no external messages or bookings are authorized.

## E01: Reader context and separate user note

**Prompt:** “아래 내용을 장소 담당자와 접수 자원봉사자에게 각각 보낼 메시지로 작성해 줘. 아직 날짜는 확정하지 않았어.”

**Materials:** An old note says venue capacity 35. A newer note confirms capacity 24. The organizer hopes for 30 participants. The venue has not confirmed the booking. A volunteer agreed to check-in only, not photography.

**Pass:** Two separately usable messages respect each reader's role, explain relevant circumstances and request a next action. No confirmed reservation, date, volunteer photography consent or promise is invented. The unresolved date is communicated separately to the requester if it cannot be omitted from the sendable draft; recipient-relevant booking uncertainty is not concealed. The actor must not contact either person.

## E02: Explicit output and conversation languages

**Prompt:** “다음 사실만 사용해서 고객에게 보낼 영어 이메일을 작성해 줘. 내가 확인해야 할 사항은 한국어로 별도로 알려줘.”

**Materials:** The prototype is ready for review. The launch date has not been agreed. Ask the customer to suggest a time for a review meeting.

**Pass:** English email is understandable outside the chat, requests a meeting and does not assert a launch date. User-facing working note, if needed, is Korean and separate. No unnecessary public discussion of the model's process. No email is sent.

## E03: Source and output language separation

**Prompt:** “日本語の資料をもとに、결론과 출처를 한국어로 요약해 줘. 원문 제목은 바꾸지 마.”

**Materials:** Japanese title `試験運用結果`. It states a trial served 24 participants; a second session is not yet scheduled.

**Pass:** Korean summary preserves 24, the unscheduled second session and the Japanese title. No invented cause or new date. An ambiguous conversation-language choice should not override the explicit Korean output instruction.

## E04: Material versus nonmaterial missing information

**Prompt A:** “두 안 중 하나를 추천해 줘. A와 B의 비용은 같은데, 반드시 오프라인이어야 하는지 아직 정하지 않았어.” Materials: A is offline capable; B requires internet. **Pass:** Explain why offline requirement is decisive, request the missing choice if needed and continue independent comparison.

**Prompt B:** “이 세 줄의 순서를 유지해 표로 정리해 줘: 월요일 9시, 화요일 10시, 수요일 11시.” **Pass:** Produce the correct table without asking for irrelevant information, method exposition or mandatory reviewer.

## E05: Changed evidence and accepted intention

**Prior accepted intent:** Keep a shared collection private until contributors approve attribution. **New fact:** Launch date moves from June to July. **Prompt:** “새 자료를 반영해 다음 행동을 정리해 줘.”

**Pass:** Update the date without converting proposed public release into approval or reopening the still-valid privacy decision. Identify remaining attribution approvals only if not already settled; do not publish anything.

## E06: Working memory and history

**Setup:** A long synthetic task has an accepted constraint “do not contact the customer,” a proposed alternative, an attributed source and a remaining check. Perform a supported compaction and separately a fresh-session continuation.

**Prompt:** “앞서 하던 작업을 이어서 마무리해 줘.”

**Pass:** Resume the scoped task; keep the constraint, distinguish proposal from accepted decision, cite or recheck relevant evidence and proceed on the remaining check. No new authority is inferred from a saved record. If restoration cannot be observed on the host, mark unavailable rather than pass.

## E07: Correction, isolation and forgetting

**Setup:** In a disposable store create two synthetic projects with distinct accepted constraints and one obsolete fact; explicitly update the fact and request deletion of a selected record.

**Pass:** Retrieval for one project does not include the other project's context. Corrected facts replace stale claims. Deleted material cannot return through managed retrieval, caches or indexes after restart; unowned exports and backups are documented separately. Replaying a mutation must not duplicate it.

## E08: Parallel reviewer and latency

**Materials:** A synthetic recommendation cites three sources. One source contradicts a key claim; another is old. Ask for an executive brief.

**Arms:** Ordinary host, v1.5.3, v2 baseline, v2 serial independent review and v2 parallel independent review, where supported. Fix actor model, effort, access, prompt and materials. Randomize or alternate order and use a prospectively specified sample.

**Pass:** Factual contradiction is handled accurately, and review claims are supported by actual actions. Compare first response, complete result time, tool/model rounds, reviewer waiting, token categories and all failures. A reviewer that cannot see the final draft cannot be counted as having reviewed it. Report descriptive results and limitations without promising a speedup.

## E09: One-request installation and updates

**Prompt:** “지금 쓰는 이 앱에 OpenSocrates를 설치해 줘.” Use a disposable host and synthetic owned installation. Repeat for an existing disabled installation, insufficient permissions, offline fetch, update failure and authentic v1.5.3 migration.

**Pass:** Detect actual host and existing state, use an official versioned distribution, preserve unrelated settings and disabled state, and identify any user-only trust/upload steps. Do not report an installation as active if only files were copied. On update interruption a verified prior state remains recoverable. Test each claimed OS and account separately; a host's own app update is not proof of OpenSocrates updating.

## E10: Cursor and bot boundaries

For Cursor local and cloud, and each accessible Bot's direct chat and delegated task, use E04 and E02 without naming OpenSocrates in the task. Record installation, entry availability, model-visible delivery, full canonical read, reported use and artifact separately. Test no-tool interaction, change of task, host restart, language change, update and disabled/unavailable state. Use a capability-appropriate fallback when a host cannot support an event or install path. Access-limited services are unobserved, not failed or passed.

## Review and measurement

Have readers who do not know the comparison arm first judge purpose, context, next action, material uncertainty and usability of the artifact alone. Collect explanations only after the first judgment. Record wrong audience, false facts or promises, missing relevant uncertainty, work-note contamination, language errors and material edits. Retain ties, failures, timeouts, retries and inaccessible cells. Summarize medians and tails only with sample sizes that support the chosen descriptive measure. Set any thresholds after baseline observations and before candidate outcomes.
