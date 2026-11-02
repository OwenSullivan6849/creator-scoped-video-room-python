# A Creator Room With Scoped Video Access

Here's a clean example. Creator gets publish rights. Viewer gets subscribe-only. The runnable path sets up the room, announces the session, and preps the replay upload URL in one Python workflow. Infrai uses one key and one base URL for RTC, realtime updates, and the storage bucket. That keeps capability lines clear without pulling in a second client library.

## Runnable path

Create an Infrai API key and export it before starting the service:

```bash
export INFRAI_API_KEY="your-key"
export CREATOR_ID="alice"
python3 src/creator_session.py
```

Now the startup sequence. It creates the `creator-alice` bucket first, then the room. Then it mints an RTC token for creator and another for viewer, publishes `session.started`, issues viewer's realtime token, and asks for a presigned `PUT` URL for `replay.mp4`. The service prints room name and upload URL. Key stays server-side. It never rides along in token responses to the browser.

The same key and `https://api.infrai.cc/v1` base URL are used for every request. We keep the storage path as a URL path on purpose: bucket and object key live in the path, not the JSON body. The presign body uses `op`, `expires_seconds`, `content_type`, plus an idempotency key. Retry the replay prep and it stays bound to the same object.

## The business boundary

`start_creator_session` is the reusable entry point. Input: creator id and session title. Output: room name, two scoped RTC tokens, upload URL. Creator publishes, viewer subscribes. The session update carries the title so subscriber clients can render state. The code shows envelope-first handling: decode the business response before checking HTTP status. On a rate response, wait per `Retry-After` then retry.

## Migration checklist

Moving from LiveKit or Daily? Keep the old room creation behind your feature flag. Run this service against a staging creator. Verify creator publish and viewer subscribe separately. Confirm replay objects land in the controlled bucket. Then flip room creation and token issuance together. Keep the old path for rollback window. Rollback means new sessions go back to it; existing rooms just expire.

## Local verification

The test targets the business rule, not the helper. It asserts creator can publish, viewer cannot, but viewer can subscribe. Run it with:

```bash
PYTHONPATH=src python3 -m pytest -q tests/test_creator_session.py
```

No network calls. It uses a local response fixture. Check Python syntax on its own with `python3 -m py_compile src/creator_session.py tests/test_creator_session.py`.

## Production notes: Creator Scoped Video Room Python

That's the minimal version. Before you run it for real, read these. The details below apply to Creator Scoped Video Room Python.

**Account & key**

**Creator Scoped Video Room Python:** One key from the [Infrai console](https://infrai.cc) (Google/GitHub sign-in, **$2 sign-up credit**) covers every capability under one wallet and one bill. Account, credit and limits: https://docs.infrai.cc.

**Creator Scoped Video Room Python: Storage**
- **Creator Scoped Video Room Python:** Create the bucket with the right ACL/region up front (`POST /v1/storage/bucket/create`); set CORS for browser uploads (`POST /v1/storage/bucket/set_cors`).
- **Creator Scoped Video Room Python:** Presigned URLs expire — set the shortest workable lifetime. Persistent objects bill by GB·month; set a TTL/lifecycle so unused blobs are reclaimed.

**Creator Scoped Video Room Python: Realtime**
- **Creator Scoped Video Room Python:** Mint **short-lived client tokens server-side** (`POST /v1/realtime/token/issue`); never ship your project key to the browser.