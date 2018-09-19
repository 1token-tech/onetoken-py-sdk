import asyncio
import json
import urllib
import hmac
from typing import Union, Tuple
from datetime import datetime

import aiohttp
import jwt
import time
import hashlib

from . import autil
from . import log
from . import util
from .model import Info, Order
from .config import Config


def get_trans_host(exg):
    return '{}/{}'.format(Config.TRADE_HOST, exg)


def get_ws_host(exg, name):
    return '{}/{}/{}'.format(Config.TRADE_HOST_WS, exg, name)


def get_name_exchange(symbol):
    sp = symbol.split('/', 1)
    return sp[1], sp[0]


def gen_jwt(secret, uid):
    payload = {
        'user': uid,
        # 'nonce': nonce
    }
    c = jwt.encode(payload, secret, algorithm='RS256', headers={'iss': 'qb-trade', 'alg': 'RS256', 'typ': 'JWT'})
    return c.decode('ascii')


def gen_nonce():
    return str(int(time.time() * 1000000))


def gen_sign(secret, verb, url, nonce, data_str):
    """Generate a request signature compatible with BitMEX."""
    # Parse the url so we can remove the base and extract just the path.

    if data_str is None:
        data_str = ''

    parsed_url = urllib.parse.urlparse(url)
    path = parsed_url.path

    # print "Computing HMAC: %s" % verb + path + str(nonce) + data
    message = verb + path + str(nonce) + data_str
    # print(message)

    signature = hmac.new(bytes(secret, 'utf8'), bytes(message, 'utf8'), digestmod=hashlib.sha256).hexdigest()
    return signature


IDLE = 'idle'
GOING_TO_CONNECT = 'going-to-connect'
CONNECTING = 'connecting'
READY = 'ready'
GOING_TO_DICCONNECT = 'going-to-disconnect'


