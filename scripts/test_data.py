"""Owned local D1 fixtures. No remote flag, URL, SQL argument, or HTTP reset API.

prepare/reset operate only on one offline Wrangler namespace; serve holds a lock.
Use a distinct run-id and worker for concurrent processes. Fixture capabilities
are local-only and retained in an ignored manifest, never printed to stdout.
"""
import argparse
from contextlib import closing
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone

from qa_provenance import verified_build

ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = ROOT / '.sites-runtime' / 'test-data'
SCHEMA = 1


def namespace(run_id, worker):
    for value in (run_id, worker):
        if not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}', value):
            raise ValueError('Run and worker must be simple non-path identifiers.')
    path = DATA_ROOT / run_id / worker
    # Resolve against the repository itself, not a potentially redirected root.
    if not path.resolve().is_relative_to(ROOT.resolve() / '.sites-runtime' / 'test-data'):
        raise ValueError('Test namespace escapes the owned local root.')
    return path


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


@contextmanager
def exclusive(path):
    lock = path / 'operation.lock'
    fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    try:
        os.write(fd, str(os.getpid()).encode())
        os.close(fd)
        yield
    finally:
        lock.unlink(missing_ok=True)


def load_owned(path):
    manifest = json.loads((path / 'manifest.json').read_text())
    if manifest.get('schema') != SCHEMA or manifest.get('kind') != 'everyday-local-test-data':
        raise ValueError('Not an owned local test manifest.')
    if Path(manifest['namespace']).resolve() != path.resolve():
        raise ValueError('Manifest belongs to another namespace.')
    if manifest.get('environment') != 'local' or manifest['url'] != f"http://127.0.0.1:{manifest['port']}":
        raise ValueError('Only loopback local test data is permitted.')
    if not (path / 'storage').resolve().is_relative_to(path.resolve()):
        raise ValueError('Storage escapes the owned local worker.')
    if Path(manifest['persist_to']).resolve() != (path / 'storage').resolve():
        raise ValueError('Storage is outside its owned namespace.')
    database = Path(manifest['database']).resolve()
    if not database.is_relative_to((path / 'storage').resolve()) or not database.is_file():
        raise ValueError('Database is outside its owned namespace.')
    return manifest


def offline(port):
    # Refuse reset/seed whenever any listener uses this namespace's configured port.
    with socket.socket() as sock:
        try:
            sock.bind(('127.0.0.1', port))
        except OSError as error:
            raise ValueError('Stop the local test server before changing fixtures.') from error


def seed(database, run_id, worker, reset=False):
    token = hashlib.sha256(f'everyday-local:{run_id}:{worker}:standard'.encode()).hexdigest()
    empty_token = hashlib.sha256(f'everyday-local:{run_id}:{worker}:empty'.encode()).hexdigest()
    user = f'guest:{token}'
    with closing(sqlite3.connect(database)) as db, db:
        db.execute('PRAGMA foreign_keys=ON')
        if reset:
            for table in ('coupon_redemptions', 'checkout_requests', 'commerce_mutations',
                          'commerce_guards', 'orders', 'cart', 'cart_state', 'coupon_limits'):
                db.execute(f'DELETE FROM {table}')
        db.execute('INSERT OR IGNORE INTO cart(user,product,qty) VALUES(?,?,?)', (user, 46, 1))
        db.execute("INSERT OR IGNORE INTO coupon_limits(code,max_uses) VALUES('LIMITED20',5)")
    return {'standard_guest': {'cookie': token, 'product': 46, 'qty': 1},
            'empty_cart_guest': {'cookie': empty_token},
            'low_stock_product': {'product': 201, 'stock': 2},
            'out_of_stock_product': {'product': 202, 'stock': 0},
            'expired_coupon': {'code': 'EXPIRED10'},
            'service_failure': {'mode': 'browser-route-abort', 'path': '/api/cart'},
            'clock': {'mode': 'pure-domain-context', 'epoch': 1793145600000}}


