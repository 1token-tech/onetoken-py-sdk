import functools
import sys
import logging
from pathlib import Path

log = logging.getLogger('ots')


def set_log():
    # syslog.basicConfig()
    # import logging as syslog
    # syslog.basicConfig()
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.DEBUG)
    ch.setFormatter(
        logging.Formatter('%(levelname)-.7s [%(asctime)s][1token]%(message)s', '%H:%M:%S'))
    log.addHandler(ch)
    log.setLevel(logging.INFO)

    def wrap(level, orig):
        @functools.wraps(orig)
        def new_func(*args, **kwargs):
            if level < log.level:
                return
            left = ' '.join(str(x) for x in args)
            right = ' '.join('{}={}'.format(k, v) for k, v in kwargs.items())
            new = ' '.join(filter(None, [left, right]))
            import inspect
            r = inspect.stack()[1]
            new = f'[{Path(r.filename).name}:{r.lineno}] {new}'
            orig(new)

        return new_func

    log.debug = wrap(logging.DEBUG, log.debug)
    log.info = wrap(logging.INFO, log.info)
    log.warning = wrap(logging.WARNING, log.warning)
    log.exception = wrap(logging.WARNING, log.exception)


set_log()


def log_level(level):
    print('set log level to {}'.format(level))
    log.setLevel(level)


def main():
    log_level(logging.DEBUG)
    log.debug('debug log test')
    log.info('info log test')
    log.warning('warning log test')
    log.exception('exception log test')


if __name__ == '__main__':
    main()
