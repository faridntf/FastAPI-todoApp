"""Opt-in real PostgreSQL concurrency tests in a disposable, isolated schema.

Run with RUN_POSTGRES_AUTH_TESTS=1; uses the configured PostgreSQL server.
No application tables or existing users are modified.
"""
import os
import sys
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text, select
from sqlalchemy.orm import Session
from core import Base, setting, get_db
from users.userRouter import router
from users.models import AuthSession, RefreshCredential
import tasks.models
import categories.models


@unittest.skipUnless(os.getenv("RUN_POSTGRES_AUTH_TESTS") == "1", "Opt-in PostgreSQL tests")
class PostgresConcurrencyTest(unittest.TestCase):
    def setUp(self):
        self.schema = "auth_test_" + uuid4().hex
        self.admin = create_engine(setting.SQLALCHEMY_POSTGRES_DATABASE_URL)
        with self.admin.begin() as conn:
            conn.execute(text('CREATE SCHEMA "' + self.schema + '"'))
        self.engine = create_engine(setting.SQLALCHEMY_POSTGRES_DATABASE_URL,
                                    connect_args={"options": "-csearch_path=" + self.schema})
        Base.metadata.create_all(self.engine)
        self.app = FastAPI()
        self.app.include_router(router)
        def database():
            with Session(self.engine) as db:
                yield db
        self.app.dependency_overrides[get_db] = database
        with TestClient(self.app, base_url="https://testserver") as client:
            result = client.post("/users/register", json={"username":"RaceUser", "email":"race@example.com",
                                "password":"Example123", "re_password":"Example123"})
            self.assertEqual(result.status_code, 201, result.text)

    def tearDown(self):
        self.engine.dispose()
        assert self.schema.startswith("auth_test_") and self.schema[10:].isalnum()
        with self.admin.begin() as conn:
            conn.execute(text('DROP SCHEMA "' + self.schema + '" CASCADE'))
        self.admin.dispose()

    def parallel(self, operation):
        barrier = Barrier(2)
        def run():
            with TestClient(self.app, base_url="https://testserver") as client:
                barrier.wait(timeout=10)
                return operation(client)
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(run) for _ in range(2)]
            return [future.result(timeout=30) for future in futures]

    def test_two_simultaneous_logins_only_one_succeeds(self):
        results = self.parallel(lambda client: client.post("/users/login", data={"username":"RaceUser", "password":"Example123"}))
        self.assertEqual(sorted(r.status_code for r in results), [200,409])
        with Session(self.engine) as db:
            self.assertEqual(len(db.scalars(select(AuthSession).where(AuthSession.revoked_at.is_(None))).all()), 1)
            self.assertEqual(len(db.scalars(select(RefreshCredential)).all()), 1)

    def test_two_simultaneous_refreshes_detect_replay(self):
        with TestClient(self.app, base_url="https://testserver") as client:
            tokens = client.post("/users/login", data={"username":"RaceUser", "password":"Example123"}).json()
        results = self.parallel(lambda client: client.post("/users/token/refresh", json={"refresh_token":tokens["refresh_token"]}))
        self.assertEqual(sorted(r.status_code for r in results), [200,401])
        with Session(self.engine) as db:
            self.assertIsNotNone(db.scalar(select(AuthSession)).revoked_at)
            self.assertEqual(len(db.scalars(select(RefreshCredential)).all()), 2)

    def test_migration_upgrade_and_downgrade(self):
        import importlib.util
        from alembic.migration import MigrationContext
        from alembic.operations import Operations
        path = Path(__file__).resolve().parents[1]/"src/migrations/versions/a8c193d5e270_add_auth_sessions.py"
        spec = importlib.util.spec_from_file_location("auth_migration", path)
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)
        with self.engine.begin() as conn:
            with Operations.context(MigrationContext.configure(conn)):
                migration.downgrade()
                migration.upgrade()
            conn.execute(select(AuthSession)).all()
            conn.execute(select(RefreshCredential)).all()


if __name__ == "__main__":
    unittest.main()
