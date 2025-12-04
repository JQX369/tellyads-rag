import pytest

pytest.importorskip("supabase")

from tvads_rag import supabase_db


class FakeResponse:
    def __init__(self, data=None):
        self.data = data or []


class FakeTable:
    def __init__(self):
        self.operations = []

    # Chainable query methods record their usage and return self.
    def select(self, *args, **kwargs):
        self.operations.append(("select", args, kwargs))
        return self

    def eq(self, *args, **kwargs):
        self.operations.append(("eq", args, kwargs))
        return self

    def limit(self, *args, **kwargs):
        self.operations.append(("limit", args, kwargs))
        return self

    def insert(self, rows):
        self.operations.append(("insert", (rows,), {}))
        return self

    def execute(self):
        # The specific FakeResponse is injected by the tests using monkeypatch.
        return FakeResponse()


class FakeClient:
    def __init__(self, table_response=None, rpc_response=None):
        self._table = FakeTable()
        self._table_response = table_response or []
        self._rpc_response = rpc_response or []

    def table(self, name):
        # Return a fresh table object whose execute() returns the configured data.
        table = FakeTable()

        def _exec():
            return FakeResponse(self._table_response)

        table.execute = _exec
        return table

    def rpc(self, fn_name, params):
        assert fn_name == "match_embedding_items_hybrid"

        class _RPC:
            def __init__(self, data):
                self._data = data

            def execute(self_inner):
                return FakeResponse(self._data)

        return _RPC(self._rpc_response)


def test_ad_exists_true_for_external_id(monkeypatch):
    fake_client = FakeClient(table_response=[{"id": "123"}])

    def fake_get_client():
        return fake_client

    monkeypatch.setattr(supabase_db, "_get_client", fake_get_client)

    assert supabase_db.ad_exists(external_id="TA100", s3_key=None) is True


def test_ad_exists_false_when_no_match(monkeypatch):
    fake_client = FakeClient(table_response=[])

    def fake_get_client():
        return fake_client

    monkeypatch.setattr(supabase_db, "_get_client", fake_get_client)

    assert supabase_db.ad_exists(external_id="TA100", s3_key=None) is False


def test_insert_embedding_items_sends_embedding_and_meta(monkeypatch):
    captured_rows = {}

    class InsertTable(FakeTable):
        def __init__(self, name):
            super().__init__()
            self.name = name

        def insert(self, rows):
            captured_rows[self.name] = rows
            return self

        def execute(self):
            # Return fake ids for each row
            return FakeResponse(
                [{"id": f"row-{i}"} for i, _ in enumerate(captured_rows[self.name])]
            )

    class ClientWithCapture(FakeClient):
        def table(self, name):
            return InsertTable(name)

    fake_client = ClientWithCapture()

    def fake_get_client():
        return fake_client

    monkeypatch.setattr(supabase_db, "_get_client", fake_get_client)

    items = [
        {
            "chunk_id": "c1",
            "segment_id": None,
            "claim_id": None,
            "super_id": None,
            "storyboard_id": None,
            "item_type": "transcript_chunk",
            "text": "hello world",
            "meta": {"foo": "bar"},
            "embedding": [0.1, 0.2, 0.3],
        }
    ]

    ids = supabase_db.insert_embedding_items("ad-1", items)
    assert ids == ["row-0"]
    assert "embedding_items" in captured_rows
    row = captured_rows["embedding_items"][0]
    assert row["ad_id"] == "ad-1"
    assert row["embedding"] == [0.1, 0.2, 0.3]
    assert row["meta"] == {"foo": "bar"}


def test_hybrid_search_calls_rpc(monkeypatch):
    fake_rows = [{"embedding_id": "abc"}]
    fake_client = FakeClient(rpc_response=fake_rows)

    def fake_get_client():
        return fake_client

    monkeypatch.setattr(supabase_db, "_get_client", fake_get_client)

    result = supabase_db.hybrid_search([0.1, 0.2], "brand offer", limit=5, item_types=["claim"])
    assert result == fake_rows









