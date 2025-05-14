# log.py -- 日志相关
#
# Copyright (C) 2022 KAAAsS
import copy
import json
import logging
import os
import re
import sys
import threading
import timeit
from pathlib import Path

from colorama import Fore, Style

LOG_NO_COLOR = os.getenv('LOG_NO_COLOR', False)

# 创建标准输出日志
_stdout_handler = logging.StreamHandler(sys.stdout)


class ColoredFormatter(logging.Formatter):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def format(self, record):
        if record.levelno == logging.DEBUG:
            color = Fore.BLUE
        elif record.levelno == logging.INFO:
            color = Fore.GREEN
        elif record.levelno == logging.WARNING:
            color = Fore.YELLOW
        elif record.levelno in [logging.ERROR, logging.CRITICAL]:
            color = Fore.RED
        else:
            color = ""

        if not LOG_NO_COLOR:
            record = copy.copy(record)
            record.levelname = f"{color}{record.levelname}{Style.RESET_ALL}"
        return super().format(record)


_stdout_handler.setFormatter(ColoredFormatter(
    '%(asctime)s - %(levelname)s - %(name)s - %(message)s',
))

# Logger
logger_map = {}

_current_ctx = threading.local()


def _log_func_wrapper(func):
    def wrapper(*args, **kwargs):
        extra = {}

        # 格式化字符串
        msg = args[0] % args[1:]

        # 附加 JSON 数据
        kw_data = get_current_ctx().copy()
        kw_data.update(kwargs)
        kv_msg = json.dumps(kw_data, ensure_ascii=False, default=repr)
        if kw_data:
            msg += f" -- {kv_msg}"

        if 'exc_info' in kwargs:
            extra['exc_info'] = kwargs['exc_info']

        return func(msg, **extra)

    return wrapper


def get_current_ctx():
    if hasattr(_current_ctx, 'ctx'):
        return _current_ctx.ctx
    return {}


def set_current_ctx(ctx: dict):
    _current_ctx.ctx = ctx


class log_ctx:
    """
    用于设置当前日志 ctx 的上下文管理器

    ## Example
    ```python
    with log_ctx(lib_name='lib_name'):
        debug('debug')
    ```
    """

    def __init__(self, **kwargs):
        self.last_ctx = get_current_ctx()
        self.ctx = self.last_ctx.copy()
        self.ctx.update(kwargs)

    def __enter__(self):
        set_current_ctx(self.ctx)

    def __exit__(self, exc_type, exc_val, exc_tb):
        set_current_ctx(self.last_ctx)


class log_elapse:
    """
    用于记录代码块执行时间

    ## Example
    ```python
    with log_elapse('thing to be done'):
        do_something()
    ```
    """

    def __init__(self, msg):
        self.msg = msg

    def __enter__(self):
        info(self.msg, event='start')
        self.start_time = timeit.default_timer()

    def __exit__(self, exc_type, exc_val, exc_tb):
        elapsed_time = timeit.default_timer() - self.start_time
        info(self.msg, event='end', elapsed_time=elapsed_time)


def log_funcs(name=None, from_file=None):
    """
    Usage:
    >>> debug, info, warn, error, fatal = log_funcs(from_file=__file__)
    """
    # 从文件名中获取 logger 名称
    if from_file is not None:
        base_dir = Path(__file__).parent.parent
        rel_path = Path(from_file).relative_to(base_dir)
        name = str(rel_path).replace('.py', '')

    if name is None:
        raise ValueError('name 和 from_file 不能同时为空')

    if name not in logger_map:
        logger = logging.Logger(name)
        logger.addHandler(_stdout_handler)
        logger_map[name] = logger
    logger = logger_map[name]
    return _log_func_wrapper(logger.debug), _log_func_wrapper(logger.info), _log_func_wrapper(logger.warning), \
        _log_func_wrapper(logger.error), _log_func_wrapper(logger.critical)


debug, info, warn, error, fatal = log_funcs('util/log')


def log_stdout_level(level):
    try:
        _stdout_handler.setLevel(level)
    except ValueError:
        fatal(f"错误的日志等级", level=level)
        exit(1)


def inject_global_timer():
    """设置全局计时器"""
    global _global_start_time
    _global_start_time = timeit.default_timer()

    def exit_handler():
        elapsed_time = timeit.default_timer() - _global_start_time
        set_current_ctx({})
        info('执行结束', elapsed_time=elapsed_time)

    import atexit
    atexit.register(exit_handler)


def add_log_file(log_file: Path):
    """添加日志文件"""
    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(levelname)s - %(name)s - %(message)s',
    ))
    for logger in logger_map.values():
        logger.addHandler(file_handler)


REG_LOG = re.compile(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3}) - (\w+) - (.*) - (.*) -- (\{.*\})')


def parse_line(line: str) -> dict:
    """
    解析一行日志
    格式：2024-04-05 05:05:51,676 - DEBUG - msg -- {"a": "b"}
    """
    matched = REG_LOG.match(line)
    if not matched:
        return {}
    result = {
        'time': matched.group(1),
        'level': matched.group(2),
        'module': matched.group(3),
        'msg': matched.group(4),
    }
    try:
        result.update(json.loads(matched.group(5)))
    except json.JSONDecodeError:
        pass
        # warn('not a valid json in log line', line=line)
    return result


def parse_file(log_file) -> list[dict]:
    """解析日志文件"""
    with open(log_file, 'r') as f:
        return [parse_line(line) for line in f]


if __name__ == '__main__':
    inject_global_timer()
    debug('debug', a=1, b=2)

    with log_ctx(lib_name='lib_name'):
        debug('debug', c=3, d=4)

    print(parse_line('2024-06-05 00:53:55,766 - INFO - util/log - scanning project -- {"project": "chaos-mesh", '
                     '"event": "start"}'))

    with log_elapse('sleep'):
        import time

        time.sleep(1)
        os.system('sleep 1')
