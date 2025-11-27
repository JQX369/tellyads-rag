from contextlib import contextmanager

import pytest

pytest.importorskip("psycopg2")

from tvads_rag import db


class FakeCursor:
    def __init__(self, rows):
        self.rows = rows
        self.sql = None
        self.params = None

    def execute(self, sql, params):
        self.sql = sql
        self.params = params

    def fetchall(self):
        return self.rows

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class FakeConnection:
    def __init__(self, cursor):
        self._cursor = cursor

    def cursor(self):
        return self._cursor


def test_hybrid_search_calls_rpc(monkeypatch):
    rows = [{"embedding_id": "abc"}]
    cursor = FakeCursor(rows)
    conn = FakeConnection(cursor)

    @contextmanager
    def fake_get_connection():
        yield conn

    monkeypatch.setattr(db, "get_connection", fake_get_connection)

    result = db.hybrid_search([0.1, 0.2], "brand offer", limit=5, item_types=["claim"])

    assert result == rows
    assert "match_embedding_items_hybrid" in cursor.sql
    assert cursor.params[0].startswith("[0.1")
    assert cursor.params[2] == 5
    assert cursor.params[3] == ["claim"]

