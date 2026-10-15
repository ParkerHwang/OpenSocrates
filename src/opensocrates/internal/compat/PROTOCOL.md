# Opt-in legacy selector protocol

The native Go adapter targets external `codex-cli 0.144.4`, tag
`rust-v0.144.4`, commit `8c68d4c87dc54d38861f5114e920c3de2efa5876`.
It launches the host executable directly with `app-server --listen stdio://`.
It does not redistribute that executable, invoke Python, install an SDK, or
bootstrap authentication. The default decision path never starts this service.

Protocol primary references checked during implementation:

- [Current official app-server documentation](https://learn.chatgpt.com/docs/app-server)
- [Pinned initialize/initialized transport and SDK replacement](https://github.com/openai/codex/blob/8c68d4c87dc54d38861f5114e920c3de2efa5876/codex-rs/app-server/README.md)
- [Pinned experimental thread fields](https://github.com/openai/codex/blob/8c68d4c87dc54d38861f5114e920c3de2efa5876/codex-rs/app-server-protocol/src/protocol/v2/thread.rs)
- [Pinned turn/start schema](https://github.com/openai/codex/blob/8c68d4c87dc54d38861f5114e920c3de2efa5876/codex-rs/app-server-protocol/schema/typescript/v2/TurnStartParams.ts)
- [Pinned read-only sandbox and network flag](https://github.com/openai/codex/blob/8c68d4c87dc54d38861f5114e920c3de2efa5876/codex-rs/app-server-protocol/schema/typescript/v2/SandboxPolicy.ts)
- [Pinned dynamic call request](https://github.com/openai/codex/blob/8c68d4c87dc54d38861f5114e920c3de2efa5876/codex-rs/app-server-protocol/schema/typescript/v2/DynamicToolCallParams.ts)
- [Pinned dynamic call response](https://github.com/openai/codex/blob/8c68d4c87dc54d38861f5114e920c3de2efa5876/codex-rs/app-server-protocol/schema/typescript/v2/DynamicToolCallResponse.ts)

Experimental `dynamicTools` and `environments` are intentionally absent from
the filtered public TypeScript ThreadStartParams schema; their camelCase wire
fields are present in pinned Rust source. The initialize handshake requests
`experimentalApi: true`. Empty environments disable implicit environment access;
omitting them would have a different meaning. Successful selection requires
both a completed agent message and `turn.status == completed`.

Compatibility retained: medium reasoning effort, exactly three candidate fields,
known nonduplicate method IDs without an artificial count cap, transcript opt
out, eight context calls, 32 KiB chunks, 256 KiB total, 128 directory entries,
explicitly untrusted context, a disposable home/workspace, no inherited secrets,
read-only sandbox, denied approvals, no hooks/plugins/agents/shell/web, process
group cleanup, 1–30 second deadlines, canonical artifact assembly, v2/v3 artifact
headers and v2 HMAC read receipts, turn/session cleanup and 24-hour sweep.
Model-authored instructions are discarded. Existing host model metadata does
not select or override the selector model.

Intentional changes: the exact external native CLI version replaces matching
Python SDK/package versions; credentials are privately copied rather than
symlinked so a refresh cannot mutate the user's real auth file; credential
hardlinks and auth files larger than 1 MiB are rejected. Explicit activation uses `OPENSOCRATES_SELECTOR_MODE=legacy`.
`OPENSOCRATES_CODEX_BINARY` can identify the external binary by absolute path;
otherwise the host's Codex executable is discovered and checked. Set
`OPENSOCRATES_SELECTOR_TRANSCRIPT_ACCESS=off` to disable transcript-derived reads.
The legacy credential and context lane remains explicitly unavailable on
Windows; native Windows decision/install/update integrations are separate.
Unknown app-server requests receive a content-free protocol denial.
Foreign files and unsafe objects are preserved during artifact cleanup.

The Go native fixture exercises transport, version handshake, account checks,
dynamic context requests, approval denial, deadlines, cancellation and output
rejection without a network call. It is synthetic protocol evidence. Real
authenticated 0.144.4 macOS selection and host read/activation still require
separate live-probe evidence; a fixture does not establish model quality or
delivery into an existing conversation.

## Unauthenticated trust-config validation

`ValidateConfig` uses a separate configuration-validation lane. It does not
inherit the selector's exact-version requirement. It probes the installed
external CLI's `app-server --help`, selects advertised `--listen stdio://` or
legacy `--stdio`, and requires advertised `--strict-config`. Only initialize is
sent; no account, authentication, config read, thread, turn or tool RPC occurs.
An isolated private home contains only the supplied original/candidate config,
with hooks, plugins, agent fanout, analytics and all OTEL exporters disabled,
and all homes/temp directories are removed after the process tree is closed.
The actual returned `codexHome` must equal the isolated canonical home; stdin
then closes, stdout must reach EOF and the process must exit zero. Combined
version/help/server stdout and stderr are bounded at 1 MiB, each server line at
256 KiB, notifications at 128, and validation at fourteen seconds plus a
one-second process cleanup reserve. Unsafe or unknown capabilities fail closed.

This intentionally strengthens the old initialize-only check: non-strict Codex
may fall back to defaults for an invalid config and still initialize. Source
shows config loading and that fallback occur before MessageProcessor creation;
strict mode returns the error before accepting client requests. The source
check covers the retained 0.133.0 host qualification and the 0.144.4 selector
reference; runtime probing accommodates compatible installed versions without
claiming additional host qualification.

- [0.144.4 config loading before request processing](https://github.com/openai/codex/blob/8c68d4c87dc54d38861f5114e920c3de2efa5876/codex-rs/app-server/src/lib.rs#L448)
- [0.144.4 transport and strict config flags](https://github.com/openai/codex/blob/8c68d4c87dc54d38861f5114e920c3de2efa5876/codex-rs/cli/src/main.rs#L515)
- [0.133.0 host flags](https://github.com/openai/codex/blob/9474e5cfc4494b0ba319352aa86ce436c59e65c8/codex-rs/cli/src/main.rs#L435)
- [0.133.0 initialize home boundary](https://github.com/openai/codex/blob/9474e5cfc4494b0ba319352aa86ce436c59e65c8/codex-rs/app-server-protocol/schema/typescript/InitializeResponse.ts)

## 한국어

이전 선택기 경로는 사용자가 명시적으로 활성화한 경우에만 외부 네이티브
Codex 0.144.4 app-server에 연결합니다. 기본 의사결정 경로는 추가 모델 호출이나
인증을 요구하지 않습니다. Python SDK와 shim은 사용하지 않습니다.
기존 OAuth 파일은 소유권과 권한을 확인한 뒤 일회용 전용 디렉터리로 복사하며,
종료·취소·시간 제한 뒤 관련 프로세스와 임시 파일을 정리합니다.
모델이 만든 지침은 버리고 기존 EN/KO 정본에서 파일과 접지 안내를 조립합니다.
Windows의 이전 인증·POSIX 문맥 읽기 경로는 계속 미지원이며, 네이티브 Windows
의사결정·설치·업데이트 지원과 구분합니다. 합성 프로토콜 검증으로 실제 호스트
접지나 답변 품질 향상을 주장하지 않습니다.
