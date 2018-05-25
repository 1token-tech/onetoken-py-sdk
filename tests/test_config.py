import onetoken


def test_config():
    r = onetoken.Config
    r.change_host()
    print(r)
    for key, value in r.__dict__.items():
        if isinstance(value, str) and '1token.trade' in value:
            assert '//1token.trade/api' in value
        print(key, value)
