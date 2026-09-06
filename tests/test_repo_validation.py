import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('repo_validation', ROOT / 'scripts/validate_repo.py')
validator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(validator)


class RepositoryValidationTests(unittest.TestCase):
    def test_duplicate_json_keys_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'contract.json'
            path.write_text('{"version":"1","version":"2"}')
            with self.assertRaises(ValueError):
                validator.read_json(path)

    def test_source_hashes_detect_modified_added_and_removed_assets(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            assets = root / 'skills/setup-ai-first/assets'
            assets.mkdir(parents=True)
            (assets.parent / 'SKILL.md').write_text('skill')
            (root / '.codex-plugin').mkdir()
            (root / '.codex-plugin/plugin.json').write_text(json.dumps({'version': '1.0.0'}))
            source = assets / 'schema.md'
            source.write_text('original')
            with patch.multiple(validator, ROOT=root, ASSETS=assets, MANIFEST=assets / 'asset-manifest.json'):
                original = validator.asset_manifest()
                source.write_text('edited')
                self.assertNotEqual(original, validator.asset_manifest())
                source.write_text('original')
                extra = assets / 'new.json'
                extra.write_text('{}')
                self.assertNotEqual(original, validator.asset_manifest())
                extra.unlink()
                self.assertEqual(original, validator.asset_manifest())
                source.unlink()
                self.assertNotEqual(original, validator.asset_manifest())

    def test_field_inventory_changes_are_visible_in_generated_table(self):
        with tempfile.TemporaryDirectory() as tmp:
            assets = Path(tmp)
            contract = {'brief': {'kind': 'brief'}, 'task': {'kind': 'task'},
                        'optional_task': {}, 'provenance': {}}
            path = assets / 'workflow-contract.json'
            path.write_text(json.dumps(contract))
            with patch.object(validator, 'ASSETS', assets):
                before = validator.contract_table()
                contract['task']['new-required-field'] = 'text'
                path.write_text(json.dumps(contract))
                after = validator.contract_table()
                self.assertNotEqual(before, after)
                self.assertIn('`new-required-field`', after)


if __name__ == '__main__':
    unittest.main()
