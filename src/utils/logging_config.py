import argparse
import logging
import sys
from typing import Dict, List, Optional


class LoggingConfig:
    _loggers: Dict[str, dict] = {}
    levels = [logging.CRITICAL, logging.ERROR, logging.WARNING, logging.INFO, logging.DEBUG]

    @classmethod
    def get_logger(cls, name: str,
                   _arg: Optional[str] = None,
                   _default: Optional[int] = None,
                   _help: Optional[str] = None,
                   _format: Optional[str] = None) -> logging.Logger:
        if name not in cls._loggers:
            _arg = _arg or f'--log-{name.lower()}'
            _help = _help or f'{name} verbosity (0-4)'
            if _default is not None:
                # TODO: accept string
                _default = min(max(0, _default), len(cls.levels)-1)
            cls._loggers[name] = {
                'default': _default,
                'arg': _arg,
                'help': _help,
                'format': _format
            }
        return logging.getLogger(name)

    @classmethod
    def configure(cls, _argv: List[str] = None) -> List[str]:
        """Fully self-contained configuration.

        Returns:
            list of remaining_args
        """
        _argv = sys.argv if _argv is None else _argv

        # Setup parser
        parser = argparse.ArgumentParser(add_help=False)
        parser.add_argument('-v', action='count', default=0, help='Global verbosity')
        for name, config in cls._loggers.items():
            parser.add_argument(
                config['arg'],
                type=int,
                default=config['default'],
                help=config['help']
            )

        # Parse known args
        args, remaining = parser.parse_known_args(_argv)
        _argv.clear()
        _argv.extend(remaining)

        # Configure logging
        for name, config in cls._loggers.items():
            level_num = getattr(args, config['arg'].replace('-', '_').lstrip('_'), None)
            level_num = (args.v if args.v > 0
                         else level_num if level_num is not None
                         else config['default'] if config['default'] is not None
                         else 1)

            logger = logging.getLogger(name)
            logger.setLevel(cls.levels[min(level_num, len(cls.levels)-1)])

            # Remove all existing handlers
            for handler in logger.handlers[:]:
                logger.removeHandler(handler)

            # Add new handler with configured format
            _format = config['format'] or f'%(asctime)s - {name} - %(levelname)s - %(message)s'
            handler = logging.StreamHandler()
            formatter = logging.Formatter(_format)
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            print(logger)
        return remaining


if __name__ == '__main__':
    gui_log = LoggingConfig.get_logger('GUI', _default=2)
    db_log = LoggingConfig.get_logger('DB_access', _default=1)
    other_log = LoggingConfig.get_logger('other', _format='plain format %(message)s')

    argv = "--log-gui=3 --some-other -t".split()
    LoggingConfig.configure(argv)
    print(f'Remaining args: {" ".join(argv)}')

    gui_log.info("Application started")  # Will use configured level
    db_log.warning("Database connected")  # shouldn't print
    other_log.critical("message in plain format")