def prepare(args, path):
    path.mkdir(parents=True, exist_ok=True)
    with exclusive(path):
        if (path / 'manifest.json').exists():
            old = load_owned(path)
            if old['port'] != args.port:
                raise ValueError('A namespace cannot change ports; use a new worker.')
        offline(args.port)
        if not (ROOT / 'dist/server/wrangler.json').exists():
            raise ValueError('Build the app before preparing test data.')
        storage = path / 'storage'
        if not storage.resolve().is_relative_to(path.resolve()):
            raise ValueError('Storage escapes the owned local worker.')
        sqlite_files = [p for p in storage.rglob('*.sqlite') if p.name != 'metadata.sqlite']
        if not sqlite_files:
            command = ['node', '--import', (ROOT / 'scripts/sites-env.mjs').as_uri(),
                       str(ROOT / 'node_modules/wrangler/bin/wrangler.js'), 'd1', 'execute', 'DB',
                       '--local', '--config', str(ROOT / 'dist/server/wrangler.json'),
                       '--persist-to', str(storage), '--command', 'SELECT 1']
            subprocess.run(command, cwd=ROOT, check=True, stdout=subprocess.DEVNULL)
            sqlite_files = [p for p in storage.rglob('*.sqlite') if p.name != 'metadata.sqlite']
        if len(sqlite_files) != 1:
            raise ValueError('Expected exactly one local D1 database.')
        database = sqlite_files[0].resolve()
        if not database.is_relative_to(path.resolve()):
            raise ValueError('Database is outside its namespace.')
        migrations = sorted((ROOT / 'drizzle').glob('*.sql'))
        with closing(sqlite3.connect(database)) as db, db:
            db.execute('CREATE TABLE IF NOT EXISTS _qa_migrations(name TEXT PRIMARY KEY,sha256 TEXT NOT NULL)')
            for migration in migrations:
                old = db.execute('SELECT sha256 FROM _qa_migrations WHERE name=?', (migration.name,)).fetchone()
                checksum = digest(migration)
                if old:
                    if old[0] != checksum:
                        raise ValueError('Previously applied migration changed.')
                    continue
                # Atomic even when a migration has multiple trigger statements.
                name = migration.name.replace("'", "''")
                db.executescript('BEGIN IMMEDIATE;\n' + migration.read_text(encoding='utf-8') +
                                 f"\nINSERT INTO _qa_migrations VALUES('{name}','{checksum}');\nCOMMIT;")
        fixtures = seed(database, args.run_id, args.worker)
        manifest = {'schema': SCHEMA, 'kind': 'everyday-local-test-data', 'environment': 'local',
                    'run_id': args.run_id, 'worker': args.worker, 'namespace': str(path.resolve()),
                    'persist_to': str(storage.resolve()), 'database': str(database),
                    'url': f'http://127.0.0.1:{args.port}', 'port': args.port, 'fixtures': fixtures,
                    'migrations': {p.name: digest(p) for p in migrations}}
        (path / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print(json.dumps({'manifest': str(path / 'manifest.json'), 'url': manifest['url']}))


def reset(args, path):
    manifest = load_owned(path)
    with exclusive(path):
        offline(manifest['port'])
        database = Path(manifest['database']).resolve()
        if not database.is_relative_to(path.resolve()) or not database.is_file():
            raise ValueError('Database is outside its owned namespace.')
        seed(database, args.run_id, args.worker, reset=True)
    print('Reset owned local worker fixtures.')


def serve(args, path):
    manifest = load_owned(path)
    provenance = verified_build()
    with exclusive(path):
        offline(manifest['port'])
        command = ['node', '--import', (ROOT / 'scripts/sites-env.mjs').as_uri(),
                   str(ROOT / 'node_modules/wrangler/bin/wrangler.js'), 'dev',
                   '--config', str(ROOT / 'dist/server/wrangler.json'), '--local',
                   '--persist-to', manifest['persist_to'], '--ip', '127.0.0.1',
                   '--port', str(manifest['port']), '--inspector-port', '0']
        process = subprocess.Popen(command, cwd=ROOT)
        (path / 'server.json').write_text(json.dumps({
            'url': manifest['url'], 'pid': process.pid, 'owner_pid': os.getpid(),
            'started_utc': datetime.now(timezone.utc).isoformat(),
            'config': str(ROOT / 'dist/server/wrangler.json'),
            'source_sha256': provenance['source']['sha256'],
            'build_sha256': provenance['build']['sha256'],
        }, indent=2), encoding='utf-8')
        try:
            return process.wait()
        except KeyboardInterrupt:
            process.terminate()
            process.wait(timeout=15)
            return 130


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare', 'reset', 'serve'))
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--worker', default='main')
    parser.add_argument('--port', type=int, default=8790)
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error('Use an unprivileged TCP port.')
    path = namespace(args.run_id, args.worker)
    return {'prepare': prepare, 'reset': reset, 'serve': serve}[args.action](args, path) or 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (ValueError, FileExistsError, FileNotFoundError) as error:
        print(f'BLOCKED: {error}', file=sys.stderr)
        sys.exit(2)
