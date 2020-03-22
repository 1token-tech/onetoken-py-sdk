"""
async util
"""
import asyncio
import json
from datetime import datetime

import aiohttp
import arrow


def dumper(obj):
    if isinstance(obj, arrow.Arrow):
        return obj.isoformat()
    if isinstance(obj, datetime):
        return obj.isoformat()
    return obj


_aiohttp_sess = None


def get_aiohttp_session():
    global _aiohttp_sess
    if _aiohttp_sess is None:
        _aiohttp_sess = aiohttp.ClientSession()
    return _aiohttp_sess


async def http_go(func, url, timeout=15, method='json', accept_4xx=False, *args, **kwargs):
    """

    :param func:
    :param url:
    :param timeout:
    :param method:
        json -> return json dict
        raw -> return raw object
        text -> return string

    :param accept_4xx:
    :param args:
    :param kwargs:
    :return:
    """
    from . import HTTPError
    assert not accept_4xx
    assert method in ['json', 'text', 'raw']
    try:
        if 'params' not in kwargs or kwargs['params'] is None:
            kwargs['params'] = {}
        params = kwargs['params']
        params['source'] = 'onetoken-py-sdk'
        kwargs['timeout'] = timeout
        resp = await asyncio.wait_for(func(url, *args, **kwargs), timeout)
        txt = await resp.text()
        if resp.status >= 500:
            return None, HTTPError(HTTPError.RESPONSE_5XX, txt)

        if 400 <= resp.status < 500:
            return None, HTTPError(HTTPError.RESPONSE_4XX, txt)

        if method == 'raw':
            return resp, None
        elif method == 'text':
            return txt, None
        elif method == 'json':
            try:
                return json.loads(txt), None
            except:
                return None, HTTPError(HTTPError.NOT_JSON, txt)
    except asyncio.TimeoutError:
        return None, HTTPError(HTTPError.TIMEOUT, "")
    except aiohttp.ClientError as e:
        return None, HTTPError(HTTPError.HTTP_ERROR, str(e))
    except Exception as e:
        return None, HTTPError(HTTPError.HTTP_ERROR, str(e))



