import yaml
from pathlib import Path

from onetoken import account


def test_sign_no_body():
    r = account.gen_sign(secret='this-is-long-secret', verb='GET', url='/okex/demo/info', nonce='this-is-nonce',
                         data_str=None)
    assert r == 'bf676b208d1b90e2763b0206f8426fc66583b07281a0368c97a9ee71e098e33e'


def test_sign_with_body():
    r = account.gen_sign(secret='this-is-long-secret', verb='POST', url='/okex/demo/info', nonce='this-is-nonce',
                         data_str='{"price": 0.1,     "amount": 0.2}')
    assert r == 'd75535f8f5e2d21dd5e5a0e8609ef56e3177d55f661dfc51b458b9d7ada711dc'


def test_ws_sign():
    r = Path('~/.onetoken/demo-vnpy.yml').expanduser()
    if not r.exists():
        return
    r = r.read_text()
    r = yaml.load(r)

    r = account.gen_sign(secret=r['ot_secret'], verb='GET', url='/ws/mock-vnpy', nonce='1555471107536351',
                         data_str=None)
    print(r)
    assert r == 'e5eadcb5d34e7d05465015ba35fd96b0424fdcfedd1fde2313cf9434d23c4c67'
