import asyncio
import hashlib

import arrow
import pytest

import onetoken


@pytest.mark.asyncio
async def test_tick_quote():
    q = await onetoken.quote.get_client()

    happen = False

    async def update(tk):
        nonlocal happen
        happen = True
        assert tk.contract == 'kucoin/eos.usdt'
        print('tick updated')

    await q.subscribe_tick('kucoin/eos.usdt', on_update=update)
    for _ in range(3):
        await asyncio.sleep(1)
    await q.close()
    assert happen


@pytest.mark.asyncio
async def test_tick_v3_quote():
    happen = False
    last = None

    async def update(tk: onetoken.Tick):
        nonlocal happen, last
        assert tk.contract == 'okef/btc.usd.q'
        if last == tk.time:
            print('same time', tk, hashlib.md5(str(tk.bids).encode()), hashlib.md5(str(tk.asks).encode()))
        last = tk.time
        if not happen:
            print('tick updated', arrow.get(tk.time).to('PRC').time(),
                  arrow.get(tk.exchange_time).to('PRC').time(), tk.asks[0],
                  tk.bids[0], len(tk.asks), len(tk.bids))
        happen = True

    await onetoken.quote.subscribe_tick_v3('okef/btc.usd.q', on_update=update)
    for _ in range(3):
        await asyncio.sleep(1)
    assert happen


@pytest.mark.asyncio
async def test_candle_quote():
    happen = False

    async def update(candle):
        nonlocal happen
        happen = True
        assert candle.contract == 'okef/btc.usd.q'
        assert candle.duration == '1m'
        print('candle updated')

    await onetoken.quote.subscribe_candle('okef/btc.usd.q', '1m', on_update=update)
    await onetoken.quote.subscribe_candle('okef/btc.usd.q', '1m', on_update=update)
    for _ in range(3):
        await asyncio.sleep(1)
    assert happen


if __name__ == "__main__":
    asyncio.ensure_future(test_tick_v3_quote())
    # asyncio.ensure_future(test_candle_quote())
    asyncio.get_event_loop().run_forever()
