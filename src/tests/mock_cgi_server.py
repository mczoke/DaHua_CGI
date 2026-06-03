"""模拟 CGI 服务器，支持多场景测试

用法: 直接运行该脚本会启动 aiohttp server 在 127.0.0.1:8080
支持查询参数 ?scenario=xxx 切换不同行为
"""
import asyncio
import json
from aiohttp import web

NONCE = "abc123"
REALM = "testrealm"

SCENARIOS = {
    "success": {
        "status": 200,
        "body": "OK",
        "delay": 0,
    },
    "empty_response": {
        "status": 200,
        "body": "",
        "delay": 0,
    },
    "auth_failed": {
        "status": 401,
        "body": "Unauthorized",
        "delay": 0,
    },
    "not_found": {
        "status": 404,
        "body": "Not Found",
        "delay": 0,
    },
    "server_error": {
        "status": 500,
        "body": "Internal Server Error",
        "delay": 0,
    },
    "timeout": {
        "status": 200,
        "body": "OK",
        "delay": 15,  # 模拟超时场景
    },
    "slow": {
        "status": 200,
        "body": "OK",
        "delay": 3,
    },
    "bad_json": {
        "status": 200,
        "body": "{invalid json}",
        "delay": 0,
    },
    "partial_success": {
        "status": 200,
        "body": "Error: param1 failed\nOK\nError: param3 failed",
        "delay": 0,
    },
    "multi_device": {
        "status": 200,
        "body": "OK",
        "delay": 0.1,
    },
    "chunked": {
        "status": 200,
        "body": "OK\nOK\nOK",
        "delay": 0.1,
    },
}


async def handle_config(request):
    scenario_name = request.query.get("scenario", "success")
    scenario = SCENARIOS.get(scenario_name, SCENARIOS["success"])

    # 模拟延迟
    if scenario["delay"] > 0:
        await asyncio.sleep(scenario["delay"])

    auth = request.headers.get("Authorization")
    if scenario["status"] == 401:
        hdr = f'Digest realm="{REALM}", nonce="{NONCE}", qop="auth"'
        return web.Response(
            status=401,
            headers={"WWW-Authenticate": hdr},
            text=scenario["body"],
        )

    if auth or scenario_name in ("auth_failed",):
        return web.Response(
            status=scenario["status"],
            text=scenario["body"],
        )

    # 无 auth header 时发起 Digest 挑战
    hdr = f'Digest realm="{REALM}", nonce="{NONCE}", qop="auth"'
    return web.Response(
        status=401,
        headers={"WWW-Authenticate": hdr},
        text="Unauthorized",
    )


async def handle_status(request):
    """返回服务器状态"""
    return web.Response(
        status=200,
        content_type="application/json",
        text=json.dumps({"status": "running", "scenarios": list(SCENARIOS.keys())}),
    )


async def handle_reset(request):
    """重置计数器等状态"""
    return web.Response(status=200, text="reset ok")


app = web.Application()
app.router.add_get("/cgi-bin/configManager.cgi", handle_config)
app.router.add_get("/status", handle_status)
app.router.add_post("/reset", handle_reset)

if __name__ == "__main__":
    web.run_app(app, host="127.0.0.1", port=8080)
