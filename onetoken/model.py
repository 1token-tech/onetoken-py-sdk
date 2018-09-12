import json

import arrow
import dateutil
import dateutil.parser


class Tick:
    def __init__(self, time, price, volume=0, bids=None, asks=None, contract=None,
                 source=None,
                 exchange_time=None,
                 amount=None,
                 **kwargs):

        # internally use python3's datetime
        if isinstance(time, arrow.Arrow):
            time = time.datetime
        assert time.tzinfo
        self.contract = contract
        self.source = source
        self.time = time
        self.price = price
        self.volume = volume
        self.amount = amount
        self.bids = []
        self.asks = []
        self.exchange_time = exchange_time
        if bids:
            self.bids = sorted(bids, key=lambda x: -x['price'])
        if asks:
            self.asks = sorted(asks, key=lambda x: x['price'])
        for item in self.bids:
            assert 'price' in item and 'volume' in item
        for item in self.asks:
            assert 'price' in item and 'volume' in item
            # self.asks = asks

    # last as an candidate of last
    @property
    def last(self):
        return self.price

    @last.setter
    def last(self, value):
        self.price = value

    @property
    def bid1(self):
        if self.bids:
            return self.bids[0]['price']
        return None

    @property
    def ask1(self):
        if self.asks:
            return self.asks[0]['price']
        return None

    @property
    def weighted_middle(self):
        a = self.bids[0]['price'] * self.asks[0]['volume']
        b = self.asks[0]['price'] * self.bids[0]['volume']
        return (a + b) / (self.asks[0]['volume'] + self.bids[0]['volume'])

    def get_interest_side(self, bs):
        if bs == 's':
            return self.bids
        if bs == 'b':
            return self.asks

    def __str__(self):
        return '<{} {}.{:03d} {}/{} {} {}>'.format(self.contract,
                                                   self.time.strftime('%H:%M:%S'),
                                                   self.time.microsecond // 1000,
                                                   self.bid1,
                                                   self.ask1,
                                                   self.last,
                                                   self.volume)

    def __repr__(self):
        return str(self)

    @staticmethod
    def init_with_dict(dct):
        return Tick(dct['time'], dct['price'], dct['volume'], dct['bids'], dct['asks'])

    def to_dict(self):
        dct = {'time': self.time.isoformat(), 'price': self.price, 'volume': self.volume, 'asks': self.asks,
               'bids': self.bids}
        if self.exchange_time:
            dct['exchange_time'] = self.exchange_time.isoformat()
        if self.contract:
            dct['symbol'] = self.contract
        return dct

    # @staticmethod
    # def from_dct(dct):
    #     # con = ContractApi.get_by_symbol(dct['symbol'])
    #     con = dct['symbol']
    #     return Tick(time=dateutil.parser.parse(dct['time']), price=dct['price'], bids=dct['bids'], asks=dct['asks'],
    #                 contract=con, volume=dct['volume'])

    def to_mongo_dict(self):
        dct = {'time': self.time, 'price': self.price, 'volume': self.volume, 'asks': self.asks, 'bids': self.bids}
        if self.contract:
            dct['contract'] = self.contract
        return dct

    def to_short_list(self):
        b = ','.join(['{},{}'.format(x['price'], x['volume']) for x in self.bids])
        a = ','.join(['{},{}'.format(x['price'], x['volume']) for x in self.asks])
        lst = [self.contract, self.time.timestamp(), self.price, self.volume, b, a]
        return lst

    @staticmethod
    def from_short_list(lst):
        if isinstance(lst[0], str):
            # convert string to contract
            # lst[0] = ContractApi.get_by_symbol(lst[0])
            lst[0] = lst[0]
        bids, asks = lst[4], lst[5]
        bids = [{'price': float(p), 'volume': float(v)} for p, v in zip(bids.split(',')[::2], bids.split(',')[1::2])]
        asks = [{'price': float(p), 'volume': float(v)} for p, v in zip(asks.split(',')[::2], asks.split(',')[1::2])]

        time = arrow.Arrow.fromtimestamp(lst[1]).datetime
        return Tick(contract=lst[0], time=time, price=lst[2], volume=lst[3], bids=bids, asks=asks)

    def to_ws_str(self):
        lst = self.to_short_list()
        return json.dumps(lst)

    @classmethod
    def from_dict(cls, dict_or_str):
        if isinstance(dict_or_str, str):
            return cls.from_dict(json.loads(dict_or_str))
        d = dict_or_str
        exg_tm = d.get('exchange_time', None)
        if exg_tm is not None:
            exg_tm = arrow.get(exg_tm)
        t = Tick(time=arrow.get(d['time']),
                 exchange_time=exg_tm,
                 # contract=ContractApi.get_by_symbol(d['contract']),
                 contract=d['contract'],
                 volume=d['volume'],
                 asks=d['asks'],
                 bids=d['bids'],
                 price=d['last'],
                 source=d.get('source', None),
                 )
        return t

    def bs1(self, bs):
        if bs == 'b':
            return self.bid1
        else:
            return self.ask1


