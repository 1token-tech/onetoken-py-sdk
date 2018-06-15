import re
from setuptools import setup, find_packages

with open('onetoken/__init__.py', 'r', encoding='utf8') as fd:
    version = re.search(r'^__version__\s*=\s*[\'"]([^\'"]*)[\'"]', fd.read(), re.MULTILINE).group(1)
    print('regex find version', version)
if not version:
    raise RuntimeError('Cannot find version information')

setup(name='onetoken',
      author='OneToken',
      url='https://github.com/1token-trade/onetoken-py-sdk',
      author_email='admin@1token.trade',
      packages=find_packages(),
      version=version,
      description='OneToken Trade System Python SDK',
      install_requires=[
          'arrow',
          'docopt',
          'PyJWT',
          'PyYAML',
          'aiohttp==3.1.3',
      ],
      zip_safe=False,
      )
