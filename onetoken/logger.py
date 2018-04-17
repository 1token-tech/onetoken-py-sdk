import sys
import logging

log = logging.getLogger('ots')


def set_log():
    # syslog.basicConfig()
    # import logging as syslog
    # syslog.basicConfig()
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.DEBUG)
    ch.setFormatter(
        logging.Formatter('%(levelname)-.7s [%(asctime)s][qb][%(filename)s:%(lineno)s] %(message)s', '%H:%M:%S'))
    log.addHandler(ch)
    log.setLevel(logging.INFO)

    def wrap(orig):
        def new_func(*args, **kwargs):
            # print('-------wrapper----------', args, kwargs)
            left = ' '.join(str(x) for x in args)
            right = ' '.join('{}={}'.format(k, v) for k, v in kwargs.items())
            new = ' '.join(filter(None, [left, right]))
            orig(new)

        return new_func

    log.debug = wrap(log.debug)
    log.info = wrap(log.info)
    log.warning = wrap(log.warning)
    log.exception = wrap(log.exception)


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
