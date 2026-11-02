#!/bin/sh
# Standard Python installer and normal macOS trust flow; no global changes.
LAB_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd) || exit 1
LAB_PYTHON=""
for LAB_CANDIDATE in \
    python3 \
    python3.14 \
    python3.13 \
    python3.12 \
    /Library/Frameworks/Python.framework/Versions/Current/bin/python3 \
    /opt/homebrew/bin/python3 \
    /usr/local/bin/python3
do
    if command -v "$LAB_CANDIDATE" >/dev/null 2>&1 && \
        "$LAB_CANDIDATE" -c 'import sys; sys.exit(sys.version_info[:2] < (3, 12))' >/dev/null 2>&1
    then
        LAB_PYTHON="$LAB_CANDIDATE"
        break
    fi
done
if [ -z "$LAB_PYTHON" ]; then
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