class Contract:

    def __init__(self, exchange: str, name: str, min_change=0.001, alias="", category='XTC', first_day=None,
                 last_day=None, exec_price=None, currency=None, uid=None,
                 min_amount=1, unit_amount=1, **kwargs):
        assert isinstance(min_change, float) or isinstance(min_change, int)
        self.name = name
        self.exchange = exchange
        self.category = category
        self.min_change = min_change
        self.alias = alias
        self.exec_price = exec_price
        self.first_day = first_day  # the listing date of the contract
        self.last_day = last_day  # the last date that this contract could be executed
        self.currency = currency
        self.min_amount = min_amount
        self.unit_amount = unit_amount
        self.uid = uid  # the id use in database

    def __hash__(self):
        return hash(self.symbol)

    def __eq__(self, other):
        return self.symbol == other.symbol

    def __ne__(self, other):
        return not self.__eq__(other)

    @property
    def symbol(self):
        return self.exchange + '/' + self.name

    def __str__(self):
        return '<Con:{}/{}>'.format(self.exchange, self.name)

    def __repr__(self):
        return '<{}:{}>'.format(self.__class__.__name__, self.symbol)

    @classmethod
    def from_dict(cls, data):
        if 'exchange' in data:
            exchange = data['exchange']
        else:
            sym = data['symbol']
            exchange = sym.split('/')[0]
        return cls(exchange, data['name'], data['min_change'], data['alias'], data['category'],
                   data['first_day'], data['last_day'], data['exec_price'], data['currency'],
                   data['id'], data['min_amount'], data['unit_amount'])


class Candle:
    def __init__(self, time, open, high, low, close, volume, contract, duration):
        self.contract = contract
        self.time = time
        self.open = open
        self.high = high
        self.low = low
        self.close = close
        self.volume = volume
        self.duration = duration

    def __str__(self):
        return '<Candle-{}:{}-{} {} {} {} {} {}>'.format(self.duration, self.contract, self.time.strftime('%H:%M:%S'),
                                                self.open, self.high, self.low, self.close, self.volume)

    def __repr__(self):
        return self.__str__()

    @classmethod
    def from_dict(cls, data):
        return cls(arrow.get(data['time']), data['open'], data['high'], data['low'],
                   data['close'], data['volume'], data['contract'], data['duration'])


class Info:
    def __init__(self, data):
        assert isinstance(data, dict)
        # if 'position' not in y:
        #     log.warning('failed', self.symbol, str(y))
        #     return None, Exception('ACC_GET_INFO_FAILED')
        self.data = data
        # ['position_dict']
        self.position_dict = {item['contract']: item for item in data.get('position', [])}

    @property
    def balance(self):
        return self.data['balance']

    def get_total_amount(self, pos_symbol):
        if pos_symbol in self.position_dict:
            return float(self.position_dict[pos_symbol]['total_amount'])
        else:
            return 0.0

    def get_margin_acc_info(self, pos_symbol):
        if pos_symbol not in self.position_dict:
            return None
        pos = self.position_dict[pos_symbol]
        coin, base = pos_symbol.split('.')
        data_dict = {
            'balance': pos['value_cny'],
            'cash': pos['value_cny_base'] if base == 'usdt' else 0,
            'market_value': pos['market_value'],
            'market_value_detail': {
                coin: pos['market_value_coin'],
                base: pos['market_value_base']
            },
            'position': [
                {
                    'contract': coin,
                    'total_amount': pos['amount_coin'],
                    'available': pos['available_coin'],
                    'frozen': pos['frozen_coin'],
                    'loan': pos['loan_coin'],
                    'market_value': pos['market_value_coin'],
                    'value_cny': pos['value_cny_coin']
                },
                {
                    'contract': base,
                    'total_amount': pos['amount_base'],
                    'available': pos['available_base'],
                    'frozen': pos['frozen_base'],
                    'loan': pos['loan_base'],
                    'market_value': pos['market_value_base'],
                    'value_cny': pos['value_cny_base']
                }
            ]
        }
        return Info(data_dict)


    def __repr__(self):
        return json.dumps(self.data)


