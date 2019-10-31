import asyncio

import pytest


def pytest_configure(config):
    import sys
    sys._pytest = True


@pytest.fixture(scope='session')
def event_loop():
    """Create an instance of the default event loop for each test case."""
    loop = asyncio.get_event_loop()
    print('return global loop', id(loop))
    yield loop
    print('loop close', id(loop))
    loop.close()
