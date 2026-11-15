"""Write the landing-page membership table from the server capability matrix.

    python server/tools/export_membership.py          # write web/src/membership.json
    python server/tools/export_membership.py --check  # exit 1 when the file drifted
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'server'))

from app import membership  # noqa: E402

TARGET = ROOT / 'web' / 'src' / 'membership.json'


def render():
    return json.dumps(membership.public_table(), ensure_ascii=False, indent=2) + '\n'


def main():
    expected = render()
    if '--check' in sys.argv:
        current = TARGET.read_text(encoding='utf-8') if TARGET.is_file() else ''
        if current != expected:
            print(f'{TARGET.relative_to(ROOT)} drifted from server/app/membership.py; rerun export_membership.py')
            return 1
        print('membership.json matches the server capability table')
        return 0
    TARGET.write_text(expected, encoding='utf-8')
    print(f'wrote {TARGET.relative_to(ROOT)}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
