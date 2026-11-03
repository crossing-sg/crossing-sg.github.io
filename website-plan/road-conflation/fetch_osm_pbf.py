"""Download the explicitly requested BBBike Singapore PBF into ignored local data."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import urllib.request

ROOT=Path(__file__).resolve().parents[2]
URL='https://download.bbbike.org/osm/bbbike/Singapore/Singapore.osm.pbf'
DEST=ROOT/'local-data/osm/pbf/Singapore.osm.pbf'


def run():
    DEST.parent.mkdir(parents=True,exist_ok=True)
    if DEST.exists():
        print(f'Reusing existing PBF without overwriting: {DEST} ({DEST.stat().st_size:,} bytes)')
        return
    partial=DEST.with_suffix('.pbf.part')
    request=urllib.request.Request(URL,headers={'User-Agent':'crossing-sg-local-road-review/1.0'})
    digest=hashlib.sha256()
    with urllib.request.urlopen(request,timeout=60) as response:
        headers=dict(response.headers.items())
        expected=int(response.headers.get('Content-Length','0'))
        with partial.open('wb') as stream:
            count=0
            while chunk:=response.read(1024*1024):
                stream.write(chunk);digest.update(chunk);count+=len(chunk)
                if count%(20*1024*1024)<len(chunk):print(f'Downloaded {count/1048576:.1f} MiB',flush=True)
        if expected and count!=expected:
            raise RuntimeError(f'Incomplete PBF: {count} bytes, expected {expected}')
    partial.replace(DEST)
    metadata=dict(url=URL,downloaded_utc=datetime.now(timezone.utc).isoformat(),bytes=count,
                  sha256=digest.hexdigest(),http_headers=headers,original_extract='BBBike Singapore; snapshot metadata retained in PBF header')
    DEST.with_suffix('.pbf.download.json').write_text(json.dumps(metadata,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in metadata.items() if k!='http_headers'},indent=2))


if __name__=='__main__':run()
