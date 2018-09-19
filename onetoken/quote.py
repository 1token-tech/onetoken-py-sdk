import asyncio
from collections import defaultdict
import arrow
import aiohttp
import json

from .logger import log
from .model import Tick, Contract, Candle
from .config import Config


class Quote:
    def __init__(self, key, ws_url, data_parser):
        self.key = key
        self.ws_url = ws_url
        self.data_parser = data_parser
        self.sess = None
        self.ws = None
        self.queue_handlers = defaultdict(list)
        self.data_queue = {}
        self.connected = False
        self.authorized = False
        self.lock = asyncio.Lock()
        self.ensure_connection = True
        self.pong = 0
        self.task_list = []
        self.task_list.append(asyncio.ensure_future(self.ensure_connected()))
        self.task_list.append(asyncio.ensure_future(self.heart_beat_loop()))

    async def ensure_connected(self):
        log.debug('Connecting to {}'.format(self.ws_url))
        sleep_seconds = 2
        while self.ensure_connection:
            if not self.connected:
                try:
                    if self.sess and not self.sess.closed:
                        await self.sess.close()
                    self.sess = aiohttp.ClientSession()
                    self.ws = await self.sess.ws_connect(self.ws_url, autoping=False, timeout=30)
                    await self.ws.send_json({'uri': 'auth'})
                except Exception as e:
                    try:
                        await self.sess.close()
                    except:
                        log.exception('close session fail')
                    self.sess = None
                    self.ws = None
                    log.warning(f'try connect to {self.ws_url} failed, sleep for {sleep_seconds} seconds...', e)
                    await asyncio.sleep(sleep_seconds)
                    sleep_seconds = min(sleep_seconds * 2, 64)
                else:
                    log.debug('Connected to WS')
                    self.connected = True
                    sleep_seconds = 2
                    self.pong = arrow.now().timestamp
                    asyncio.ensure_future(self.on_msg())
                    wait_for_auth = 0
                    while not self.authorized and wait_for_auth < 5:
                        await asyncio.sleep(0.1)
                        wait_for_auth += 0.1
                    if wait_for_auth >= 5:
                        log.warning('wait for auth success timeout')
                        await self.ws.close()
                    async with self.lock:
                        q_keys = list(self.queue_handlers.keys())
                        if q_keys:
                            log.info('recover subscriptions', q_keys)
                            for q_key in q_keys:
                                sub_data = json.loads(q_key)
                                asyncio.ensure_future(self.subscribe_data(**sub_data))
            else:
                await asyncio.sleep(1)

    async def heart_beat_loop(self):
        while True:
            try:
                if self.ws and not self.ws.closed:
                    if arrow.now().timestamp - self.pong > 20:
                        log.warning('connection heart beat lost')
                        await self.ws.close()
                    else:
                        await self.ws.send_json({'uri': 'ping'})
            finally:
                await asyncio.sleep(5)

    async def on_msg(self):
        while not self.ws.closed:
            msg = await self.ws.receive()
            try:
                if msg.type == aiohttp.WSMsgType.BINARY or msg.type == aiohttp.WSMsgType.TEXT:
                    import gzip
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        data = json.loads(msg.data)
                    else:
                        data = json.loads(gzip.decompress(msg.data).decode())
                    if 'uri' in data:
                        if data['uri'] == 'pong':
                            self.pong = arrow.now().timestamp
                        elif data['uri'] == 'auth':
                            log.info(data)
                            self.authorized = True
                        else:
                            q_key, parsed_data = self.data_parser(data)
                            if q_key is None:
                                log.warning('unknown message', data)
                                continue
                            if q_key in self.data_queue:
                                self.data_queue[q_key].put_nowait(parsed_data)
                elif msg.type == aiohttp.WSMsgType.CLOSED:
                    log.warning('closed', msg)
                    break
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    log.warning('error', msg)
                    break
            except Exception as e:
                log.warning('msg error...', e)
        try:
            await self.ws.close()
        except:
            pass

        self.connected = False
        self.authorized = False
        log.warning('ws was disconnected...')

    async def subscribe_data(self, uri, on_update=None, **kwargs):
        log.info('subscribe', uri, **kwargs)
        while not self.connected or not self.authorized:
            await asyncio.sleep(1)
        sub_data = {'uri': uri}
        sub_data.update(kwargs)
        q_key = json.dumps(sub_data, sort_keys=True)
        async with self.lock:
            try:
                await self.ws.send_json(sub_data)
                print('sub data', sub_data)
                if q_key not in self.data_queue:
                    self.data_queue[q_key] = asyncio.Queue()
                    if on_update:
                        if not self.queue_handlers[q_key]:
                            asyncio.ensure_future(self.handle_q(q_key))
            except Exception as e:
                log.warning('subscribe {} failed...'.format(kwargs), e)
            else:
                if on_update:
                    self.queue_handlers[q_key].append(on_update)

    async def handle_q(self, q_key):
        while q_key in self.data_queue:
            q = self.data_queue[q_key]
            try:
                tk = await q.get()
            except:
                log.warning('get data from queue failed')
                continue
            for callback in self.queue_handlers[q_key]:
                if asyncio.iscoroutinefunction(callback):
                    await callback(tk)
                else:
                    callback(tk)

    async def close(self):
        self.ensure_connection = False
        for task in self.task_list:
            task.cancel()
        if self.sess:
            await self.sess.close()


