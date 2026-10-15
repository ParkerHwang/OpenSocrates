#!/bin/sh
# Standard Python installer and normal macOS trust flow; no global changes.
LAB_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd) || exit 1
if command -v python3 >/dev/null 2>&1 && python3 -c 'import sys; sys.exit(sys.version_info[:2] < (3, 12))' >/dev/null 2>&1; then
    LAB_PYTHON=python3
elif command -v python3.12 >/dev/null 2>&1; then
    LAB_PYTHON=python3.12
else
    echo 'Python 3.12 이상을 공식 사이트에서 설치한 후 다시 여세요. / Install Python 3.12 or later, then reopen:'
    echo 'https://www.python.org/downloads/macos/'
    printf 'Enter를 누르면 닫습니다. / Press Enter to close. '
    read -r LAB_REPLY
    exit 2
fi
"$LAB_PYTHON" "$LAB_DIR/start-lab.py" "$@"
LAB_STATUS=$?
if [ "$LAB_STATUS" -ne 0 ]; then
    printf 'Enter를 누르면 닫습니다. / Press Enter to close. '
    read -r LAB_REPLY
fi
exit "$LAB_STATUS"
