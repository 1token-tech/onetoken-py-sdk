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
