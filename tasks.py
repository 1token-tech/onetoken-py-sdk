import os

import invoke


@invoke.task
def upload(ctx):
    ctx.run('python setup.py sdist bdist_wheel upload')
    ctx.run('rm -rf build dist onetoken_trade.egg-info')
    ctx.run('git add . ')
    ctx.run('git commit -a -m "update version" ')
    ctx.run('git push')


@invoke.task
def clean(ctx):
    ctx.run('rm -rf build dist onetoken_trade.egg-info')


@invoke.task
def build(ctx):
    ctx.run('pip install pip -U', warn=True)
    ctx.run('python setup.py sdist bdist_wheel && cd dist && pip uninstall onetoken -y')
    for item in os.listdir('dist'):
        if item.endswith('.whl'):
            cmd = f'cd dist && pip install {item}'
            print(cmd)
            ctx.run(cmd)
