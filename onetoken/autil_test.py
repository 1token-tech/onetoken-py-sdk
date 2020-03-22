import aiohttp
import pytest


@pytest.mark.asyncio
async def test_http():
    from . import autil
    async with aiohttp.ClientSession() as sess:
        # res, err = await autil.http_go(sess.get, url='https://httpbin.org/delay/3', timeout=2)
        # print(res)
        # print(err)
        res, err = await autil.http_go(sess.get, url='http://localhost:3000/stream-html', timeout=20)
        print(res)
        print(err)

        res, err = await autil.http_go(sess.get, url='http://localhost:3000/stream-html', timeout=5)
        print(res)
        print(err)
