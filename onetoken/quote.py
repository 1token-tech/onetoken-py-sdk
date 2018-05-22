import asyncio
from collections import defaultdict
import arrow
import aiohttp
import json

from .logger import log
from .model import Tick, Contract

HOST = 'wss://api.1token.trade/v1/ws/tick'
ALT_HOST = 'wss://1token.trade/api/v1/ws/tick'  # 连接api.1token.trade遇到ssl证书问题，可以切换至此备用API HOST

REST_HOST = 'https://api.1token.trade/v1'
ALT_REST_HOST = 'https://1token.trade/api/v1'  # 连接api.1token.trade遇到ssl证书问题，可以切换至此备用API HOST


class Quote:
    def __init__(self, key=None, ensure_connection=True):
        self.key = key
        self.sess = None
        self.ws = None
        self.last_tick_dict = {}
        self.tick_queue_update = defaultdict(list)
        self.tick_queue = {}
        self.connected = False
        self.lock = asyncio.Lock()
        self.ensure_connection = ensure_connection
        self.pong = 0
        self.task_list = []
        self.task_list.append(asyncio.ensure_future(self.ensure_connected()))
        self.task_list.append(asyncio.ensure_future(self.heart_beat_loop()))

    async def ensure_connected(self):
        log.debug('Connecting to {}'.format(HOST))
        sleep_seconds = 2
        while self.ensure_connection:
            if not self.connected:
                try:
                    self.sess = aiohttp.ClientSession()
                    self.ws = await self.sess.ws_connect(HOST + '?gzip=true', autoping=False, timeout=30)
                    await self.ws.send_json({'uri': 'auth', 'sample-rate': 0})
                except Exception as e:
                    self.sess.close()
                    self.sess = None
                    self.ws = None
                    log.warning(f'try connect to WebSocket failed, sleep for {sleep_seconds} seconds...', e)
                    await asyncio.sleep(sleep_seconds)
                    sleep_seconds = min(sleep_seconds * 2, 64)
                else:
                    log.debug('Connected to WS')
                    self.connected = True
                    sleep_seconds = 2
                    self.pong = arrow.now().timestamp
                    asyncio.ensure_future(self.on_msg())
                    async with self.lock:
                        cons = list(self.tick_queue_update.keys())
                        if cons:
                            log.info('recover subscriptions', cons)
                            for con in cons:
                                asyncio.ensure_future(self.subscribe_tick(con))
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
                        if data['uri'] == 'single-tick-verbose':
                            self.parse_tick(data)
                        elif data['uri'] == 'pong':
                            self.pong = arrow.now().timestamp
                        elif data['uri'] == 'auth':
                            log.info(data)
                        else:
                            log.warning('unknown message', data)
                elif msg.type == aiohttp.WSMsgType.CLOSED:
                    log.debug('closed')
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
        log.warning('ws was disconnected...')

    def parse_tick(self, data):
        try:
            tick = Tick.from_dict(data['data'])
            self.last_tick_dict[tick.contract] = tick
            if tick.contract in self.tick_queue:
                self.tick_queue[tick.contract].put_nowait(tick)
        except Exception as e:
            log.warning('parse error', e)

    async def subscribe_tick(self, contract, on_update=None):
        log.info('subscribe tick', contract)
        while not self.connected:
            await asyncio.sleep(1)
        async with self.lock:
            try:
                await self.ws.send_json({'uri': 'subscribe-single-tick-verbose', 'contract': contract})
                if contract not in self.tick_queue:
                    self.tick_queue[contract] = asyncio.Queue()
                    if on_update:
                        if not self.tick_queue_update[contract]:
                            asyncio.ensure_future(self.handle_q(contract))
            except Exception as e:
                log.warning('subscribe {} failed...'.format(contract), e)
            else:
                if on_update:
                    self.tick_queue_update[contract].append(on_update)

    async def handle_q(self, contract):
        while contract in self.tick_queue:
            q = self.tick_queue[contract]
            try:
                tk = await q.get()
            except:
                log.warning('get tick from queue failed')
                continue
            for callback in self.tick_queue_update[contract]:
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


_client_pool = {}


async def get_client(key='defalut'):
    if key in _client_pool:
        return _client_pool[key]
    else:
        c = Quote(key)
        _client_pool[key] = c
        return c


async def get_last_tick(contract):
    async with aiohttp.ClientSession() as sess:
        from . import autil
        res, err = await autil.http_go(sess.get, f'{REST_HOST}/quote/single-tick/{contract}')
        if not err:
            res = Tick.from_dict(res)

        return res, err


async def subscribe_tick(contract, on_update):
    c = await get_client()
    return await c.subscribe_tick(contract, on_update)


async def get_contracts(exchange):
    async with aiohttp.ClientSession() as sess:
        from . import autil
        res, err = await autil.http_go(sess.get, f'{REST_HOST}/basic/contracts?exchange={exchange}')
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
        res, err = await autil.http_go(sess.get, f'{REST_HOST}/basic/contracts?exchange={exchange}&name={name}')
        if not err:
            if not res:
                return None, 'contract-not-exist'
            con = Contract.from_dict(res[0])
            return con, err
        return res, err
