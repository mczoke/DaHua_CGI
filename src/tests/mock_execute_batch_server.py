"""Mock CGI server for execute_batch integration tests.

Supports per-request scenarios via query parameter `scenario=xxx`.
Also tracks request count per scenario to allow sequential scenarios.
"""
import asyncio
import json
from aiohttp import web

REALM = "testrealm"
NONCE = "abc123"

# Track request counts for sequential scenario control
_request_counters: dict = {}
_request_counter_lock = asyncio.Lock()


async def _incr(key: str) -> int:
    async with _request_counter_lock:
        _request_counters[key] = _request_counters.get(key, 0) + 1
        return _request_counters[key]


def _get_count(key: str) -> int:
    return _request_counters.get(key, 0)


class ResponseSpec:
    """Defines how a mock request should respond."""
    def __init__(self, status=200, body="OK", delay=0, auth_challenge=True):
        self.status = status
        self.body = body
        self.delay = delay
        self.auth_challenge = auth_challenge


# Default scenario specs
SCENARIOS = {
    # 全成功
    "all_ok": ResponseSpec(200, "OK\nOK", 0),
    # 部分成功（混合返回）
    "partial_ok": ResponseSpec(200, "Error: param1 failed\nOK\nError: param3 failed", 0),
    # 401 未认证
    "auth_failed": ResponseSpec(401, "Unauthorized", 0),
    # 500 服务器错误
    "server_error": ResponseSpec(500, "Internal Server Error", 0),
    # 超时
    "timeout": ResponseSpec(200, "OK", 15),
    # 慢响应
    "slow": ResponseSpec(200, "OK", 3),
    # 空响应
    "empty": ResponseSpec(200, "", 0),
    # 成功
    "success": ResponseSpec(200, "OK", 0),
}


async def handle_config(request):
    scenario = request.query.get("scenario", "success")
    spec = SCENARIOS.get(scenario, SCENARIOS["success"])

    await _incr(scenario)

    if spec.delay > 0:
        await asyncio.sleep(spec.delay)

    # Check authorization for scenarios that need auth challenge
    auth = request.headers.get("Authorization", "")
    if spec.auth_challenge and not auth and spec.status == 401:
        hdr = f'Digest realm="{REALM}", nonce="{NONCE}", qop="auth"'
        return web.Response(status=401, headers={"WWW-Authenticate": hdr}, text="Unauthorized")

    return web.Response(status=spec.status, text=spec.body)


async def handle_reset(request):
    async with _request_counter_lock:
        _request_counters.clear()
    return web.Response(status=200, text="reset ok")


async def handle_status(request):
    async with _request_counter_lock:
        counters_snapshot = dict(_request_counters)
    return web.Response(
        status=200,
        content_type="application/json",
        text=json.dumps({"status": "running", "counters": counters_snapshot}),
    )


def create_app():
    app = web.Application()
    app.router.add_get("/cgi-bin/configManager.cgi", handle_config)
    app.router.add_get("/status", handle_status)
    app.router.add_post("/reset", handle_reset)
    return app


if __name__ == "__main__":
    web.run_app(create_app(), host="127.0.0.1", port=8080)
