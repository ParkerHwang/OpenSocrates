"""Collect frozen source-room bytes and record independent SHA256 provenance."""
import hashlib
import json
import re
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

BASE = 'http://127.0.0.1:49804/'
ROOT = Path(__file__).resolve().parents[1]
raw = ROOT / 'raw'
raw.mkdir(exist_ok=True)
records = []

def get(name):
    url = BASE + name
    with urllib.request.urlopen(url) as response:
        data = response.read()
    filename = name or 'index.html'
    (raw / filename).write_bytes(data)
    records.append(dict(file='raw/' + filename, collection_url=url,
                        collected_at_utc=datetime.now(timezone.utc).isoformat(),
                        sha256=hashlib.sha256(data).hexdigest(), bytes=len(data)))
    return data

index = get('').decode()
for name in re.findall(r'href="([^\"]+)"', index):
    if '/' in name or name.startswith('.'):
        raise ValueError('Unexpected source-room link')
    get(name)
(ROOT / 'deliverables' / 'collection-register.json').write_text(json.dumps(records, indent=2)+'\n')
print(f'Collected {len(records)} files including index')
