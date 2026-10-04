"""agent_lab/runtime.py — our `stream_discovery` for the lab-bridge (WS /ws/explore, mode "live").

Ships into the bridge repo unchanged. It is a thin client of the Pivot Gateway: it starts an
exploration, follows its SSE and yields bridge contract events. No bridge endpoint, contract or
viewer code changes.

Env on the bridge app:
  PIVOT_GATEWAY_URL   e.g. https://pivot-gateway-7474660394752821.aws.databricksapps.com
  Databricks Apps injects DATABRICKS_HOST / DATABRICKS_CLIENT_ID / DATABRICKS_CLIENT_SECRET
  (the bridge app's service principal, which needs CAN_USE on the Gateway app).
  PIVOT_GATEWAY_DEV_TOKEN  local development only.
"""

from __future__ import annotations

import json
import os
import time
from typing import Any, AsyncIterator

import httpx

try:  # the bridge's single source of truth for event shapes
    from ar_vr_bridge import contract as _contract
except ImportError:  # running outside the bridge (tests): yield plain dicts
    _contract = None

# The bridge falls back to its simulator (and says so to the viewer) when importing this module
# raises ImportError. Without a Gateway to talk to, keep that fallback instead of failing live runs.
if not os.environ.get("PIVOT_GATEWAY_URL"):
    raise ImportError("PIVOT_GATEWAY_URL is not set: the bridge keeps its simulator")

_TIMEOUT = httpx.Timeout(connect=10.0, read=120.0, write=10.0, pool=10.0)
_token_cache: dict[str, Any] = {"token": None, "exp": 0.0}


async def _auth_header(client: httpx.AsyncClient) -> dict[str, str]:
    dev = os.environ.get("PIVOT_GATEWAY_DEV_TOKEN")
    if dev:
        return {"Authorization": f"Bearer {dev}"}
    if _token_cache["token"] and time.time() < _token_cache["exp"] - 60:
        return {"Authorization": f"Bearer {_token_cache['token']}"}
    host = os.environ["DATABRICKS_HOST"]
    host = host if host.startswith("http") else f"https://{host}"
    resp = await client.post(
        f"{host.rstrip('/')}/oidc/v1/token",
        data={"grant_type": "client_credentials", "scope": "all-apis"},
        auth=(os.environ["DATABRICKS_CLIENT_ID"], os.environ["DATABRICKS_CLIENT_SECRET"]),
    )
    resp.raise_for_status()
    body = resp.json()
    _token_cache.update(token=body["access_token"], exp=time.time() + float(body.get("expires_in", 3600)))
    return {"Authorization": f"Bearer {body['access_token']}"}


def _event_classes() -> dict[str, Any]:
    """Map `event` name → contract class, by reading each pydantic model's `event` default."""
    if _contract is None:
        return {}
    out = {}
    for obj in vars(_contract).values():
        fields = getattr(obj, "model_fields", None)
        if isinstance(fields, dict) and "event" in fields and isinstance(fields["event"].default, str):
            out[fields["event"].default] = obj
    return out


_CLASSES = _event_classes()


def to_contract(payload: dict) -> Any:
    cls = _CLASSES.get(payload.get("event"))
    if cls is None:
        return payload
    return cls.model_validate(payload)


async def _sse(response: httpx.Response) -> AsyncIterator[dict]:
    data: list[str] = []
    async for line in response.aiter_lines():
        if line.startswith("data:"):
            data.append(line[5:].lstrip())
        elif line == "" and data:
            yield json.loads("\n".join(data))
            data = []


async def stream_discovery(query: str, query_id: str) -> AsyncIterator[Any]:
    base = os.environ["PIVOT_GATEWAY_URL"].rstrip("/")
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            headers = await _auth_header(client)
            resp = await client.post(f"{base}/api/v1/explorations",
                                     json={"query": query, "exploration_id": query_id}, headers=headers)
            resp.raise_for_status()
            events_url = f"{base}{resp.json()['events']}"
            async with client.stream("GET", events_url, headers=headers) as stream:
                stream.raise_for_status()
                async for payload in _sse(stream):
                    payload["query_id"] = query_id
                    yield to_contract(payload)
                    if payload.get("event") in ("done", "error"):
                        return
    except Exception as exc:  # noqa: BLE001
        # The bridge's WebSocket loop does not catch: an exception here drops the viewer's socket
        # with nothing shown. Report it as the contract's error event instead.
        yield to_contract({"event": "error", "query_id": query_id,
                           "message": f"agent lab unavailable: {type(exc).__name__}: {exc}"[:500]})
