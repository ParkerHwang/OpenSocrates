#!/bin/sh
# Fixed launcher for the released Apple-silicon macOS package hooks.
# The host package supplies only literal mode/host/event arguments.

set -eu

pass_through() {
    code=$1
    launch_mode=${2:-}
    launch_host=${3:-}
    if [ "$launch_mode" = hook ] && { [ "$launch_host" = codex ] || [ "$launch_host" = claude ]; }; then
        # Selector hook failures are always literal empty stdout.
        exit 0
    fi
    case "$code" in
        unsupported_platform|missing_runtime|invalid_arguments)
            ;;
        *)
            code=launcher_unavailable
            ;;
    esac
    printf '%s\n' "{\"decision\":\"pass\",\"diagnostic\":{\"code\":\"$code\",\"status\":\"unavailable\"}}"
    exit 0
}

if [ "$#" -lt 2 ] || [ "$#" -gt 3 ]; then
    pass_through invalid_arguments "${1:-}" "${2:-}"
fi

mode=$1
host=$2
event=${3:-}
codex_session_start_compact=false
codex_session_start_payload_base64=

case "$mode" in
    hook)
        case "$host" in
            claude|codex) ;;
            *) pass_through invalid_arguments "$mode" "$host" ;;
        esac
        case "$event" in
            session_started|user_prompt_submitted|skill_invoked|tool_succeeded|tool_failed|tool_batch_completed|completion_candidate|pre_compaction|post_compaction|session_ended)
                ;;
            *) pass_through invalid_arguments "$mode" "$host" ;;
        esac
        ;;
    control)
        if [ "$#" -ne 2 ]; then
            pass_through invalid_arguments "$mode" "$host"
        fi
        case "$host" in
            claude|codex) ;;
            *) pass_through invalid_arguments "$mode" "$host" ;;
        esac
        ;;
    *)
        pass_through invalid_arguments "$mode" "$host"
        ;;
esac

# Ordinary Codex SessionStart callbacks are specified literal no-ops. Avoid
# booting the large frozen selector runtime for startup/resume/clear, because a
# cold PyInstaller tree can exceed Codex's fixed two-second hook budget. Keep
# the bounded callback only in this process's memory. macOS's system plist
# parser admits only an exact top-level compact source. The textual fallback is
# used only by cross-platform package-contract tests; either way, the runtime
# still performs the complete JSON and native-event validation, so this hint
# cannot authorize a restore or any other side effect.
if [ "$mode" = hook ] && [ "$host" = codex ] && [ "$event" = session_started ]; then
    codex_session_start_payload_base64=$(
        /usr/bin/head -c 4194305 2>/dev/null |
            /usr/bin/openssl base64 -A 2>/dev/null
    ) || exit 0
    payload_bytes=$(
        printf '%s' "$codex_session_start_payload_base64" |
            /usr/bin/openssl base64 -d -A 2>/dev/null |
            /usr/bin/wc -c
    ) || exit 0
    set -- $payload_bytes
    if [ "$#" -ne 1 ]; then
        exit 0
    fi
    payload_bytes=$1
    case "$payload_bytes" in
        ''|*[!0-9]*) exit 0 ;;
    esac
    if [ "$payload_bytes" -gt 4194304 ]; then
        exit 0
    fi
    if [ -x /usr/bin/plutil ]; then
        payload_source=$(
            printf '%s' "$codex_session_start_payload_base64" |
                /usr/bin/openssl base64 -d -A 2>/dev/null |
                /usr/bin/plutil -extract source raw -o - - 2>/dev/null
        ) || exit 0
        if [ "$payload_source" != compact ]; then
            exit 0
        fi
    else
        if ! printf '%s' "$codex_session_start_payload_base64" |
            /usr/bin/openssl base64 -d -A 2>/dev/null |
            LC_ALL=C /usr/bin/grep -Eq '"source"[[:space:]]*:[[:space:]]*"compact"'; then
            exit 0
        fi
    fi
    codex_session_start_compact=true
fi

system_name=$(uname -s 2>/dev/null || printf '%s' unknown)
machine_name=$(uname -m 2>/dev/null || printf '%s' unknown)
case "$system_name/$machine_name" in
    Darwin/arm64|Darwin/aarch64)
        relative_binary=darwin-arm64/opensocrates-runtime/opensocrates-runtime
        ;;
    *)
        pass_through unsupported_platform "$mode" "$host"
        ;;
esac

# The generated host package places the launcher and the native runtime in
# sibling directories under the plugin root:
#
#   <plugin-root>/bin/launch.sh
#   <plugin-root>/runtime/<target>/opensocrates-runtime/opensocrates-runtime
#
# The launcher is valid only in that generated bin/ layout. Resolve exactly one
# runtime path from the plugin root; a launcher moved to the plugin root and a
# stray runtime tree under bin/ are deliberately unsupported.
launcher_dir=$(CDPATH= cd -P "$(dirname "$0")" 2>/dev/null && pwd -P) || pass_through missing_runtime "$mode" "$host"
plugin_root=$(CDPATH= cd -P "$launcher_dir/.." 2>/dev/null && pwd -P) || plugin_root=$launcher_dir

runtime_path=$plugin_root/runtime/$relative_binary
if [ ! -f "$runtime_path" ] || [ ! -x "$runtime_path" ]; then
    pass_through missing_runtime "$mode" "$host"
fi

case "$mode" in
    hook)
        if [ "$codex_session_start_compact" = true ]; then
            printf '%s' "$codex_session_start_payload_base64" |
                /usr/bin/openssl base64 -d -A 2>/dev/null |
                "$runtime_path" hook "$event" --host "$host" 2>/dev/null || true
        else
            "$runtime_path" hook "$event" --host "$host" 2>/dev/null || true
        fi
        exit 0
        ;;
    control)
        exec "$runtime_path" control apply --host "$host"
        ;;
esac

pass_through launcher_unavailable "$mode" "$host"
