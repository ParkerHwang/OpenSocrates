#!/bin/sh
# Fixed, platform-selecting launcher for macOS/Linux package hooks.
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

# The generated host package places the launcher and the native runtime in
# sibling directories under the plugin root:
#
#   <plugin-root>/bin/launch.sh
#   <plugin-root>/runtime/<target>/opensocrates-runtime/opensocrates-runtime
#
# The runtime must therefore be resolved from the plugin root rather than from
# the launcher's own directory. Candidates are probed in package-layout order:
# the launcher's parent directory first (the generated layout), then the
# launcher's own directory (a launcher placed at the plugin root). The
# launcher directory itself is never treated as a runtime root, so a stray
# tree under bin/ cannot satisfy the lookup.
launcher_dir=$(CDPATH= cd -P "$(dirname "$0")" 2>/dev/null && pwd -P) || pass_through missing_runtime "$mode" "$host"
plugin_root=$(CDPATH= cd -P "$launcher_dir/.." 2>/dev/null && pwd -P) || plugin_root=$launcher_dir

runtime_path=
for runtime_root in "$plugin_root/runtime" "$launcher_dir/runtime"; do
    candidate=$runtime_root/$relative_binary
    if [ -f "$candidate" ] && [ -x "$candidate" ]; then
        runtime_path=$candidate
        break
    fi
done
if [ -z "$runtime_path" ]; then
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
