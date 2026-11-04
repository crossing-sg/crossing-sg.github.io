"""Download a complete country PBF without replacing any earlier local source."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
URL = 'https://download.openstreetmap.fr/extracts/asia/singapore.osm.pbf'
DEST = ROOT / 'local-data/osm/complete-singapore/singapore.osm.pbf'


def main():
    DEST.parent.mkdir(parents=True, exist_ok=True)
    meta = DEST.with_suffix('.pbf.download.json')
    if DEST.exists():
        if not meta.exists() or hashlib.sha256(DEST.read_bytes()).hexdigest() != json.loads(meta.read_text())['sha256']:
            raise RuntimeError('Existing download is unverified; refusing to replace it')
        print('Verified existing download:', DEST)
        return
    request = urllib.request.Request(URL, headers={'User-Agent': 'Mozilla/5.0 crossing-sg-local-review/1.0'})
    partial = DEST.with_suffix('.pbf.part')
    with urllib.request.urlopen(request, timeout=60) as response, partial.open('xb') as stream:
        headers = dict(response.headers.items())
        digest = hashlib.sha256()
        size = 0
        while chunk := response.read(1024 * 1024):
            stream.write(chunk)
            digest.update(chunk)
            size += len(chunk)
        if size != int(headers['Content-Length']):
            raise RuntimeError('Incomplete download')
    partial.rename(DEST)
    metadata = dict(url=URL, downloaded_utc=datetime.now(timezone.utc).isoformat(),
                    bytes=size, sha256=digest.hexdigest(), http_headers=headers)
    meta.write_text(json.dumps(metadata, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(metadata, indent=2))


if __name__ == '__main__':
    main()
