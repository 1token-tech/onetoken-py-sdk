class Config:
    HOST_REST = 'https://1token.trade/api/v1'
    TRADE_HOST = 'https://1token.trade/api/v1/trade'
    TRADE_HOST_WS = 'wss://1token.trade/api/v1/ws/trade'
    TICK_HOST_WS = 'wss://1token.trade/api/v1/ws/tick?gzip=true'
    CANDLE_HOST_WS = 'wss://1token.trade/api/v1/ws/candle-v3?gzip=true'

    @classmethod
    def change_host(cls, target='1token.trade/', match='1token.trade/', nossl=False):
        for item in ['TRADE_HOST', 'TRADE_HOST_WS', 'TICK_HOST_WS', 'HOST_REST', 'CANDLE_HOST_WS']:
            new = getattr(cls, item).replace(match, target)
            if nossl:
                new = new.replace('https://', 'http://')
                new = new.replace('wss://', 'ws://')
            setattr(cls, item, new)
