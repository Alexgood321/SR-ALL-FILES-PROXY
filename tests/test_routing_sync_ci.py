import importlib.util
import subprocess
import tempfile
import unittest
import hashlib
import zipfile
import os
import sys
from unittest import mock
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('routing_sync_ci', ROOT / 'scripts/routing_sync_ci.py')
ci = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ci)


def git(root, *args):
    return subprocess.check_output(['git', '-C', str(root), *args], stderr=subprocess.STDOUT).decode().strip()


class PublicationTests(unittest.TestCase):
    def setUp(self):
        base = ROOT / '.ci-test-tmp'
        base.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=base)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.remote = self.root / 'remote.git'
        subprocess.run(['git', 'init', '--bare', '--initial-branch=main', str(self.remote)], check=True, capture_output=True)
        self.repo = self.root / 'repo'
        subprocess.run(['git', 'clone', str(self.remote), str(self.repo)], check=True, capture_output=True)
        git(self.repo, 'config', 'user.name', 'Fixture')
        git(self.repo, 'config', 'user.email', 'fixture@example.invalid')
        for target in ('incy', 'happ'):
            (self.repo / target).mkdir()
            for path in ci.artifact_paths(target):
                (self.repo / path).write_text('baseline')
        (self.repo / 'helper.py').write_text('trusted')
        git(self.repo, 'add', '.')
        git(self.repo, 'commit', '-m', 'baseline')
        git(self.repo, 'push', 'origin', 'HEAD:main')
        self.baseline = git(self.repo, 'rev-parse', 'HEAD')
        self.ready = []

    def validate(self, root, target, runtime, mode):
        for path in ci.artifact_paths(target):
            (root / path).write_text(target + ' generated')

    def publish(self, target, validate=None):
        return ci.publish_target(self.repo, target, self.root / 'runtime',
                                 validate=validate or self.validate,
                                 ready=lambda target, sha: self.ready.append((target, sha)))

    def test_independent_commits_and_exact_ready_sha(self):
        for target in ('incy', 'happ'):
            sha = self.publish(target)
            self.assertEqual(self.ready[-1], (target, sha))
            self.assertEqual(set(git(self.repo, 'show', '--pretty=', '--name-only', sha).splitlines()), set(ci.artifact_paths(target)))
        self.assertEqual(git(self.repo, 'status', '--porcelain'), '')

    def test_failed_stage_staged_index_does_not_pollute_other_target(self):
        def fail(root, target, runtime, mode):
            self.validate(root, target, runtime, mode)
            git(root, 'add', '--', *ci.artifact_paths(target))
            raise RuntimeError('fixture commit failure')
        with self.assertRaises(RuntimeError):
            self.publish('incy', fail)
        self.assertFalse(self.ready)
        self.publish('happ')
        self.assertEqual(self.ready[-1][0], 'happ')

    def test_unexpected_index_path_blocks_publication(self):
        def contaminated(root, target, runtime, mode):
            self.validate(root, target, runtime, mode)
            (root / 'helper.py').write_text('unreviewed')
            git(root, 'add', 'helper.py')
        with self.assertRaises(ci.CISafetyError):
            self.publish('incy', contaminated)
        self.assertFalse(self.ready)
        self.assertEqual(git(self.remote, 'rev-parse', 'main'), self.baseline)

    def test_non_force_retry_regenerates_after_data_only_remote_advance(self):
        count = []
        def race(root, target, runtime, mode):
            self.validate(root, target, runtime, mode)
            count.append(git(root, 'rev-parse', 'HEAD'))
            if len(count) == 1:
                (self.repo / 'incy/xray-conversion-report.md').write_text('other publisher')
                git(self.repo, 'add', 'incy/xray-conversion-report.md')
                git(self.repo, 'commit', '-m', 'concurrent artifact')
                git(self.repo, 'push', 'origin', 'HEAD:main')
        sha = self.publish('happ', race)
        self.assertEqual(len(count), 2)
        self.assertNotEqual(count[0], count[1])
        self.assertEqual(self.ready, [('happ', sha)])

    def test_protected_remote_advance_cannot_execute_new_helper(self):
        (self.repo / 'helper.py').write_text('unreviewed')
        git(self.repo, 'add', 'helper.py')
        git(self.repo, 'commit', '-m', 'unknown toolchain')
        git(self.repo, 'push', 'origin', 'HEAD:main')
        # Model an event checkout that predates the remote protected change.
        git(self.repo, 'checkout', '--detach', self.baseline)
        with self.assertRaises(ci.CISafetyError):
            self.publish('happ')
        self.assertFalse(self.ready)

    def test_no_change_ready_attaches_to_policy_touch_not_event_head(self):
        sha = self.publish('incy', lambda *_: None)
        self.assertEqual(sha, self.baseline)
        self.assertEqual(self.ready, [('incy', self.baseline)])

    def test_happ_failure_does_not_prevent_incy_publication(self):
        def fail(*_):
            raise RuntimeError('fixture HAPP validation failure')
        with self.assertRaises(RuntimeError):
            self.publish('happ', fail)
        self.publish('incy')
        self.assertEqual([target for target, _ in self.ready], ['incy'])

    def test_validation_modes_and_invalid_artifact_never_regenerate_first(self):
        real_run = subprocess.run
        for mode in ('source', 'artifact'):
            commands = []
            def run(args, **kwargs):
                if args[0] == 'git':
                    return real_run(args, **kwargs)
                commands.append(args)
            with mock.patch.object(ci, 'verify_xray'), mock.patch.object(ci.subprocess, 'run', run):
                ci.validate_target(self.repo, 'incy', self.root / 'runtime', mode)
            calls = [args for args in commands if 'scripts/generate_incy_xray_policy.py' in args]
            self.assertEqual('--check' in calls[0], mode == 'artifact')
            self.assertTrue(any('run' in args and '-test' in args for args in commands))
        def bad_artifact(args, **kwargs):
            if args[0] == 'git':
                return real_run(args, **kwargs)
            if 'scripts/generate_incy_xray_policy.py' in args:
                self.assertIn('--check', args)
                raise subprocess.CalledProcessError(1, args)
        with mock.patch.object(ci, 'verify_xray'), mock.patch.object(ci.subprocess, 'run', bad_artifact):
            with self.assertRaises(subprocess.CalledProcessError):
                ci.validate_target(self.repo, 'incy', self.root / 'runtime', 'artifact')

    def test_archive_pin_and_extracted_binary_are_both_verified(self):
        runtime = self.root / 'runtime'
        runtime.mkdir()
        archive = runtime / 'xray.zip'
        with zipfile.ZipFile(archive, 'w') as zipped:
            zipped.writestr('xray', b'fixture binary; not real Xray')
            zipped.writestr('geosite.dat', b'fixture asset')
        digest = hashlib.sha256(archive.read_bytes()).hexdigest()
        with mock.patch.object(ci, 'XRAY_SHA256', digest):
            ci.verify_xray(runtime, extract=True)
            ci.prepare_xray(runtime)  # Existing archive is still verified, not blindly trusted.
            ci.verify_xray(runtime)
            (runtime / 'xray/xray').write_bytes(b'contaminated stage output')
            with self.assertRaises(ci.CISafetyError):
                ci.verify_xray(runtime)
            archive.write_bytes(b'corrupt archive')
            with self.assertRaises(ci.CISafetyError):
                ci.verify_xray(runtime)

    def test_ready_client_uses_target_context_and_exact_artifact_revision(self):
        calls = []
        class Response:
            status = 201
            def __enter__(self): return self
            def __exit__(self, *_): return False
        def open_url(request, **kwargs):
            calls.append(request)
            return Response()
        with mock.patch.dict(os.environ, {'GITHUB_REPOSITORY': 'fixture/repo', 'GITHUB_TOKEN': 'fixture-only', 'GITHUB_RUN_ID': '123'}), mock.patch.object(ci.urllib.request, 'urlopen', open_url):
            import json
            for target in ('incy', 'happ'):
                ci.mark_ready(target, self.baseline)
                self.assertTrue(calls[-1].full_url.endswith('/statuses/' + self.baseline))
                self.assertEqual(json.loads(calls[-1].data)['context'], f'{target}/xray-policy-ready')
            Response.status = 500
            with self.assertRaises(ci.CISafetyError):
                ci.mark_ready('happ', self.baseline)

    def test_cli_modes_use_isolated_worktree_and_do_not_modify_checkout(self):
        runtime = self.root / 'runtime'
        with mock.patch.object(sys, 'argv', ['ci', '--runtime', str(runtime), '--prepare-xray']), mock.patch.object(ci, 'prepare_xray') as prepare:
            ci.main()
            prepare.assert_called_once_with(runtime)
        with mock.patch.object(sys, 'argv', ['ci', '--runtime', str(runtime)]):
            with self.assertRaises(SystemExit): ci.main()
        previous = Path.cwd()
        os.chdir(self.repo)
        try:
            with mock.patch.object(sys, 'argv', ['ci', '--runtime', str(runtime), '--target', 'happ', '--publish']), mock.patch.object(ci, 'publish_target') as publish:
                ci.main()
                publish.assert_called_once_with(self.repo, 'happ', runtime)
            with mock.patch.object(sys, 'argv', ['ci', '--runtime', str(runtime), '--target', 'incy', '--mode', 'artifact']), mock.patch.object(ci, 'validate_target', self.validate):
                ci.main()
            self.assertEqual(git(self.repo, 'status', '--porcelain'), '')
        finally:
            os.chdir(previous)


if __name__ == '__main__':
    unittest.main()
