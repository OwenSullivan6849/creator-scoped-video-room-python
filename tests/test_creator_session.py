import json
from creator_session import InfraiClient, start_creator_session


class FakeResponse:
    status = 200

    def __init__(self, data):
        self.data = json.dumps({"ok": True, "data": data}).encode()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return self.data


def test_creator_gets_publish_access_and_viewer_is_subscriber():
    calls = []
    responses = iter([{}, {"name": "room-1"}, {"token": "creator-token"}, {"token": "viewer-token"}, {}, {}, {"url": "https://upload.example/replay"}])

    def opener(request, timeout):
        calls.append((request.method, request.full_url, json.loads(request.data) if request.data else None))
        return FakeResponse(next(responses))

    session = start_creator_session(InfraiClient("test-key", opener=opener), "alice", "Demo")
    assert session.room == "room-1"
    creator_payload = calls[2][2]
    viewer_payload = calls[3][2]
    assert creator_payload["can_publish"] is True
    assert viewer_payload["can_publish"] is False
    assert viewer_payload["can_subscribe"] is True
    assert calls[0][0] == "POST"
    assert "/v1/storage/bucket/create" in calls[0][1]
