"""Exercise local-data ownership, isolation and migration compatibility on real SQLite."""
import argparse
from contextlib import closing
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import socket
import sqlite3
import subprocess
import sys
import unittest
import uuid

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('data_tool', ROOT / 'scripts/test_data.py')
tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)


class DataContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.run_id = 'contracts-' + uuid.uuid4().hex[:10]
        cls.paths = []
        for worker in ('a', 'b'):
            with socket.socket() as sock:
                sock.bind(('127.0.0.1', 0))
                port = sock.getsockname()[1]
            args = argparse.Namespace(run_id=cls.run_id, worker=worker, port=port)
            path = tool.namespace(cls.run_id, worker)
            tool.prepare(args, path)
            cls.paths.append((args, path, tool.load_owned(path)))

    def test_path_traversal_rejected(self):
        for run, worker in (('../other', 'a'), ('ok', '../../b'), ('C:\\other', 'a'), ('ok', 'x/y')):
            with self.assertRaises(ValueError):
                tool.namespace(run, worker)

    def test_seed_idempotent(self):
        args, path, manifest = self.paths[0]
        with closing(sqlite3.connect(manifest['database'])) as db, db:
            before = db.execute('SELECT user,product,qty FROM cart ORDER BY user,product').fetchall()
        tool.prepare(args, path)
        with closing(sqlite3.connect(manifest['database'])) as db, db:
            self.assertEqual(before, db.execute('SELECT user,product,qty FROM cart ORDER BY user,product').fetchall())

    def test_worker_reset_isolation(self):
        args, path, first = self.paths[0]
        second = self.paths[1][2]
        self.assertNotEqual(first['database'], second['database'])
        self.assertNotEqual(first['fixtures']['standard_guest']['cookie'], second['fixtures']['standard_guest']['cookie'])
        with closing(sqlite3.connect(second['database'])) as db, db:
            db.execute("INSERT INTO cart(user,product,qty) VALUES('guest:isolated',201,2)")
        tool.reset(args, path)
        tool.reset(args, path)
        with closing(sqlite3.connect(second['database'])) as db, db:
            self.assertEqual(db.execute("SELECT qty FROM cart WHERE user='guest:isolated'").fetchone()[0], 2)
        with closing(sqlite3.connect(first['database'])) as db, db:
            self.assertEqual(db.execute('SELECT product,qty FROM cart').fetchall(), [(46, 1)])

    def test_active_port_blocks_reset(self):
        args, path, manifest = self.paths[0]
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', manifest['port']))
            sock.listen()
            with self.assertRaises(ValueError):
                tool.reset(args, path)

    def test_exclusive_lock_blocks_reset(self):
        args, path, _ = self.paths[0]
        with tool.exclusive(path):
            with self.assertRaises(FileExistsError):
                tool.reset(args, path)

    def test_external_database_manifest_rejected(self):
        _, path, manifest = self.paths[0]
        original = (path / 'manifest.json').read_bytes()
        try:
            (path / 'manifest.json').write_text(json.dumps({**manifest, 'database': str(ROOT / 'package.json')}))
            with self.assertRaises(ValueError):
                tool.load_owned(path)
        finally:
            (path / 'manifest.json').write_bytes(original)

    def test_storage_redirect_cannot_touch_another_worker(self):
        args, _, _ = self.paths[0]
        redirected = tool.namespace(self.run_id, 'redirected')
        redirected.mkdir()
        target = self.paths[1][1] / 'storage'
        if os.name == 'nt':
            subprocess.run(['cmd', '/c', 'mklink', '/J', str(redirected / 'storage'), str(target)],
                           check=True, capture_output=True)
        else:
            (redirected / 'storage').symlink_to(target, target_is_directory=True)
        with self.assertRaises(ValueError):
            tool.prepare(argparse.Namespace(run_id=self.run_id, worker='redirected', port=args.port), redirected)

    def test_migration_preserves_legacy_rows_and_repeat_history(self):
        _, path, manifest = self.paths[0]
        database = path / 'legacy-upgrade.sqlite'
        with closing(sqlite3.connect(database)) as db, db:
            db.executescript((ROOT / 'drizzle/0000_legal_the_twelve.sql').read_text())
            db.execute("INSERT INTO cart VALUES('legacy-guest',46,2)")
            db.execute("INSERT INTO orders VALUES('legacy-order','legacy-guest','[]',749,'{}')")
            db.commit()
            db.executescript((ROOT / 'drizzle/0001_resilient_commerce.sql').read_text())
            self.assertEqual(db.execute('SELECT * FROM cart').fetchall(), [('legacy-guest', 46, 2)])
            self.assertEqual(db.execute('SELECT id,total FROM orders').fetchall(), [('legacy-order', 749)])
        with closing(sqlite3.connect(manifest['database'])) as db, db:
            rows = db.execute('SELECT name,sha256 FROM _qa_migrations ORDER BY name').fetchall()
            self.assertEqual(dict(rows), manifest['migrations'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
