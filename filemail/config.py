# -*- coding: utf-8 -*-
import os
from ConfigParser import ConfigParser

from errors import FMConfigError


class Config():
    """
    Config handles creating, loading or storing settings for ``username``.

    Config class also stores information about the logged in session.

    :param username: `String` with valid filemail.com username
    :param \*\*kwargs: (optional) Keywords concerning user and connection

    If no configfile containing ``apikey`` and ``password`` exists for the
    username passed, you need to provide them as keywords
    """

    def __init__(self, username, **kwargs):
        self._config = {}
        self.config_file = None

        self.required_keys = [
            'apikey',
            'password',
            'username'
            ]

        self.optional_keys = [
            'country',
            'created',
            'defaultconfirmation',
            'defaultdays',
            'defaultdownloads',
            'defaultnotify',
            'defaultsubject',
            'email',
            'logintoken',
            'maxdays',
            'maxdownloads',
            'maxtransfersize',
            'membershipname',
            'name',
            'newsletter',
            'signature',
            'source',
            'subscription'
            ]

        self.valid_keys = self.required_keys + self.optional_keys
        self.set('username', username)

        if kwargs:
            self.update(kwargs)

        self.checkForConfigfile()

    def checkForConfigfile(self):
        """Attempt to locate and set configfile path"""

        self.config_file = self._locateConfig()

    def set(self, key, value):
        """
        Add or update keys in the config

        :param key: `String` of valid key name
        :param value: `String` or `Int` with value for key

        ``set()`` validates the key before adding to the config.
        """

        if self.validKey(key):
            if key in self.required_keys:
                if value is None:
                    msg = 'Required key, "%s", can\'t be None' % key
                    raise FMConfigError(msg)
            self._config[key] = value
        else:
            raise AttributeError('Non valid config key, "%s" passed' % key)

    def get(self, key):
        """
        Get value of given `key` in config

        :param key: `String` with key name
        :returns: `value` if key is valid and in config or `None` if not
        """

        if key in self._config:
            return self._config[key]
        return None

    def update(self, config):
        """
        Bulk update the config with a dictionary

        :param config: `Dictionary` with config options
        """

        if not isinstance(config, dict):
            raise Exception('You need to pass a dict')

        for key, value in config.items():
            self.set(key, value)

    def config(self):
        """:returns: `Dictionary` containing the current config"""

        return self._config

    def validKey(self, key):
        """
        Validates key for the config

        :param key: `String` with key to check against valid keys
        :returns: `Boolean`
        """

        return key in self.valid_keys

    def save(self):
        """
        Save the current config to disk

        If noe configfile is stored in the class it will attempt to locate
        ``filemail.cfg`` in known locations or create one in the users
        ``${HOME}`` directory.
        """

        if self.config_file is None:
            config_file = self._locateConfig()

        if config_file is None:
            #raise FMConfigError('No config file found')
            config_file = os.path.join(os.path.expanduser('~'), 'filemail.cfg')

        config = ConfigParser()
        config.add_section(self._username)
        for key, value in self._config.items():
            config.set(self._username, key, value)

        config.write(open(config_file, 'w'))

        self.config_file = config_file

    def load(self):
        """Load and set config from file"""

        if self.config_file is None:
            self.checkForConfigfile()

        if self.config_file is None:
            #raise FMConfigError('No config file found')
            return None

        config = self._read(self.config_file)
        username = self.get('username')

        if username in config.sections():
            env = dict(config.items(username))

            for key, value in env.items():
                self.set(key, value)

    def _checkFilePermissions(self):
        pass

    def _read(self, config_file):
        """
        Open and parse the stored configfile

        :param config_file: `String` with full path to configfile
        :returns: `Dictionary` with config
        """

        config = ConfigParser()
        config.readfp(open(config_file))

        return config

    def _locateConfig(self):
        """
        Locate configfile in prioritized order:

        :returns: full path to configfile

        * Environment variable ``FILEMAIL_CONFIG_PATH``
        * Current directory
        * ``${HOME}`` directory

        """

        if self.config_file is not None:
            return self.config_file

        here = os.path.dirname(__file__)
        locations = [
            os.getenv('FILEMAIL_CONFIG_FILE', ''),
            os.path.join(os.path.dirname(here), 'filemail.cfg'),
            os.path.join(os.path.expanduser('~'), 'filemail.cfg')
            ]

        for path in locations:
            if os.path.isfile(path):
                if os.path.basename(path) == 'filemail.cfg':
                    self.config_file = path
                    return path

        return None

    def __repr__(self):
        return repr(self._config)