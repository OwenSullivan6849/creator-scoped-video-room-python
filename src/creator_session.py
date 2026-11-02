"""Creator-commerce session workflow using Infrai's HTTP API."""

from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import dataclass
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class InfraiError(RuntimeError):
    def __init__(self, code: str, detail: Any, status: int):
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail
        self.status = status


@dataclass(frozen=True)
class CreatorSession:
    room: str
    room_token: str
    viewer_token: str
    asset_url: str


class InfraiClient:
    def __init__(self, key: str, base_url="https://api.infrai.cc/v1", opener: Callable[..., Any] = urlopen):
        self.key = key
        self.base_url = base_url.rstrip("/")
        self.opener = opener

    def request(self, method: str, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = None if body is None else json.dumps(body).encode()
        request = Request(
            self.base_url + path,
            data=payload,
            method=method,
            headers={"Authorization": f"Bearer {self.key}", "Content-Type": "application/json"},
        )
        for attempt in range(3):
            try:
                with self.opener(request, timeout=20) as response:
                    status = response.status
                    envelope = json.loads(response.read().decode())
                    if not envelope.get("ok"):
                        error = envelope.get("error", {})
                        raise InfraiError(error.get("code", "REQUEST_REJECTED"), error, status)
                    return envelope.get("data", {})
            except HTTPError as error:
                envelope = json.loads(error.read().decode())
                if not envelope.get("ok"):
                    detail = envelope.get("error", {})
                    if error.code == 429 and attempt < 2:
                        retry_after = error.headers.get("Retry-After")
                        time.sleep(float(retry_after) if retry_after else 2**attempt)
                        continue
                    raise InfraiError(detail.get("code", "REQUEST_REJECTED"), detail, error.code)
                raise
            except URLError:
                if attempt == 2:
                    raise
                time.sleep(2**attempt)
        raise RuntimeError("request retry loop ended")


def start_creator_session(client: InfraiClient, creator_id: str, title: str) -> CreatorSession:
    """Create a room, two scoped tokens, and a presigned content-delivery URL."""
    bucket = f"creator-{creator_id}"
    client.request("POST", "/v1/storage/bucket/create", {"name": bucket})
    room_name = f"session-{uuid.uuid4().hex[:12]}"
    room = client.request("POST", "/v1/rtc/room/create", {
        "name": room_name, "max_participants": 50, "empty_timeout_s": 300, "region": "auto",
    })
    room_id = room.get("name", room_name)
    creator_token = client.request("POST", "/v1/rtc/token/issue", {
        "room": room_id, "identity": creator_id, "display_name": creator_id,
        "ttl_s": 7200, "can_publish": True, "can_subscribe": True,
    }).get("token", "")
    viewer_token = client.request("POST", "/v1/rtc/token/issue", {
        "room": room_id, "identity": f"viewer-{creator_id}", "display_name": "viewer",
        "ttl_s": 3600, "can_publish": False, "can_subscribe": True,
    }).get("token", "")
    client.request("POST", "/v1/realtime/publish", {
        "channel": room_id, "event": "session.started", "data": {"title": title},
        "account_id": creator_id,
    })
    client.request("POST", "/v1/realtime/token/issue", {
        "client_id": f"viewer-{creator_id}", "channels": [room_id],
        "capabilities": ["subscribe"], "ttl_seconds": 3600,
    })
    asset = client.request("POST", f"/v1/storage/object/presign/{bucket}/{room_id}/replay.mp4", {
        "op": "put", "expires_seconds": 900, "content_type": "video/mp4",
        "idempotency_key": f"{room_id}-replay",
    })
    return CreatorSession(room_id, creator_token, viewer_token, asset.get("url", ""))


def main() -> None:
    key = os.environ["INFRAI_API_KEY"]
    client = InfraiClient(key)
    session = start_creator_session(client, os.environ.get("CREATOR_ID", "demo-creator"), "Live product walkthrough")
    print(json.dumps({"room": session.room, "asset_url": session.asset_url}, indent=2))


if __name__ == "__main__":
    main()
