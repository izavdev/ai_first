"""Read-only compatibility checks and receipts for reviewed local installations."""
from datetime import date
import hashlib
import json
from pathlib import Path
import re

from . import PACKAGE_VERSION, POLICY_REVISION

MARKER = f'<!-- ai-first-policy: {POLICY_REVISION} -->'
GENERATED = ('README.md', 'terminology.md')
CONFIGURATION = ('ai-first-schema.md', 'tracker.md', 'ai-first-capabilities.yml',
                 'capabilities-guide.md', 'plan-storage.md', 'runtime-guide.md')


def digest(path):
    return 'sha256:' + hashlib.sha256(path.read_bytes()).hexdigest()


def unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f'Duplicate JSON key: {key}')
        result[key] = value
    return result


def read_json(path):
    def invalid_constant(value):
        raise ValueError(f'Invalid JSON constant: {value}')
    return json.loads(path.read_text(encoding='utf-8'), object_pairs_hook=unique,
                      parse_constant=invalid_constant)


def relative(root, name):
    if not isinstance(name, str) or not name or '\\' in name:
        raise ValueError('Expected a portable relative file path')
    path = root / name
    if Path(name).is_absolute() or '..' in Path(name).parts or not path.resolve().is_relative_to(root.resolve()):
        raise ValueError('Installation paths must remain inside the installation')
    return path


def runtime_errors(root):
    manifest = read_json(root / 'runtime-manifest.json')
    errors = []
    if (manifest.get('schema') != 'ai-first-runtime/v1'
            or manifest.get('policy_revision') != POLICY_REVISION
            or manifest.get('package_version') != PACKAGE_VERSION):
        errors.append('Runtime manifest/version mismatch; rerun setup')
    files = manifest.get('files')
    required = {'policy.py', 'approval.py', 'workflow-contract.json', 'adapter-contract.json',
                'ai_first/__init__.py', 'ai_first/version.py', 'ai_first/installation.py', 'ai_first/cli.py',
                'ai_first/schema.py', 'ai_first/classification.py', 'ai_first/workflow.py',
                'ai_first/capabilities.py', 'ai_first/decomposition.py', 'ai_first/adapters.py',
                'ai_first/inventory.py'}
    if not isinstance(files, dict) or set(files) != required:
        return ['Runtime file inventory mismatch; rerun setup']
    for name, expected in files.items():
        path = relative(root, name)
        if not path.is_file() or digest(path) != expected:
            errors.append(f'Runtime file missing or modified: {name}')
    contract = read_json(root / 'workflow-contract.json')
    if contract.get('policy_revision') != POLICY_REVISION:
        errors.append('Unsupported workflow contract policy revision')
    return errors


def doctor(root, required_policy=POLICY_REVISION):
    """Check reviewed bytes and protocol markers, never authenticate a tracker."""
    root = Path(root)
    errors, unrecorded, customized = [], [], []
    if required_policy != POLICY_REVISION:
        errors.append(f'Consumer requires {required_policy}; helper implements {POLICY_REVISION}')
    try:
        errors.extend(runtime_errors(root))
        receipt = read_json(root / 'installation.json')
        if (receipt.get('schema') != 'ai-first-installation/v2'
                or receipt.get('policy_revision') != POLICY_REVISION
                or receipt.get('package_version') != PACKAGE_VERSION):
            errors.append('Missing or incompatible installation receipt; rerun setup')
        files = receipt.get('installed_hashes', {})
        runtime = read_json(root / 'runtime-manifest.json')['files']
        expected_files = set(runtime) | set(CONFIGURATION) | set(GENERATED) | {'runtime-manifest.json'}
        if set(files) != expected_files:
            errors.append('Receipt file inventory does not match this installation version')
        for name in expected_files:
            path = relative(root, name)
            if not path.is_file():
                errors.append(f'Missing installed file: {name}')
            elif digest(path) != files.get(name):
                if name in runtime or name == 'runtime-manifest.json':
                    errors.append(f'Runtime differs from recorded installation: {name}')
                else:
                    unrecorded.append(name)
        for name in ('ai-first-schema.md', 'tracker.md'):
            text = (root / name).read_text(encoding='utf-8')
            markers = re.findall(r'<!-- ai-first-policy: [^\n]*? -->', text)
            if markers != [MARKER]:
                errors.append(f'Missing, duplicate, or incompatible policy marker: {name}')
        source_hashes = receipt.get('source_hashes', {})
        for source, destination in receipt.get('source_to_destination', {}).items():
            if destination in files and source_hashes.get(source) != files[destination]:
                customized.append(destination)
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
        errors.append(f'Cannot validate installation: {error}')
    return dict(compatible=not errors, policy_revision=POLICY_REVISION,
                package_version=PACKAGE_VERSION, errors=errors,
                reviewed_customizations=sorted(set(customized)),
                unrecorded_changes=sorted(unrecorded))


def record_installation(root, source_manifest, tracker):
    """Record already-reviewed files. Does not copy, reset, or approve configuration."""
    root, source_manifest = Path(root), Path(source_manifest)
    if tracker not in ('github', 'ado', 'linear'):
        raise ValueError('Unsupported tracker')
    source = read_json(source_manifest)
    if source.get('schema') != 'ai-first-assets/v1' or source.get('package_version') != PACKAGE_VERSION:
        raise ValueError('Source package version does not match helper')
    prefix = 'skills/setup-ai-first/'
    skill_root = source_manifest.parent.parent
    for name, expected in source['sources'].items():
        if not name.startswith(prefix):
            raise ValueError('Unexpected source path in setup manifest')
        path = relative(skill_root, name[len(prefix):])
        if digest(path) != expected:
            raise ValueError(f'Source package hash mismatch: {name}')
    source_runtime = read_json(source_manifest.parent / 'runtime-manifest.json')
    if read_json(root / 'runtime-manifest.json') != source_runtime:
        raise ValueError('Installed runtime manifest differs from the verified source')
    errors = runtime_errors(root)
    if errors:
        raise ValueError('; '.join(errors))
    for name in ('ai-first-schema.md', 'tracker.md'):
        markers = re.findall(r'<!-- ai-first-policy: [^\n]*? -->', (root / name).read_text(encoding='utf-8'))
        if markers != [MARKER]:
            raise ValueError(f'Reconcile the policy revision in {name} before recording')
    names = set(source_runtime['files']) | set(CONFIGURATION) | set(GENERATED) | {'runtime-manifest.json'}
    mapping = {}
    for name in names - set(GENERATED):
        asset = f'adapters/{tracker}.md' if name == 'tracker.md' else name
        source_name = prefix + 'assets/' + asset
        if source_name not in source['sources']:
            raise ValueError(f'Missing source manifest entry: {source_name}')
        mapping[source_name] = name
    receipt = dict(schema='ai-first-installation/v2', setup_date=date.today().isoformat(),
                   package_version=PACKAGE_VERSION, policy_revision=POLICY_REVISION,
                   tracker=tracker, source_manifest_digest=digest(source_manifest),
                   source_hashes={key: source['sources'][key] for key in sorted(mapping)},
                   source_to_destination=dict(sorted(mapping.items())),
                   installed_hashes={name: digest(relative(root, name)) for name in sorted(names)},
                   source_commit=None, source_dirty=None)
    # A failed validation above leaves the previous receipt intact.
    temporary = root / 'installation.json.tmp'
    temporary.write_text(json.dumps(receipt, indent=2, ensure_ascii=False)+'\n', encoding='utf-8', newline='\n')
    temporary.replace(root / 'installation.json')
    return receipt
