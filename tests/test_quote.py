import asyncio
import onetoken
import pytest


@pytest.mark.asyncio
async def test_go():
    q = onetoken.quote.Quote(ensure_connection=True)

    happen = False

    async def update(tk):
        nonlocal happen
        happen = True
        assert tk.contract == 'okef/btc.usd.q'

    await q.subscribe_tick('okef/btc.usd.q', on_update=update)
    for _ in range(5):
        await asyncio.sleep(1)
    await q.close()
    assert happen
# async def subscribe_tick(contract, on_update):
#     c = await get_client()
#     return await c.subscribe_tick(contract, on_update)