class Account:
    def __init__(self, symbol: str, api_key=None, api_secret=None, session=None, loop=None):
        """

        :param symbol:  account symbol, binance/test_user1
        :param api_key:  ot-key in 1token
        :param api_secret: ot-secret in 1token
        :param session: support specified http session
        :param loop:
        """
        self.symbol = symbol
        if api_key is None and api_secret is None:
            self.api_key, self.api_secret = self.load_ot_from_config_file()
        else:
            self.api_key = api_key
            self.api_secret = api_secret
        log.debug('async account init {}'.format(symbol))
        self.name, self.exchange = get_name_exchange(symbol)
        if '/' in self.name:
            self.name, margin_contract = self.name.split('/', 1)
            self.margin_contract = f'{self.exchange}/{margin_contract}'
        else:
            self.margin_contract = None
        self.host = get_trans_host(self.exchange)
        self.host_ws = get_ws_host(self.exchange, self.name)
        if session is None:
            self.session = aiohttp.ClientSession(loop=loop)
        else:
            self.session = session
        self.ws = None
        self.ws_state = IDLE
        self.ws_support = True
        self.last_pong = 0
        self.closed = False

        self.sub_queue = {}
        asyncio.ensure_future(self.keep_connection())

    def close(self):
        if self.ws and not self.ws.closed:
            asyncio.ensure_future(self.ws.close())
        if self.session and not self.session.closed:
            asyncio.ensure_future(self.session.close())
        self.closed = True

    def __del__(self):
        self.close()

    def __str__(self):
        return '<{}>'.format(self.symbol)

    def __repr__(self):
        return '<{}:{}>'.format(self.__class__.__name__, self.symbol)

    @property
    def trans_path(self):
        return '{}/{}'.format(self.host, self.name)

    @property
    def ws_path(self):
        return self.host_ws

    async def get_pending_list(self, contract=None):
        return await self.get_order_list(contract)

    async def get_order_list(self, contract=None, state=None):
        data = {}
        if contract:
            data['contract'] = contract
        if state:
            data['state'] = state
        t = await self.api_call('get', '/orders', params=data)
        return t

    # TODO can be simplified @liuzk oid can be removed
    async def cancel_use_client_oid(self, oid, *oids):
        """
        cancel order use client oid, support batch
        :param oid:
        :param oids:
        :return:
        """
        if oids:
            oid = f'{oid},{",".join(oids)}'
        log.debug('Cancel use client oid', oid)

        data = {'client_oid': oid}
        t = await self.api_call('delete', '/orders', params=data)
        return t

    async def cancel_use_exchange_oid(self, oid, *oids):
        """
        cancel order use exchange oid, support batch
        :param oid:
        :param oids:
        :return:
        """
        if oids:
            oid = f'{oid},{",".join(oids)}'
        log.debug('Cancel use exchange oid', oid)
        data = {'exchange_oid': oid}
        t = await self.api_call('delete', '/orders', params=data)
        return t

    async def cancel_all(self, contract=None):
        log.debug('Cancel all')
        if contract:
            data = {'contract': contract}
        else:
            data = {}
        t = await self.api_call('delete', '/orders/all', params=data)
        return t

    async def get_info(self, timeout=15) -> Tuple[Union[Info, None], Union[Exception, None]]:
        y, err = await self.api_call('get', '/info', timeout=timeout)
        if err:
            return None, err
        if not isinstance(y, dict):
            return None, ValueError(f'{y} not dict')
        acc_info = Info(y)
        if self.margin_contract is not None:
            pos_symbol = self.margin_contract.split('/', 1)[-1]
            return acc_info.get_margin_acc_info(pos_symbol), None
        return acc_info, None

    async def place_and_cancel(self, con, price, bs, amount, sleep, options=None):

        k = util.rand_client_oid(con)
        res1, err1 = await self.place_order(con, price, bs, amount, client_oid=k, options=options)
        if err1:
            return (res1, None), (err1, None)
        await asyncio.sleep(sleep)
        res2, err2 = await self.cancel_use_client_oid(k)
        if err1 or err2:
            return (res1, res2), (err1, err2)
        return [res1, res2], None

    async def get_status(self):
        return await self.api_call('get', '/status')

    async def get_order_use_client_oid(self, oid, *oids):
        """
        :param oid:
        :param oids:
        :return:
        """
        if oids:
            oid = f'{oid},{",".join(oids)}'
        res = await self.api_call('get', '/orders', params={'client_oid': oid})
        log.debug(res)
        return res

    async def get_order_use_exchange_oid(self, oid, *oids):
        """
        :param oid:
        :param oids:
        :return:
        """
        if oids:
            oid = f'{oid},{",".join(oids)}'
        res = await self.api_call('get', '/orders', params={'exchange_oid': oid})
        log.debug(res)
        return res

    async def amend_order_use_client_oid(self, client_oid, price, amount):
        """
        :param price:
        :param amount:
        :param client_oid:
        :return:
        """
        log.debug('Amend order use client oid', client_oid, price, amount)

        data = {'price': price,
                'amount': amount}
        params = {'client_oid': client_oid}
        res = await self.api_call('patch', '/orders', data=data, params=params)
        log.debug(res)
        return res

    async def amend_order_use_exchange_oid(self, exchange_oid, price, amount):
        """
        :param price:
        :param amount:
        :param exchange_oid:
        :return:
        """
        log.debug('Amend order use exchange oid', exchange_oid, price, amount)

        data = {'price': price,
                'amount': amount}
        params = {'exchange_oid': exchange_oid}
        res = await self.api_call('patch', '/orders', data=data, params=params)
        log.debug(res)
        return res

    async def place_order(self, con, price, bs, amount, client_oid=None, tags=None, options=None, on_update=None):
        """
        just pass request, and handle order update --> fire callback and ref_key
        :param options:
        :param con:
        :param price:
        :param bs:
        :param amount:
        :param client_oid:
        :param tags: a key value dict
        :return:
        """
        log.debug('Place order', con=con, price=price, bs=bs, amount=amount, client_oid=client_oid)

        if client_oid is None:
            client_oid = util.rand_client_oid(con)

        if on_update:
            if not self.ws_support:
                log.warning('ws push not supported for this exchange {}'.format(self.exchange))
            else:
                if self.ws_state != READY:
                    log.warning(f'ws connection is {self.ws_state}/{READY}, on_update may failed.')
                if 'order' not in self.sub_queue:
                    await self.subscribe_orders()

                self.sub_queue['order'][client_oid] = asyncio.Queue()
                asyncio.ensure_future(self.handle_order_q(client_oid, on_update))

        data = {'contract': con,
                'price': price,
                'bs': bs,
                'amount': amount}
        if client_oid:
            data['client_oid'] = client_oid
        if tags:
            data['tags'] = ','.join(['{}:{}'.format(k, v) for k, v in tags.items()])
        if options:
            data['options'] = json.dumps(options)
        res = await self.api_call('post', '/orders', data=data)
        log.debug(res)
        return res

    async def handle_order_q(self, client_oid, on_update):
        if 'order' not in self.sub_queue:
            log.warning('order was not subscribed, on_update will not be handled.')
            return
        q = self.sub_queue['order'].get(client_oid, None)
        if not q:
            log.warning('order queue for {} is not init yet.'.format(client_oid))
            return
        while self.is_running:
            try:
                order = await q.get()
                log.debug('on update order {}'.format(order))
                if on_update:
                    assert callable(on_update), 'on_update is not callable'

                    try:
                        if asyncio.iscoroutinefunction(on_update):
                            await on_update(order)
                        else:
                            on_update(order)
                    except:
                        log.exception('handle info error')
                if order['status'] in Order.END_STATUSES:
                    log.debug('{} finished with status {}'.format(order['client_oid'], order['status']))
                    break
            except:
                log.exception('handle q failed.')

        del self.sub_queue['order'][client_oid]

    async def get_dealt_trans(self, con=None):
        """
        get recent dealt transactions
        :param con:
        :return:
        """
        log.debug('Get dealt trans', con=con)
        data = {}
        if con is not None:
            data['contract'] = con
        res = await self.api_call('get', '/trans', params=data)
        log.debug(res)
        return res

    async def post_withdraw(self, currency, amount, address, fee=None, client_wid=None, options=None):
        log.debug('Post withdraw', currency=currency, amount=amount, address=address, fee=fee, client_wid=client_wid)
        if client_wid is None:
            client_wid = util.rand_client_wid(self.exchange, currency)
        data = {
            'currency': currency,
            'amount': amount,
            'address': address
        }
        if fee is not None:
            data['fee'] = fee
        if client_wid:
            data['client_wid'] = client_wid
        if options:
            data['options'] = json.dumps(options)
        res = await self.api_call('post', '/withdraws', data=data)
        log.debug(res)
        return res

    async def cancel_withdraw_use_exchange_wid(self, exchange_wid):
        log.debug('Cancel withdraw use exchange_wid', exchange_wid)
        data = {'exchange_wid': exchange_wid}
        return await self.api_call('delete', '/withdraws', params=data)

    async def cancel_withdraw_use_client_wid(self, client_wid):
        log.debug('Cancel withdraw use client_wid', client_wid)
        data = {'client_wid': client_wid}
        return await self.api_call('delete', '/withdraws', params=data)

    async def get_withdraw_use_exchange_wid(self, exchange_wid):
        log.debug('Cancel withdraw use exchange_wid', exchange_wid)
        data = {'exchange_wid': exchange_wid}
        return await self.api_call('get', '/withdraws', params=data)

    async def get_withdraw_use_client_wid(self, client_wid):
        log.debug('Cancel withdraw use client_wid', client_wid)
        data = {'client_wid': client_wid}
        return await self.api_call('get', '/withdraws', params=data)

    async def get_deposit_list(self, currency):
        log.debug('Get deposit list', currency)
        data = {'currency': currency}
        return await self.api_call('get', '/deposits', params=data)

    async def get_deposit_addr_list(self, currency):
        log.debug('Get deposit address list', currency)
        data = {'currency': currency}
        return await self.api_call('get', '/deposits/addresses', params=data)

    async def get_loan_records(self, contract=None):
        if contract is None:
            contract = self.margin_contract
        log.debug('Get loan orders', contract)
        data = {'contract': contract}
        return await self.api_call('get', '/loan-records', params=data)

    async def borrow(self, currency, amount, contract=None):
        if contract is None:
            contract = self.margin_contract
        log.debug('Borrow', contract, currency, amount)
        data = {'contract': contract, 'currency': currency, 'amount': amount}
        return await self.api_call('post', '/borrow', data=data)

    async def repay(self, exchange_loan_id, currency, amount):
        log.debug('Repay', exchange_loan_id, currency, amount)
        data = {'exchange_loan_id': exchange_loan_id, 'currency': currency, 'amount': amount}
        return await self.api_call('post', '/return', data=data)

    async def margin_transfer_in(self, currency, amount, contract=None):
        if contract is None:
            contract = self.margin_contract
        log.debug('Margin transfer in', contract, currency, amount)
        data = {'contract': contract, 'currency': currency, 'amount': amount, 'target': 'margin'}
        return await self.api_call('post', '/assets-internal', data=data)

    async def margin_transfer_out(self, currency, amount, contract=None):
        if contract is None:
            contract = self.margin_contract
        log.debug('Margin transfer out', contract, currency, amount)
        data = {'contract': contract, 'currency': currency, 'amount': amount, 'target': 'spot'}
        return await self.api_call('post', '/assets-internal', data=data)

    @property
    def is_running(self):
        return not self.closed

    async def api_call(self, method, endpoint, params=None, data=None, timeout=15):
        method = method.upper()
        if method == 'GET':
            func = self.session.get
        elif method == 'POST':
            func = self.session.post
        elif method == 'PATCH':
            func = self.session.patch
        elif method == 'DELETE':
            func = self.session.delete
        else:
            raise Exception('Invalid http method:{}'.format(method))

        nonce = gen_nonce()
        # headers = {'jwt': gen_jwt(self.secret, self.user_name)}

        url = self.trans_path + endpoint

        # print(self.api_secret, method, url, nonce, data)
        json_str = json.dumps(data) if data else ''
        sign = gen_sign(self.api_secret, method, '/{}/{}{}'.format(self.exchange, self.name, endpoint), nonce, json_str)
        headers = {'Api-Nonce': str(nonce), 'Api-Key': self.api_key, 'Api-Signature': sign,
                   'Content-Type': 'application/json'}
        res, err = await autil.http_go(func, url=url, data=json_str, params=params, headers=headers, timeout=timeout)
        if err:
            return None, err
        return res, None

    def set_ws_state(self, new, reason=''):
        log.debug(f'set ws state from {self.ws_state} to {new}', reason)
        self.ws_state = new

    async def keep_connection(self):
        while self.is_running:
            if not self.ws_support:
                break
            if self.ws_state == GOING_TO_CONNECT:
                await self.ws_connect()
            elif self.ws_state == READY:
                try:
                    while not self.ws.closed:
                        ping = datetime.now().timestamp()
                        await self.ws.send_json({'uri': 'ping', 'uuid': ping})
                        await asyncio.sleep(10)
                        if self.last_pong < ping:
                            log.warning('ws connection heartbeat lost')
                            break
                except:
                    log.exception('ws connection ping failed')
                finally:
                    self.set_ws_state(GOING_TO_CONNECT, 'heartbeat lost')
            elif self.ws_state == GOING_TO_DICCONNECT:
                await self.ws.close()
            await asyncio.sleep(1)

    async def ws_connect(self):
        self.set_ws_state(CONNECTING)
        nonce = gen_nonce()
        sign = gen_sign(self.api_secret, 'GET', f'/ws/{self.name}', nonce, None)
        headers = {'Api-Nonce': str(nonce), 'Api-Key': self.api_key, 'Api-Signature': sign}
        url = self.ws_path
        try:
            print(url)
            self.ws = await self.session.ws_connect(url, autoping=False, headers=headers, timeout=30)
        except:
            self.set_ws_state(GOING_TO_CONNECT, 'ws connect failed')
            log.exception('ws connect failed')
            await asyncio.sleep(5)
        else:
            log.info('ws connected.')
            asyncio.ensure_future(self.on_msg())

    async def on_msg(self):
        while not self.ws.closed:
            msg = await self.ws.receive()
            try:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    await self.handle_message(msg.data)
                elif msg.type == aiohttp.WSMsgType.CLOSED:
                    log.debug('closed')
                    break
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    log.warning('error', msg)
                    break
            except Exception as e:
                log.warning('msg error...', e)
        self.set_ws_state(GOING_TO_CONNECT, 'ws was disconnected...')

    async def handle_message(self, msg):
        try:
            data = json.loads(msg)
            log.debug(data)
            if 'uri' not in data:
                if 'code' in data:
                    code = data['code']
                    if code == 'no-router-found':
                        log.warning('ws push not supported for this exchange {}'.format(self.exchange))
                        self.ws_support = False
                        return
                log.warning('unexpected msg get', data)
                return
            action = data['uri']
            if action == 'pong':
                self.last_pong = datetime.now().timestamp()
                return
            status = data['status']
            if action == 'connection':
                if status == 'ok':
                    self.set_ws_state(READY, 'Connected and auth passed.')
                    for key in self.sub_queue.keys():
                        await self.ws.send_json({'uri': 'sub-{}'.format(key)})
                else:
                    self.set_ws_state(GOING_TO_CONNECT, data['message'])
            elif action == 'info':
                if status == 'ok':
                    if 'info' not in self.sub_queue:
                        return
                    info = data['data']
                    info = Info(info)
                    for handler in self.sub_queue['info'].values():
                        try:
                            await handler(info)
                        except:
                            log.exception('handle info error')
            if action == 'order' and 'order' in self.sub_queue:
                if status == 'ok':
                    for order in data['data']:
                        client_oid = order['client_oid']
                        if client_oid in self.sub_queue['order']:
                            self.sub_queue['order'][client_oid].put_nowait(order)
                else:
                    # todo 这里处理order 拿到 error 的情况
                    log.warning('order update error message', data)
        except Exception as e:
            log.warning('unexpected msg format', msg, e)

    async def subscribe_info(self, handler, handler_name=None):
        if not self.ws_support:
            log.warning('ws push not supported for this exchange {}'.format(self.exchange))
            return
        if 'info' not in self.sub_queue:
            self.sub_queue['info'] = {}
        if handler_name is None:
            handler_name = 'default'
        self.sub_queue['info'][handler_name] = handler
        if self.ws_state == READY:
            await self.ws.send_json({'uri': 'sub-info'})
        elif self.ws_state == IDLE:
            self.set_ws_state(GOING_TO_CONNECT, 'user sub info')

    async def unsubscribe_info(self, handler_name=None):
        if handler_name is None:
            handler_name = 'default'
        if 'info' in self.sub_queue:
            del self.sub_queue['info'][handler_name]
            if len(self.sub_queue['info']) == 0 and self.ws_state == READY:
                await self.ws.send_json({'uri': 'unsub-info'})
                del self.sub_queue['info']
            if not self.sub_queue and self.ws_state != IDLE:
                self.set_ws_state(GOING_TO_DICCONNECT, 'subscribe nothing')

    async def subscribe_orders(self):
        if 'order' not in self.sub_queue:
            self.sub_queue['order'] = {}
        if self.ws_state == READY:
            await self.ws.send_json({'uri': 'sub-order'})
        elif self.ws_state == IDLE:
            self.set_ws_state(GOING_TO_CONNECT, 'user sub order')

    async def unsubcribe_orders(self):
        if 'order' in self.sub_queue:
            del self.sub_queue['order']
        if self.ws_state == READY:
            await self.ws.send_json({'uri': 'unsub-order'})
        if not self.sub_queue and self.ws_state != IDLE:
            self.set_ws_state(GOING_TO_DICCONNECT, 'subscribe nothing')

    @staticmethod
    def load_ot_from_config_file():
        import os
        config = os.path.expanduser('~/.onetoken/config.yml')
        if os.path.isfile(config):
            log.info(f'load ot_key and ot_secret from {config}')
            import yaml
            js = yaml.safe_load(open(config).read())
            ot_key, ot_secret = js.get('ot_key'), js.get('ot_secret')
            if ot_key is None:
                ot_key = js.get('api_key')
            if ot_secret is None:
                ot_secret = js.get('api_secret')
            return ot_key, ot_secret
        else:
            log.warning(f'load {config} fail')
            return None, None
