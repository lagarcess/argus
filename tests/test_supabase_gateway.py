from types import SimpleNamespace
from unittest.mock import MagicMock

from argus.domain.supabase_gateway import SupabaseGateway


def test_batched_fetch_helper_exists_for_unbounded_queries():
    gateway = SupabaseGateway(client=MagicMock())
    assert hasattr(gateway, "_fetch_all_rows")


class _RecordingSupabaseClient:
    def __init__(self) -> None:
        self.inserted_message: dict[str, object] | None = None

    def table(self, table_name: str):
        return _RecordingTable(self, table_name)


class _RecordingTable:
    def __init__(self, client: _RecordingSupabaseClient, table_name: str) -> None:
        self.client = client
        self.table_name = table_name
        self.payload: dict[str, object] = {}

    def insert(self, payload: dict[str, object]):
        if self.table_name == "messages":
            self.client.inserted_message = payload
        self.payload = payload
        return self

    def update(self, payload: dict[str, object]):
        self.payload = payload
        return self

    def eq(self, *_args: object):
        return self

    def execute(self):
        if self.table_name == "messages":
            return SimpleNamespace(data=[{"id": "msg-1", **self.payload}])
        return SimpleNamespace(data=[self.payload])


def test_create_message_writes_empty_metadata_object_when_omitted():
    client = _RecordingSupabaseClient()
    gateway = SupabaseGateway(client=client)
    gateway.get_conversation = MagicMock(return_value=object())

    message = gateway.create_message(
        user_id="user-1",
        conversation_id="conversation-1",
        role="user",
        content="Backtest buying and holding Apple over the past year.",
    )

    assert client.inserted_message is not None
    assert client.inserted_message["metadata"] == {}
    assert message.metadata == {}


class _MockAuthAdmin:
    def get_user_by_email(self, _email: str) -> object:
        raise RuntimeError("fall back to profile lookup")

    def list_users(self, **_kwargs: object) -> object:
        raise RuntimeError("fall back to profile lookup")


class _MockAuth:
    admin = _MockAuthAdmin()


class _ExistingProfileClient:
    def __init__(self) -> None:
        self.auth = _MockAuth()
        self.upserted_profile: dict[str, object] | None = None
        self.profile = {
            "id": "user-1",
            "email": "developer@argus.local",
            "username": "mock-developer",
            "display_name": "Mock Developer",
            "language": "en",
            "locale": "en-US",
            "theme": "dark",
            "is_admin": True,
            "onboarding": {
                "completed": True,
                "stage": "completed",
                "language_confirmed": True,
                "primary_goal": "test_stock_idea",
            },
            "created_at": "2026-05-14T00:00:00+00:00",
            "updated_at": "2026-05-14T00:00:00+00:00",
        }

    def table(self, table_name: str):
        assert table_name == "profiles"
        return _ExistingProfileTable(self)


class _ExistingProfileTable:
    def __init__(self, client: _ExistingProfileClient) -> None:
        self.client = client
        self.selected = "*"

    def select(self, selected: str):
        self.selected = selected
        return self

    def eq(self, *_args: object):
        return self

    def limit(self, *_args: object):
        return self

    def single(self):
        return self

    def upsert(self, payload: dict[str, object], **_kwargs: object):
        self.client.upserted_profile = payload
        self.client.profile = {**self.client.profile, **payload}
        return self

    def execute(self):
        if self.selected == "id":
            return SimpleNamespace(data=[{"id": self.client.profile["id"]}])
        return SimpleNamespace(data=[self.client.profile])


def test_mock_user_lookup_preserves_existing_profile_onboarding():
    client = _ExistingProfileClient()
    gateway = SupabaseGateway(
        client=client,
        mock_user_email="developer@argus.local",
        mock_user_password="password",
    )

    user = gateway.get_or_create_mock_user()

    assert client.upserted_profile is None
    assert user.onboarding.completed is True
    assert user.onboarding.primary_goal == "test_stock_idea"
