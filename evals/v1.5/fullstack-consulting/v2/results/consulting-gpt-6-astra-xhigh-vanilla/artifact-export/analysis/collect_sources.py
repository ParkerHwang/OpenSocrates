"""Collect the frozen source room, preserving bytes and collection provenance."""
from pathlib import Path
from urllib.request import urlopen
from html.parser import HTMLParser
from datetime import datetime, timezone
import hashlib, json

ROOT = Path(__file__).resolve().parents[1]
BASE = "http://127.0.0.1:55588/"
RAW = ROOT / "evidence" / "raw"
RAW.mkdir(parents=True, exist_ok=True)

class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self.links.extend(v for k, v in attrs if k == "href")

def download(rel, name):
    with urlopen(BASE + rel) as response:
        data = response.read()
    (RAW / name).write_bytes(data)
    return dict(file=name, collection_url=BASE + rel,
                collected_at_utc=datetime.now(timezone.utc).isoformat(),
                sha256=hashlib.sha256(data).hexdigest(), bytes=len(data))

records = [download("", "index.html")]
parser = Links()
parser.feed((RAW / "index.html").read_text())
for rel in parser.links:
    if "/" in rel or rel.startswith("."):
        raise ValueError(f"Unexpected source-room link: {rel}")
    records.append(download(rel, rel))
(ROOT / "evidence" / "collection_manifest.json").write_text(json.dumps(records, indent=2) + "\n")
print(f"Collected {len(records)} files; byte hashes recorded in evidence/collection_manifest.json")
