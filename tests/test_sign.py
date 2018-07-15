from onetoken import account


def test_sign_no_body():
    r = account.gen_sign(secret='this-is-long-secret', verb='GET', url='/okex/demo/info', nonce='this-is-nonce',
                         data_str=None)
    assert r == 'bf676b208d1b90e2763b0206f8426fc66583b07281a0368c97a9ee71e098e33e'


def test_sign_with_body():
    r = account.gen_sign(secret='this-is-long-secret', verb='GET', url='/okex/demo/info', nonce='this-is-nonce',
                         data_str='this-is-body')
    assert r == '67251a0dcd967b45f3282f22607d77f843453bd7455913c57cc8dd0110453217'
