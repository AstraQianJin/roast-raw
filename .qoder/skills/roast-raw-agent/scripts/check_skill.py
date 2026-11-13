import argparse
from pathlib import Path
import re
import sys


def check(root):
    folder = root / '.qoder/skills/roast-raw-agent'
    skill = folder / 'SKILL.md'
    if not skill.is_file():
        return ['Missing SKILL.md']
    text = skill.read_text(encoding='utf-8')
    errors = []
    header = re.match(r'\A---\n(.*?)\n---\n', text, re.S)
    if not header:
        return ['Invalid YAML frontmatter boundaries']
    metadata = dict(line.split(': ', 1) for line in header[1].splitlines() if ': ' in line)
    name = metadata.get('name', '')
    description = metadata.get('description', '')
    if not re.fullmatch(r'[a-z0-9-]+', name) or name != folder.name:
        errors.append('Skill name must match its folder')
    if not description or len(description) > 1024:
        errors.append('Description must be one nonempty line, at most 1024 characters')
    if len(text[header.end():].splitlines()) >= 500:
        errors.append('Skill body must be under 500 lines')
    if 'TODO:' in text:
        errors.append('Unresolved template placeholder')
    for filename in ('README.md', 'CHANGELOG.md', 'INSTALLATION_GUIDE.md'):
        if (folder / filename).exists():
            errors.append(f'Extraneous file: {filename}')
    for pointer in ('AGENTS.md', 'TODO.md', 'README.md', 'docs/项目交接.md',
                    'server/app/main.py', 'server/app/store.py', 'server/app/calendar.py',
                    'server/app/stats/classify.py', 'server/app/stats/engine.py',
                    'server/app/stats/prescription.py', 'server/app/validation.py',
                    'server/tools/gen_data.py', 'server/tools/synth_plan.py',
                    'data/schema/RPL-Raw-v1.json', 'data/schema/RPL-Review-v1.json',
                    'web/package.json', 'web/src/App.vue', 'web/src/tokens.css',
                    'web/src/components/MuscleMap.vue', 'tests/verify.js',
                    'tests/browser.mjs', 'tests/cdp.mjs'):
        if not (root / pointer).is_file():
            errors.append(f'Missing project pointer: {pointer}')
    return errors


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    args = parser.parse_args()
    errors = check(args.root.resolve())
    for error in errors:
        print(f'FAIL {error}')
    if not errors:
        print('PASS Skill metadata, body, folder and project pointers')
    sys.exit(bool(errors))
