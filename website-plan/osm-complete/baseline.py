"""Record/check the pre-task files that must remain unchanged."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEST = Path(__file__).with_name('baseline-sha256.json')


def files():
    for directory in ['website/data', 'website/mapbox', 'website-plan/story-data', 'website-plan/road-conflation']:
        for path in (ROOT / directory).rglob('*'):
            if path.is_file() and '__pycache__' not in str(path):
                yield path


if __name__ == '__main__':
    if not DEST.exists():
        DEST.write_text(json.dumps({p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                                    for p in files()}, indent=2) + '\n', encoding='utf-8')
        print('Recorded preservation baseline')
    else:
        values = json.loads(DEST.read_text())
        changed = [s for s, h in values.items() if not (ROOT / s).exists() or hashlib.sha256((ROOT / s).read_bytes()).hexdigest() != h]
        print(json.dumps(dict(checked=len(values), changed=changed)))
        if changed:
            raise SystemExit(1)
