"""Collect the frozen room; run only when intentionally refreshing raw evidence."""
from pathlib import Path
from urllib.request import urlopen
import argparse
import datetime as dt
import hashlib
import json
import re

ROOT = Path(__file__).resolve().parents[1]

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--url', default='http://127.0.0.1:49799/')
    args = parser.parse_args()
    base = args.url.rstrip('/') + '/'
    raw = ROOT / 'evidence/raw'
    raw.mkdir(parents=True, exist_ok=True)
    index = urlopen(base).read()
    records = []
    for name in ['index.html'] + re.findall(r'href="([^"]+)"', index.decode()):
        if '/' in name or name.startswith('.'):
            raise ValueError('Unexpected source-room path: ' + name)
        url = base + ('' if name == 'index.html' else name)
        data = index if name == 'index.html' else urlopen(url).read()
        (raw / name).write_bytes(data)
        records.append(dict(file='evidence/raw/' + name, collection_url=url,
                            collected_at_utc=dt.datetime.now(dt.timezone.utc).isoformat(),
                            sha256=hashlib.sha256(data).hexdigest(), bytes=len(data)))
    (ROOT / 'evidence/collection-manifest.json').write_text(json.dumps(records, indent=2) + '\n')
    print(f'Collected {len(records)} files into {raw}')

if __name__ == '__main__':
    main()
