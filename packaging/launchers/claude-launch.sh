#!/bin/sh
# Fixed Apple-silicon Claude launcher. No Codex control/SDK dispatch exists.
set -eu

unavailable() {
    if [ "${1:-}" = decision ]; then
        printf '%s\n' '{"status":"unavailable","reason":"native_launcher_unavailable","applied":"unverified"}'
    elif [ "${1:-}" = locale ]; then
        printf '%s\n' '{"status":"unavailable","reason":"native_launcher_unavailable"}'
    fi
    exit 0
}

if [ "$#" -lt 2 ] || [ "$#" -gt 4 ] || { [ "$#" -eq 4 ] && [ "${1:-}" != locale ]; }; then
    unavailable "${1:-}"
fi
mode=$1
host=$2
event=${3:-}
locale_value=${4:-}
[ "$host" = claude ] || unavailable "$mode"
case "$mode" in
    hook)
        [ "$#" -eq 3 ] || unavailable "$mode"
        case "$event" in
            session_started|user_prompt_submitted) ;;
            completion_candidate|session_ended|post_compaction) exit 0 ;;
            *) unavailable "$mode" ;;
        esac
        ;;
    decision)
        if [ "$#" -eq 3 ] && [ "$event" != --stream ]; then
            unavailable "$mode"
        fi
        ;;
    locale)
        case "$event" in
            get|reset) [ "$#" -eq 3 ] || unavailable "$mode" ;;
            set)
                [ "$#" -eq 4 ] || unavailable "$mode"
                case "$locale_value" in
                    en|ko|zh|ja|fr|de|it|es|pt|th|follow) ;;
                    *) unavailable "$mode" ;;
                esac
                ;;
            *) unavailable "$mode" ;;
        esac
        ;;
    *) unavailable "$mode" ;;
esac

system_name=$(/usr/bin/uname -s 2>/dev/null) || unavailable "$mode"
machine_name=$(/usr/bin/uname -m 2>/dev/null) || unavailable "$mode"
case "$system_name/$machine_name" in
    Darwin/arm64|Darwin/aarch64) ;;
    *) unavailable "$mode" ;;
esac

launcher_dir=$(CDPATH= cd -P "$(dirname "$0")" 2>/dev/null && pwd -P) || unavailable "$mode"
case "$launcher_dir" in
    */bin) ;;
    *) unavailable "$mode" ;;
esac
plugin_root=$(CDPATH= cd -P "$launcher_dir/.." 2>/dev/null && pwd -P) || unavailable "$mode"
runtime_dir=$plugin_root/runtime/darwin-arm64/opensocrates-runtime
runtime_path=$runtime_dir/opensocrates-runtime
for owned_path in "$plugin_root/runtime" "$plugin_root/runtime/darwin-arm64" "$runtime_dir" "$runtime_path"; do
    [ ! -L "$owned_path" ] || unavailable "$mode"
done
[ -f "$runtime_path" ] && [ -x "$runtime_path" ] || unavailable "$mode"

case "$mode" in
    hook)
        "$runtime_path" claude-hook 2>/dev/null || true
        exit 0
        ;;
    decision)
        if [ "$event" = --stream ]; then
            exec "$runtime_path" decision --stream
        fi
        exec "$runtime_path" decision
        ;;
    locale)
        if [ "$event" = set ]; then
            exec "$runtime_path" locale set "$locale_value"
        fi
        exec "$runtime_path" locale "$event"
        ;;
esac