class Order:
    BUY = 'b'
    SELL = 's'

    def __init__(self, contract_symbol, entrust_price, bs, entrust_amount, account_symbol=None, entrust_time=None,
                 client_oid=None, exg_oid=None, average_dealt_price=None, dealt_amount=None, comment="", status=None,
                 last_update=None, version=0, last_dealt_amount=None, tags=None, options=None, commission=0):
        assert bs == self.BUY or bs == self.SELL
        self.bs = bs
        self.entrust_price = entrust_price
        self.entrust_amount = entrust_amount
        self.contract_symbol = contract_symbol
        self.account = account_symbol
        self.exchange_oid = exg_oid
        self.client_oid = client_oid

        if entrust_time:
            self.entrust_time = entrust_time
        else:
            self.entrust_time = arrow.now().datetime
        if last_update:
            self.last_update = last_update
        else:
            self.last_update = self.entrust_time

        self.comment = comment
        self.status = status
        # version will increase 1 once the order status changed
        self.version = version
        # last change means the different deal amount compare with the last status of order
        self.last_dealt_amount = last_dealt_amount
        self.avg_dealt_price = average_dealt_price
        self.dealt_amount = dealt_amount
        self.commission = commission
        self.tags = tags if tags else {}
        self.options = options if options else {}

    @staticmethod
    def from_dict(dct) -> 'Order':
        o = Order(contract_symbol=dct['contract'],
                  entrust_price=dct['entrust_price'],
                  average_dealt_price=dct.get('average_dealt_price', 0),
                  bs=dct['bs'],
                  entrust_amount=dct['entrust_amount'],
                  entrust_time=dateutil.parser.parse(dct['entrust_time']),
                  account_symbol=dct['account'],
                  last_update=dateutil.parser.parse(dct['last_update']),
                  exg_oid=dct['exchange_oid'],
                  client_oid=dct['client_oid'],
                  status=dct['status'],
                  version=dct['version'],
                  dealt_amount=dct.get('dealt_amount', 0),
                  last_dealt_amount=dct.get('last_dealt_amount', 0),
                  commission=dct.get('commission', 0),
                  tags=dct.get('tags', {}),
                  options=dct.get('options', {}),
                  comment=dct.get('comment', '')
                  )
        return o

    def __str__(self):
        if self.entrust_time:
            lst = (self.client_oid[-6:] if self.client_oid else None, self.entrust_time.strftime('%H:%M:%S'),
                   self.contract_symbol,
                   self.avg_dealt_price, self.entrust_price, self.bs, self.dealt_amount, self.entrust_amount,
                   self.status)
            return '<{} {} {} {}/{} {} {}/{} {}>'.format(*lst)
        else:
            return '(%s, %s,%s,%s,%s,%s)' % (
                self.client_oid, self.contract_symbol, self.entrust_price, self.bs, '---', self.entrust_amount)

    def __repr__(self):
        return str(self)

    ERROR_ORDER = 'error-order'

    WAITING = 'waiting'  # received from strategy
    PENDING = 'pending'  # already send to broker, and received status update from broker, waiting for deal
    PART_DEAL_PENDING = 'part-deal-pending'
    WITHDRAWING = 'withdrawing'  # withdraw request send, wait for action
    PART_DEAL_WITHDRAWING = 'part-deal-withdrawing'  # similar with above, but when withdraw send, some already dealt

    DEALT = 'dealt'
    WITHDRAWN = 'withdrawn'  # STOP status
    PART_DEAL_WITHDRAWN = 'part-deal-withdrawn'  # STOP status

    ACTIVE = 'active'
    END = 'end'
    ALL = 'all'

    ACTIVE_STATUS = [WAITING, PENDING, PART_DEAL_PENDING, PART_DEAL_WITHDRAWING, WITHDRAWING, ACTIVE]

    END_STATUSES = [ERROR_ORDER, DEALT, WITHDRAWN, PART_DEAL_WITHDRAWN, END]

    ALL_STATUSES = []
    ALL_STATUSES.extend(ACTIVE_STATUS)
    ALL_STATUSES.extend(END_STATUSES)
