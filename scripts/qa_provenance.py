"""Deterministic runtime input and build identities for local QA evidence."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def file_map(paths, root=ROOT):
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(paths) if p.is_file()}


def identity(files):
    return {'sha256': hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest(), 'files': files}


def runtime_inputs():
    paths = []
    for name in ('app', 'lib', 'db', 'drizzle', 'components', 'public'):
        paths += [p for p in (ROOT / name).rglob('*') if p.is_file()]
    paths += list((ROOT / 'scripts').glob('*.mjs'))
    paths += [ROOT / p for p in ('package.json', 'pnpm-lock.yaml', 'tsconfig.json',
                                 'vite.config.ts', '.openai/hosting.json')]
    return identity(file_map(paths))


def build_identity():
    return identity(file_map((ROOT / 'dist').rglob('*'), ROOT / 'dist'))


def verified_build():
    path = ROOT / '.sites-runtime/qa-build.json'
    if not path.is_file():
        raise ValueError('Build QA provenance first: python scripts/build_qa.py')
    record = json.loads(path.read_text(encoding='utf-8'))
    if record['source'] != runtime_inputs() or record['build'] != build_identity():
        raise ValueError('QA build or inputs changed; rerun python scripts/build_qa.py')
    return record
