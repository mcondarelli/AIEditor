import argparse
import logging
import sys
from typing import Union, Optional, List, Any


class LoggingConfig:
    LEVEL_MAP = {
        0: logging.CRITICAL,
        1: logging.ERROR,
        2: logging.WARNING,
        3: logging.INFO,
        4: logging.DEBUG,
    }
    LEVEL_SMAP = {
        'CRITICAL': logging.CRITICAL,
        'ERROR': logging.ERROR,
        'WARNING': logging.WARNING,
        'INFO': logging.INFO,
        'DEBUG': logging.DEBUG,
    }

    _initialized = False
    _default_level = logging.INFO
    _default_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    _loggers = {}
    _known_loggers = {}  # Stores logger names and their default levels

    @classmethod
    def get_logger(
            cls,
            name: str,
            _default: Optional[int] = None,
            _format: Optional[str] = None,
            *,
            level: Union[int, str, None] = None,
            format: Optional[str] = None,
            **kwargs: Any
    ) -> logging.Logger:
        """Get or create a logger with flexible configuration."""
        # Handle backward compatibility
        if name not in cls._loggers:
            # morph to new syntax folding old (deprecated) arguments into new ones
            effective_level = cls._default_level
            if _default is not None:
                import warnings
                warnings.warn(
                    "Numeric _default is deprecated, use level='INFO' instead",
                    DeprecationWarning,
                    stacklevel=2
                )  # TODO: use the right value and not static `INFO`
                effective_level = cls.LEVEL_MAP.get(_default, None)  # explicit override

            # Process new-style level specification
            if level is not None:
                if isinstance(level, str):
                    effective_level = getattr(logging, level.upper(), cls._default_level)
                else:
                    effective_level = level

            effective_format = _format or format
            cls._loggers[name] = {
                'level': effective_level,
                'format': effective_format,
                'kwargs': kwargs
            }
            if cls._initialized:
                # cls.configure was called: configure on-the-fly
                cls._configure_logger(name)
        return logging.getLogger(name)

    @classmethod
    def _configure_logger(cls, name: str):
        """Internal method to configure individual logger."""
        config = cls._loggers.get(name)
        if config is None:
            import warnings
            warnings.warn(f'Corrupted configuration for logger "{name}": resetting yo defaults')
            config = {
                'level': cls._default_level,
                'format': cls._default_format
            }
            cls._loggers[name] = config

        # get the handler, possibly a brand new one
        logger = logging.getLogger(name)

        # clear previous configuration, if any
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)

        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(config['format'] or cls._default_format))

        # Apply additional handler config
        for key, value in config['kwargs'].items():
            if hasattr(handler, key):
                setattr(handler, key, value)

        logger.addHandler(handler)
        # Use the level from _known_loggers if set, otherwise default
        logger.setLevel(config['level'] or cls._default_level)

    @classmethod
    def configure(
            cls,
            args: Optional[List[str]] = None,
            level: Union[int, str, None] = None,
            format: Optional[str] = None,
            **kwargs: Any
    ):
        """Configure logging from command line arguments or directly.
        Returns remaining unprocessed arguments."""

        # use sys.argv if not explicitly provided
        args = args or sys.argv
        # Parse command line arguments if provided
        if args is not None:
            cls._parse_args(args)

        # Apply direct configuration if provided
        if level is not None:
            if isinstance(level, str):
                cls._default_level = getattr(logging, level.upper(), cls._default_level)
            else:
                cls._default_level = level

        if format is not None:
            cls._default_format = format

        cls._initialized = True

        # Configure all known loggers
        for name in cls._loggers:
            cls._configure_logger(name)

    @classmethod
    def _parse_args(cls, argv: Optional[List[str]]) -> None:
        """Parse command line arguments for logging configuration.
        Returns remaining unprocessed arguments."""

        argv = argv or sys.argv
        parser = argparse.ArgumentParser(add_help=False)
        parser.add_argument('-v', dest='verbose', action='count', default=0, help='Global verbosity')
        for name, config in cls._loggers.items():
            parser.add_argument(
                f'--log-{name.lower()}',
                dest=name,
                default=config.get('level', cls._default_level),
                help=config['kwargs'].get('help')
            )

        # Parse known args
        known_args, remaining = parser.parse_known_args(argv)
        argv.clear()
        argv.extend(remaining)

        # Handle verbosity (-v, -vv, etc.)
        if known_args.verbose > 0:
            verbosity = min(known_args.verbose, 4)  # Max debug level
            cls._default_level = cls.LEVEL_MAP.get(verbosity, logging.DEBUG)
        # handle logger-specific level
        args = vars(known_args)
        for name, config in cls._loggers.items():
            if name in args:
                level = args[name]
                try:
                    l = int(level)
                    level = cls.LEVEL_MAP[l] if l < len(cls.LEVEL_MAP) else l
                except ValueError:
                    if level in cls.LEVEL_SMAP:
                        level = cls.LEVEL_SMAP[level]
                    else:
                        import warnings
                        warnings.warn(f'argument "--log-{name.tolower}": value "{level}" not recognized')
                config['level'] = level

    @classmethod
    def reset(cls):
        """Reset all logging configuration."""
        cls._initialized = False
        cls._default_level = logging.INFO
        cls._default_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        cls._loggers = {}
        cls._known_loggers = {}
        logging.getLogger().handlers = []


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
