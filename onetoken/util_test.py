def test_id():
    from . import util
    c = util.rand_client_oid('xxx')
    print(c)
    assert len(c) == 4 + 28
