from . import Config


def test_config():
    Config.change_host()
    print(Config)
    for key, value in Config.__dict__.items():
        if isinstance(value, str) and '1token.trade' in value:
            assert '//1token.trade/api' in value
        print(key, value)
