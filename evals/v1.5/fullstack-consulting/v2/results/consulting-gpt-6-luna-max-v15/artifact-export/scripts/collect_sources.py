"""Save every linked file from the disposable Meridian source room."""
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.request import urlopen
import hashlib
import json


BASE = "http://127.0.0.1:52727/"
OUT = Path(__file__).resolve().parents[1] / "evidence" / "source_room"


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.hrefs = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            href = dict(attrs).get("href")
            if href:
                self.hrefs.append(href)


def record(path, url, payload):
    return {
        "file": str(path.relative_to(OUT.parents[1])),
        "source_url": url,
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
        "sha256": hashlib.sha256(payload).hexdigest(),
        "bytes": len(payload),
    }


OUT.mkdir(parents=True, exist_ok=True)
index = urlopen(BASE).read()
(OUT / "index.html").write_bytes(index)
parser = Links()
parser.feed(index.decode("utf-8", "replace"))
items = [record(OUT / "index.html", BASE, index)]
for href in parser.hrefs:
    if href.startswith(("http://", "https://")):
        continue
    payload = urlopen(BASE + href).read()
    path = OUT / href
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    items.append(record(path, BASE + href, payload))

register = {
    "collection_type": "frozen local source-room snapshot",
    "collected_at_utc": datetime.now(timezone.utc).isoformat(),
    "base_url": BASE,
    "files": items,
}
(OUT / "collection-manifest.json").write_text(json.dumps(register, indent=2) + "\n")
print(json.dumps(register, indent=2))
