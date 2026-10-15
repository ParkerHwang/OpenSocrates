#!/usr/bin/env python3
"""Start the office evaluation UI without provider SDKs, keys or CLI clients."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve()
ROOT = SCRIPT.parent if SCRIPT.name == "start-lab.py" else SCRIPT.parents[1]
sys.path.insert(0, str(ROOT / "src"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=ROOT / "lab-data")
    parser.add_argument("--pack", type=Path, default=ROOT / "evals" / "office-work-v1")
    parser.add_argument("--payloads", type=Path, default=ROOT / "payloads")
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    if sys.version_info[:2] < (3, 12):
        print(
            "Python 3.12 이상이 필요합니다. / Python 3.12 or later required: https://www.python.org/downloads/"
        )
        return 2
    if not 0 <= args.port <= 65535:
        parser.error("port must be 0..65535")
    from opensocrates.evaluation.server import serve

    try:
        serve(
            args.data,
            args.pack,
            args.payloads,
            open_browser=not args.no_browser,
            port=args.port,
        )
    except KeyboardInterrupt:
        return 0
    except Exception:
        print(
            "실행을 완료하지 못했습니다. 설정과 데이터 폴더를 확인하세요. / Lab unavailable; check setup and owned data folder."
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
