#!/usr/bin/env python3
"""Validate repository contracts and packaging; --refresh updates generated assets."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / 'skills/setup-ai-first/assets'
MANIFEST = ASSETS / 'asset-manifest.json'
sys.path.insert(0, str(ROOT))


def unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f'Duplicate key: {key}')
        result[key] = value
    return result


def read_json(path):
    return json.loads(path.read_text(), object_pairs_hook=unique)


def asset_manifest():
    paths = [ROOT / 'skills/setup-ai-first/SKILL.md'] + [p for p in ASSETS.rglob('*')
             if p.is_file() and p != MANIFEST and '__pycache__' not in p.parts]
    return dict(schema='ai-first-assets/v1', package_version=read_json(ROOT / '.codex-plugin/plugin.json')['version'],
                sources={p.relative_to(ROOT).as_posix(): 'sha256:'+hashlib.sha256(p.read_bytes()).hexdigest()
                         for p in sorted(paths)})


def contract_table():
    contract = read_json(ASSETS / 'workflow-contract.json')
    lines = ['| Scope | Field | Type/value |', '|---|---|---|']
    for scope in ('brief', 'task', 'optional_task', 'provenance'):
        for field, rule in contract[scope].items():
            lines.append(f'| {scope} | `{field}` | `{rule}` |')
    return '\n'.join(lines)


def check(condition, message):
    if not condition:
        raise ValueError(message)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--refresh', action='store_true', help='Regenerate field table and shipped asset hashes after reviewed edits')
    args = parser.parse_args()
    try:
        import yaml
    except ImportError:
        raise ValueError('Install development dependencies: python3 -m pip install -r requirements-dev.txt')

    class Loader(yaml.SafeLoader):
        pass

    def mapping(loader, node):
        return unique([(loader.construct_object(k, deep=True), loader.construct_object(v, deep=True))
                       for k, v in node.value])
    Loader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, mapping)

    schema = ASSETS / 'ai-first-schema.md'
    start, end = '<!-- contract-fields:start -->', '<!-- contract-fields:end -->'
    text = schema.read_text()
    check(text.count(start) == text.count(end) == 1, 'Missing/duplicate generated contract table markers')
    before, rest = text.split(start)
    current, after = rest.split(end)
    wanted = '\n' + contract_table() + '\n'
    if args.refresh:
        schema.write_text(before + start + wanted + end + after)
        MANIFEST.write_text(json.dumps(asset_manifest(), indent=2, ensure_ascii=False)+'\n')
    else:
        check(current == wanted, 'Contract field table drift; review changes then use --refresh')
        check(MANIFEST.exists() and read_json(MANIFEST) == asset_manifest(),
              'Shipped asset hashes drifted; review changes then use --refresh')

    for p in [*ROOT.glob('.*-plugin/*.json'), *(ROOT / 'skills').rglob('*.json'), *(ROOT / 'integrations').rglob('*.json')]:
        read_json(p)
    claude = read_json(ROOT / '.claude-plugin/plugin.json')
    codex = read_json(ROOT / '.codex-plugin/plugin.json')
    check(claude['version'] == codex['version'], 'Plugin versions differ')
    skills = sorted(ROOT.glob('skills/*/SKILL.md'))
    check({(ROOT / path).resolve() for path in claude['skills']} == {p.parent.resolve() for p in skills}, 'Claude skill paths differ from package')
    check((ROOT / codex['skills']).resolve() == (ROOT / 'skills').resolve(), 'Codex skills path invalid')
    marketplace = read_json(ROOT / '.claude-plugin/marketplace.json')
    check(any(p['name'] == claude['name'] and p['source'] == './' for p in marketplace['plugins']), 'Marketplace bundle mismatch')
    for p in skills:
        front = p.read_text().split('---', 2)[1]
        fields = yaml.load(front, Loader=Loader)
        check(fields.get('name') == p.parent.name and bool(fields.get('description')), f'Invalid front matter: {p}')
    for base in ('skills', 'integrations'):
        for p in (ROOT / base).rglob('*'):
            if p.suffix in ('.yaml', '.yml'):
                yaml.load(p.read_text(), Loader=Loader)

    capabilities = yaml.load((ASSETS / 'ai-first-capabilities.yml').read_text(), Loader=Loader)
    check(capabilities['defaults'] == {'enabled': False, 'status': 'provisional'}, 'Unsafe capability defaults')
    check(capabilities['capabilities'] == capabilities['approvals'] == [], 'Shipped defaults must not approve capabilities')
    routes = capabilities['profile_routing']
    check(set(routes) == {'human-only', 'pair', 'delegate-a1', 'delegate-a2', 'investigation'}, 'Profile routing incomplete')
    check(routes['human-only'] is None and all(v in capabilities['profiles'] for k, v in routes.items() if k != 'human-only'), 'Profile routes reference missing profiles')

    # Local link targets only: this does not make network requests or claim live URL validity.
    documents = [ROOT / 'README.md', ROOT / 'whitepaper.md'] + list((ROOT / 'docs').glob('*.md')) + list((ROOT / 'skills').rglob('*.md'))
    for p in documents:
        for target in re.findall(r'\]\(([^\s)]+)\)', p.read_text()):
            if '://' in target or target.startswith('#'):
                continue
            path = target.split('#')[0]
            check((p.parent / path).exists(), f'Broken local link: {p.relative_to(ROOT)} -> {target}')
    subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-q'], cwd=ROOT, check=True)
    print('Repository validation passed: contracts, fixtures, skills, manifests, YAML, local links, asset hashes, and tests.')


if __name__ == '__main__':
    try:
        main()
    except (ValueError, KeyError, OSError, subprocess.SubprocessError) as error:
        print(f'Validation failed: {error}', file=sys.stderr)
        raise SystemExit(1)
