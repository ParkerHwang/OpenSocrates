from urllib.request import urlopen
from html.parser import HTMLParser
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json


BASE = "http://127.0.0.1:49802/"
DEST = Path(__file__).resolve().parents[1] / "evidence" / "source_room"


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.hrefs = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            href = dict(attrs).get("href")
            if href:
                self.hrefs.append(href)


def now():
    return datetime.now(timezone.utc).isoformat()


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def main():
    DEST.mkdir(parents=True, exist_ok=True)
    index = urlopen(BASE, timeout=30).read()
    (DEST / "index.html").write_bytes(index)
    parser = Links()
    parser.feed(index.decode("utf-8"))
    rows = []
    for name in parser.hrefs:
        body = urlopen(BASE + name, timeout=60).read()
        (DEST / name).write_bytes(body)
        rows.append({
            "file": name,
            "source_url": BASE + name,
            "retrieved_utc": now(),
            "sha256": sha256(body),
            "bytes": len(body),
        })
    manifest = {
        "index_url": BASE,
        "index_retrieved_utc": now(),
        "index_sha256": sha256(index),
        "files": rows,
    }
    (DEST / "download_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"Downloaded {len(rows)} files from {BASE}")
    for row in rows:
        print(f"{row['file']}\t{row['bytes']} bytes\t{row['sha256']}")


if __name__ == "__main__":
    main()
