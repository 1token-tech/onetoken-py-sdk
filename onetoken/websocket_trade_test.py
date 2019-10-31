import asyncio

import aiohttp
import pytest
import yaml
from pathlib import Path


@pytest.mark.asyncio
async def test_trade_subscribe_success():
    import onetoken as ot
    ot.log.info('hello')
    r = Path('~/.onetoken/demo-vnpy.yml').expanduser().read_text()
    r = yaml.load(r)

    o = ot.Account('okex/mock-vnpy', api_key=r['ot_key'], api_secret=r['ot_secret'])

    async def h(*args, **kwargs):
        print(args, kwargs)

    await o.subscribe_info(h)
    await asyncio.sleep(5)
    o.close()
    await asyncio.sleep(2)


@pytest.mark.asyncio
async def test_trade_subscribe_fail():
    import onetoken as ot
    ot.log.info('hello')
    r = Path('~/.onetoken/demo-vnpy.yml').expanduser().read_text()
    r = yaml.load(r)

    o = ot.Account('okex/mock-vnpy', api_key=r['ot_key'], api_secret=r['ot_secret'] + 'fail')

    async def h(*args, **kwargs):
        print(args, kwargs)

    await o.subscribe_info(h)
    await asyncio.sleep(3)
    o.close()


@pytest.mark.asyncio
async def test_trade_noheader():
    import onetoken as ot
    ot.log.info('hello')
    r = Path('~/.onetoken/demo-vnpy.yml').expanduser().read_text()
    r = yaml.load(r)

    o = ot.Account('okex/mock-vnpy', api_key=r['ot_key'], api_secret=r['ot_secret'] + 'fail')

    url = o.ws_path
    ws = await o.session.ws_connect(url, autoping=False, headers=None, timeout=30)

    async def h():
        while True:
            msg = await ws.receive()
            if msg.type == aiohttp.WSMsgType.CLOSED:
                return
            print(msg)

    asyncio.ensure_future(h())
    await asyncio.sleep(3)
    await ws.close()
    o.close()
    await asyncio.sleep(0.1)
