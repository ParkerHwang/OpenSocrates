#!/bin/sh
# Fixed, platform-selecting launcher for macOS/Linux package hooks.
# The host package supplies only literal mode/host/event arguments.

set -eu

pass_through() {
    code=$1
    launch_mode=${2:-}
    launch_host=${3:-}
    if [ "$launch_mode" = hook ] && [ "$launch_host" = codex ]; then
        # The Codex selector contract makes every launcher/runtime failure a
        # literal empty hook response.
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

case "$mode" in
    hook)
        case "$host" in
            codex) ;;
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
            codex) ;;
            *) pass_through invalid_arguments "$mode" "$host" ;;
        esac
        ;;
    *)
        pass_through invalid_arguments "$mode" "$host"
        ;;
esac

system_name=$(uname -s 2>/dev/null || printf '%s' unknown)
machine_name=$(uname -m 2>/dev/null || printf '%s' unknown)
case "$system_name/$machine_name" in
    Darwin/arm64|Darwin/aarch64)
        relative_binary=darwin-arm64/opensocrates-runtime/opensocrates-runtime
        ;;
    Darwin/x86_64|Darwin/amd64)
        relative_binary=darwin-x64/opensocrates-runtime/opensocrates-runtime
        ;;
    Linux/x86_64|Linux/amd64)
        relative_binary=linux-x64/opensocrates-runtime/opensocrates-runtime
        ;;
    *)
        pass_through unsupported_platform "$mode" "$host"
        ;;
esac

launcher_dir=$(CDPATH= cd -P "$(dirname "$0")" 2>/dev/null && pwd -P) || pass_through missing_runtime "$mode" "$host"
runtime_path=$launcher_dir/$relative_binary
if [ ! -f "$runtime_path" ] || [ ! -x "$runtime_path" ]; then
    pass_through missing_runtime "$mode" "$host"
fi

case "$mode" in
    hook)
        "$runtime_path" hook "$event" --host "$host" 2>/dev/null || true
        exit 0
        ;;
    control)
        exec "$runtime_path" control apply --host "$host"
        ;;
esac

pass_through launcher_unavailable "$mode" "$host"
