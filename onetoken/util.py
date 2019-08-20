import random
import string

import arrow


def rand_id(length=10):
    assert length >= 1

    first = random.choice(string.ascii_lowercase + string.ascii_uppercase)
    after = ''.join(random.choice(string.ascii_lowercase + string.ascii_uppercase + string.digits)
                    for _ in range(length - 1))

    r = first + after
    return r


def rand_client_oid(contract_symbol):
    """
        binance/btc.usdt-20190816152332asdfqwer123450
    :param contract_symbol:
    :return:
    """
    now = arrow.now().format('YYYYMMDDHHmmss')
    rand = rand_id(14)
    oid = f'{contract_symbol}-{now}{rand}'
    return oid


def rand_client_wid(exchange, currency):
    """
    binance/xxx-yearmonthday-hourminuteseconds-random
    :param exchange:
    :param currency:
    :return:
    """
    now = arrow.now().format('YYYYMMDD-HHmmss')
    rand = rand_id(5)
    cwid = f'{exchange}/{currency}-{now}-{rand}'
    return cwid
