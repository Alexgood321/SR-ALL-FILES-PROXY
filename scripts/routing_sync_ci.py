"""Small shared CI harness; existing generators remain the policy authority.

One publisher workflow calls this once per target. No daemon, cache or new
policy format. The event checkout supplies the reviewed implementation;
fresh main may differ only in the seven canonical/generated data blobs.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import urllib.request
import zipfile

XRAY_VERSION = 'v26.10.21'
XRAY_SHA256 = '0eec3ed4163c273d8c8bf821f7d219e257921cf584aa3fb970715e458e631978'
DATA_PATHS = {
    'config/remote.conf', 'modules/Unified-Routing-System-DNS.sgmodule',
    'modules/Ads-Privacy-Block.sgmodule', 'incy/xray-policy.json',
    'incy/xray-conversion-report.md', 'happ/xray-policy.json',
    'happ/xray-conversion-report.md',
}


class CISafetyError(RuntimeError):
    pass


def artifact_paths(target):
    if target not in ('incy', 'happ'):
        raise CISafetyError('unknown target')
    return (f'{target}/xray-policy.json', f'{target}/xray-conversion-report.md')


def git(root, *args):
    return subprocess.check_output(['git', '-C', str(root), *args], stderr=subprocess.PIPE)


def protected_tree(root, revision):
    result = {}
    for row in git(root, 'ls-tree', '-r', '-t', '-z', revision).split(b'\0'):
        if not row:
            continue
        metadata, raw_path = row.split(b'\t', 1)
        mode, kind, sha = metadata.decode().split()
        path = raw_path.decode()
        # Keep structural entries; only unchanged directory identity drops OID.
        result[path] = (mode, kind, None if kind == 'tree' or
                        (path in DATA_PATHS and mode == '100644' and kind == 'blob') else sha)
    return result


def _paths(raw):
    return {path.decode() for path in raw.split(b'\0') if path}


def guard_scope(root, target):
    changed = (_paths(git(root, 'diff', '--name-only', '-z')) |
               _paths(git(root, 'diff', '--cached', '--name-only', '-z')) |
               _paths(git(root, 'ls-files', '--others', '--exclude-standard', '-z')))
    if changed - set(artifact_paths(target)):
        raise CISafetyError('generator/index changed paths outside target allowlist')
    return changed


def prepare_xray(runtime):
    runtime.mkdir(parents=True, exist_ok=True)
    archive = runtime / 'xray.zip'
    if not archive.exists():
        urllib.request.urlretrieve(
            f'https://github.com/XTLS/Xray-core/releases/download/{XRAY_VERSION}/Xray-linux-64.zip', archive)
    verify_xray(runtime, extract=True)


def verify_xray(runtime, *, extract=False):
    archive = runtime / 'xray.zip'
    if hashlib.sha256(archive.read_bytes()).hexdigest() != XRAY_SHA256:
        raise CISafetyError('pinned Xray archive digest mismatch')
    destination = runtime / 'xray'
    destination.mkdir(exist_ok=True)
    with zipfile.ZipFile(archive) as zipped:
        for item in zipped.infolist():
            name = Path(item.filename)
            if name.is_absolute() or '..' in name.parts or len(name.parts) != 1 or item.is_dir():
                raise CISafetyError('unexpected Xray archive entry')
            expected = zipped.read(item)
            path = destination / name
            if path.is_symlink():
                raise CISafetyError('unsafe Xray runtime path')
            if extract:
                path.write_bytes(expected)
            elif not path.is_file() or hashlib.sha256(path.read_bytes()).digest() != hashlib.sha256(expected).digest():
                raise CISafetyError('Xray runtime content changed')
    if extract:
        (destination / 'xray').chmod(0o755)


def validate_target(root, target, runtime, mode):
    """Source mode regenerates; artifact mode checks ORIGINAL bytes first."""
    artifact_paths(target)
    if mode not in ('source', 'artifact'):
        raise CISafetyError('unknown validation mode')
    verify_xray(runtime)
    env = dict(os.environ)
    for key in ('GITHUB_TOKEN', 'GH_TOKEN', 'GITHUB_ENV', 'GITHUB_PATH', 'GITHUB_OUTPUT', 'GITHUB_STATE'):
        env.pop(key, None)
    output = root / '.routing-validation'
    output.mkdir()
    env['TMPDIR'] = str(output)
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    env['XRAY_LOCATION_ASSET'] = str(runtime / 'xray')
    def run(*args):
        subprocess.run(args, cwd=root, env=env, check=True)
    generator = f'scripts/generate_{target}_xray_policy.py'
    try:
        run(sys.executable, 'scripts/validate_shadowrocket.py')
        if mode == 'source':
            run(sys.executable, generator)
        run(sys.executable, generator, '--check')
        run(sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-p', f'test_{target}_xray_policy.py', '-v')
        run(sys.executable, generator, '--check', '--write-validation-config', str(output / 'config.json'))
        verify_xray(runtime)  # Never run a binary modified by generator/tests.
        run(str(runtime / 'xray/xray'), 'run', '-test', '-c', str(output / 'config.json'))
    finally:
        # Exactly our own generated validation file/directory, not broad rm.
        (output / 'config.json').unlink(missing_ok=True)
        output.rmdir()
    guard_scope(root, target)


def mark_ready(target, sha):
    repository = os.environ['GITHUB_REPOSITORY']
    payload = json.dumps({'state': 'success', 'context': f'{target}/xray-policy-ready',
                          'description': f'Validated generated {target.upper()} Xray policy',
                          'target_url': f'https://github.com/{repository}/actions/runs/{os.environ["GITHUB_RUN_ID"]}'}).encode()
    request = urllib.request.Request(f'https://api.github.com/repos/{repository}/statuses/{sha}',
                                    data=payload, headers={'Authorization': 'Bearer ' + os.environ['GITHUB_TOKEN'],
                                    'Accept': 'application/vnd.github+json'}, method='POST')
    with urllib.request.urlopen(request, timeout=20) as response:
        if response.status != 201:
            raise CISafetyError('READY publication failed')


def publish_target(repo, target, runtime, *, validate=validate_target, ready=mark_ready):
    allowed = set(artifact_paths(target))
    event = git(repo, 'rev-parse', 'HEAD').decode().strip()
    trusted = protected_tree(repo, event)
    runtime.mkdir(parents=True, exist_ok=True)
    for _ in range(3):
        git(repo, 'fetch', '--no-tags', 'origin', 'main')
        base = git(repo, 'rev-parse', 'FETCH_HEAD').decode().strip()
        if protected_tree(repo, base) != trusted:
            raise CISafetyError('main executable inputs differ from reviewed event')
        with tempfile.TemporaryDirectory(prefix=f'{target}-', dir=runtime) as directory:
            worktree = Path(directory) / 'worktree'
            git(repo, 'worktree', 'add', '--detach', str(worktree), base)
            try:
                if git(worktree, 'status', '--porcelain'):
                    raise CISafetyError('new target worktree not clean')
                validate(worktree, target, runtime, 'source')
                changed = guard_scope(worktree, target)
                if not changed:
                    sha = git(worktree, 'log', '-1', '--format=%H', '--', f'{target}/xray-policy.json').decode().strip()
                    if not sha:
                        raise CISafetyError('no existing artifact commit')
                    ready(target, sha)
                    return sha
                git(worktree, 'add', '--', *artifact_paths(target))
                cached = _paths(git(worktree, 'diff', '--cached', '--name-only', '-z'))
                if not cached or cached - allowed:
                    raise CISafetyError('invalid staged target publication')
                git(worktree, '-c', 'user.name=github-actions[bot]', '-c', 'user.email=41898282+github-actions[bot]@users.noreply.github.com',
                    'commit', '-m', f'Sync generated {target.upper()} Xray policy')
                sha = git(worktree, 'rev-parse', 'HEAD').decode().strip()
                if git(worktree, 'rev-parse', 'HEAD^').decode().strip() != base:
                    raise CISafetyError('unexpected artifact parent')
                actual = _paths(git(worktree, 'diff-tree', '--no-commit-id', '--name-only', '-r', '-z', sha))
                if not actual or actual - allowed or protected_tree(worktree, sha) != trusted:
                    raise CISafetyError('actual commit outside publication scope')
                try:
                    git(worktree, 'push', 'origin', 'HEAD:main')
                except subprocess.CalledProcessError:
                    # No force/rebase; next attempt gets a new worktree/index and validates again.
                    continue
                ready(target, sha)
                return sha
            finally:
                git(repo, 'worktree', 'remove', '--force', str(worktree))
    raise CISafetyError('three non-force publication attempts exhausted')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target', choices=('incy', 'happ'))
    parser.add_argument('--runtime', required=True, type=Path)
    parser.add_argument('--prepare-xray', action='store_true')
    parser.add_argument('--publish', action='store_true')
    parser.add_argument('--mode', choices=('source', 'artifact'), default='source')
    args = parser.parse_args()
    if args.prepare_xray:
        prepare_xray(args.runtime)
    elif args.target is None:
        parser.error('--target required')
    elif args.publish:
        publish_target(Path.cwd(), args.target, args.runtime)
    else:
        repo = Path.cwd()
        args.runtime.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=args.target + '-validate-', dir=args.runtime) as directory:
            worktree = Path(directory) / 'worktree'
            git(repo, 'worktree', 'add', '--detach', str(worktree), 'HEAD')
            try:
                validate_target(worktree, args.target, args.runtime, args.mode)
            finally:
                git(repo, 'worktree', 'remove', '--force', str(worktree))


if __name__ == '__main__':
    main()
