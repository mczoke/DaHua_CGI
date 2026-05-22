"""简单的模拟 CGI 服务器，用于测试 Basic / Digest 行为。

用法: 直接运行该脚本会启动 aiohttp server 在 127.0.0.1:8080
"""
import asyncio
from aiohttp import web

NONCE = "abc123"
REALM = "testrealm"

async def handle_config(request):
    # 简单支持 Basic 或 Digest：
    auth = request.headers.get('Authorization')
    if auth:
        # 如果有 Authorization（Basic 或 Digest），视为通过
        return web.Response(text='OK', status=200)

    # 否则发起 Digest 挑战（客户端应重试）
    hdr = f'Digest realm="{REALM}", nonce="{NONCE}", qop="auth"'
    return web.Response(status=401, headers={'WWW-Authenticate': hdr}, text='Unauthorized')

app = web.Application()
app.router.add_get('/cgi-bin/configManager.cgi', handle_config)

if __name__ == '__main__':
    web.run_app(app, host='127.0.0.1', port=8080)
