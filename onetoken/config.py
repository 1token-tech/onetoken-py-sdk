class Config:
    HOST_REST = 'https://api.1token.trade/v1'
    TRADE_HOST = 'https://api.1token.trade/v1/trade'
    TRADE_HOST_WS = 'wss://api.1token.trade/v1/ws/trade'
    TICK_HOST_WS = 'wss://api.1token.trade/v1/ws/tick'

    @classmethod
    def change_host(cls, target='1token.trade/api/'):
        for item in ['TRADE_HOST', 'TRADE_HOST_WS', 'TICK_HOST_WS', 'HOST_REST']:
            new = getattr(cls, item).replace('api.1token.trade/', target)
            setattr(cls, item, new)
