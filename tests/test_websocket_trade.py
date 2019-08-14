import asyncio
from pathlib import Path

import aiohttp
import pytest
import yaml

from onetoken.account import gen_nonce, gen_sign


@pytest.mark.asyncio
async def test_trade_subscribe():
    import onetoken as ot
    ot.log.info('hello')
    r = Path('~/.onetoken/demo-vnpy.yml').expanduser().read_text()
    r = yaml.load(r)

    o = ot.Account('okex/mock-vnpy', api_key=r['ot_key'], api_secret=r['ot_secret'])

    async def h(*args, **kwargs):
        print(args, kwargs)

    await o.subscribe_info(h)
    await asyncio.sleep(10)


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
    await asyncio.sleep(10)


@pytest.mark.asyncio
async def test_trade_noheader():
    import onetoken as ot
    ot.log.info('hello')
    r = Path('~/.onetoken/demo-vnpy.yml').expanduser().read_text()
    r = yaml.load(r)

    o = ot.Account('okex/mock-vnpy', api_key=r['ot_key'], api_secret=r['ot_secret'] + 'fail')

    nonce = gen_nonce()
    sign = gen_sign(o.api_secret, 'GET', f'/ws/{o.name}', nonce, None)
    # headers = {'Api-Nonce': str(nonce), 'Api-Key': o.api_key, 'Api-Signature': sign}
    url = o.ws_path
    ws = await o.session.ws_connect(url, autoping=False, headers=None, timeout=30)

    async def h():
        while True:
            msg = await ws.receive()
            if msg.type == aiohttp.WSMsgType.CLOSED:
                return
            print(msg)

    asyncio.ensure_future(h())
    await asyncio.sleep(10)


if __name__ == '__main__':
    asyncio.get_event_loop().run_until_complete(test_trade_subscribe())
    asyncio.get_event_loop().run_forever()
