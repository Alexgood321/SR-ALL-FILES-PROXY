"""HAPP is a target adapter of the existing canonical INCY compiler."""
import copy
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))


class HappPolicyTests(unittest.TestCase):
    def test_same_writer_independent_validation_ready_and_no_docker(self):
        workflow = (ROOT / '.github/workflows/sync-incy-routing.yml').read_text()
        self.assertEqual(workflow.count('  sync:\n'), 1)
        self.assertIn('context":"happ/xray-policy-ready', workflow)
        self.assertIn('happ/xray-policy.json|happ/xray-conversion-report.md', workflow)
        self.assertIn('-c /tmp/happ-xray-validation.json', workflow)
        self.assertIn("-p 'test_happ_xray_policy.py'", workflow)
        self.assertNotIn('docker ', workflow)
        self.assertNotIn('publish_policy_v2.py --publish', workflow)
        validate = (ROOT / '.github/workflows/validate-incy-routing.yml').read_text()
        self.assertIn('scripts/generate_happ_xray_policy.py', validate)
        self.assertIn('-c /tmp/happ-xray-validation.json', validate)

    def test_canonical_parity_and_independent_copy(self):
        import generate_incy_xray_policy as incy
        import generate_happ_xray_policy as happ
        expected, _, _ = incy.convert_xray()
        actual = happ.convert_happ()
        self.assertEqual(actual, expected)
        happ.validate_happ(actual)
        actual['dns']['servers'].clear()
        self.assertEqual(incy.convert_xray()[0], expected)

    def test_rejects_invalid_outbound_and_missing_dns_guard(self):
        import generate_happ_xray_policy as happ
        policy = happ.convert_happ()
        for mutation in ('unknown_tag', 'dns_guard'):
            bad = copy.deepcopy(policy)
            if mutation == 'unknown_tag':
                bad['routing']['rules'][0]['outboundTag'] = 'other'
            else:
                bad['routing']['rules'] = [r for r in bad['routing']['rules']
                                           if r.get('inboundTag') != ['dns-internal']]
            with self.assertRaises(ValueError):
                happ.validate_happ(bad)

    def test_cli_deterministic_and_validation_config(self):
        with tempfile.TemporaryDirectory() as folder:
            base = pathlib.Path(folder)
            cmd = [sys.executable, '-B', str(ROOT / 'scripts/generate_happ_xray_policy.py'),
                   '--output', str(base / 'policy.json'), '--report', str(base / 'report.md'),
                   '--write-validation-config', str(base / 'xray.json')]
            subprocess.run(cmd, check=True, capture_output=True)
            subprocess.run(cmd + ['--check'], check=True, capture_output=True)
            config = json.loads((base / 'xray.json').read_text())
            self.assertEqual({o['tag'] for o in config['outbounds']}, {'proxy', 'direct', 'block'})
            self.assertEqual(config['dns'], json.loads((base / 'policy.json').read_text())['dns'])

    def test_cli_in_process_checks_drift_without_writes(self):
        import generate_happ_xray_policy as happ
        with tempfile.TemporaryDirectory() as folder:
            base = pathlib.Path(folder)
            args = ['happ', '--output', str(base / 'policy.json'), '--report', str(base / 'report.md'),
                    '--write-validation-config', str(base / 'xray.json')]
            with mock.patch.object(sys, 'argv', args):
                self.assertEqual(happ.main(), 0)
            with mock.patch.object(sys, 'argv', args + ['--check']):
                self.assertEqual(happ.main(), 0)
            (base / 'policy.json').write_text('{}')
            with mock.patch.object(sys, 'argv', args + ['--check']):
                self.assertEqual(happ.main(), 1)
            self.assertEqual((base / 'policy.json').read_text(), '{}')


if __name__ == '__main__':
    unittest.main()