class TickQuote(Quote):
    def __init__(self, key):
        super().__init__(key, Config.TICK_HOST_WS, self.parse_tick)
        self.channel = 'subscribe-single-tick-verbose'

    def parse_tick(self, data):
        try:
            tick = Tick.from_dict(data['data'])
            q_key = json.dumps({'contract': tick.contract, 'uri': self.channel}, sort_keys=True)
            return q_key, tick
        except Exception as e:
            log.warning('parse error', e)
        return None, None

    async def subscribe_tick(self, contract, on_update):
        await self.subscribe_data(self.channel, on_update=on_update, contract=contract)


class CandleQuote(Quote):
    def __init__(self, key):
        super().__init__(key, Config.CANDLE_HOST_WS, self.parse_candle)
        self.channel = 'subscribe-candle'
        self.authorized = True

    def parse_candle(self, data):
        try:
            candle = Candle.from_dict(data['data'])
            q_key = json.dumps({'contract': candle.contract, 'duration': candle.duration, 'uri': self.channel}, sort_keys=True)
            return q_key, candle
        except Exception as e:
            log.warning('parse error', e)
        return None, None

    async def subscribe_candle(self, contract, duration, on_update):
        await self.subscribe_data(self.channel, on_update=on_update, contract=contract, duration=duration)


_client_pool = {}


async def get_client(key='defalut'):
    if key in _client_pool:
        return _client_pool[key]
    else:
        c = TickQuote(key)
        _client_pool[key] = c
        return c


async def subscribe_tick(contract, on_update):
    c = await get_client()
    return await c.subscribe_tick(contract, on_update)


_candle_client_pool = {}


async def get_candle_client(key='defalut'):
    if key in _candle_client_pool:
        return _candle_client_pool[key]
    else:
        c = CandleQuote(key)
        _candle_client_pool[key] = c
        return c


async def subscribe_candle(contract, duration, on_update):
    c = await get_candle_client()
    return await c.subscribe_candle(contract, duration, on_update)


async def get_last_tick(contract):
    async with aiohttp.ClientSession() as sess:
        from . import autil
        res, err = await autil.http_go(sess.get, f'{Config.HOST_REST}/quote/single-tick/{contract}')
        if not err:
            res = Tick.from_dict(res)

        return res, err


async def get_contracts(exchange):
    async with aiohttp.ClientSession() as sess:
        from . import autil
        res, err = await autil.http_go(sess.get, f'{Config.HOST_REST}/basic/contracts?exchange={exchange}')
        if not err:
            cons = []
            for x in res:
                con = Contract.from_dict(x)
                cons.append(con)
            return cons, err
        return res, err


async def get_contract(symbol):
    exchange, name = symbol.split('/')
    async with aiohttp.ClientSession() as sess:
        from . import autil
        res, err = await autil.http_go(sess.get, f'{Config.HOST_REST}/basic/contracts?exchange={exchange}&name={name}')
        if not err:
            if not res:
                return None, 'contract-not-exist'
            con = Contract.from_dict(res[0])
            return con, err
        return res, err
