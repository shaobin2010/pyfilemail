import os
import json
from appdirs import AppDirs
from calendar import timegm
from datetime import datetime, timedelta
from functools import wraps
from requests import Session

from pyfilemail import logger
from urls import get_URL
from transfer import Transfer
from errors import hellraiser, FMBaseError


def login_required(f):
    """Check if user is loged in.

    :raises: :class:`FMBaseError` if not logged in
    """

    @wraps(f)
    def check_login(cls, *args, **kwargs):
        if not cls.logged_in:
            raise FMBaseError('Please login to use this method')

        return f(cls, *args, **kwargs)

    return check_login


class User():
    """This is the entry point to filemail.
     If you use a registered username you'll need to provide
     a password to login.

    :param username: your email/username
    :param password: filename password if registered username is used
    :type username: str
    :type password: str
    """

    def __init__(self, username, password=None):

        self.username = username
        self.transfers = []

        self.session = Session()
        self.config = self.load_config()

        apikey = self.config.get('apikey')
        self.session.cookies['apikey'] = apikey
        if apikey.startswith('GET KEY FROM'):
            msg = 'No API KEY set in config.\n{apikey}\n'
            logger.warning(msg.format(apikey=apikey))

        if password is not None:
            self.login(password)
            self.session.cookies['source'] = 'Desktop'

        else:
            self.session.cookies['source'] = 'web'
            self.session.cookies['logintoken'] = None

    def load_config(self):
        """Load configuration file containing API KEY and other settings.

        :rtype: str
        """

        configfile = self.get_configfile()

        if not os.path.exists(configfile):
            self.save_config()

        with open(configfile, 'rb') as f:
            return json.load(f)

    def save_config(self):
        """Save configuration file to users data location.

         - Linux: ~/.local/share/pyfilemail
         - OSX: ~/Library/Application Support/pyfilemail
         - Windows: C:\\\Users\\\{username}\\\AppData\\\Local\\\pyfilemail

         :rtype: str
        """

        configfile = self.get_configfile()

        if not os.path.exists(configfile):
            configdir = os.path.dirname(configfile)

            if not os.path.exists(configdir):
                os.makedirs(configdir)

            data = {
                'apikey': 'GET KEY FROM www.filemail.com/apidoc/ApiKey.aspx'
                }

        else:
            data = self.config

        with open(configfile, 'wb') as f:
            json.dump(data, f, indent=2)

    def get_configfile(self):
        """Return full path to configuration file.

         - Linux: ~/.local/share/pyfilemail
         - OSX: ~/Library/Application Support/pyfilemail
         - Windows: C:\\\Users\\\{username}\\\AppData\\\Local\\\pyfilemail

         :rtype: str
        """

        ad = AppDirs('pyfilemail')
        configdir = ad.user_data_dir
        configfile = os.path.join(configdir, 'pyfilemail.cfg')

        return configfile

    @property
    def is_anonymous(self):
        """If user is a registered user or not.

        :rtype: bool
        """

        return not self.session.cookies.get('logintoken')

    @property
    def logged_in(self):
        """If registered user is logged in or not.

        :rtype: bool
        """
        return self.session.cookies.get('logintoken') and True or False

    def login(self, password):
        """Login to filemail as the current user.

        :param password:
        :type password: ``str``
        """

        method, url = get_URL('login')
        payload = {
            'apikey': self.config.get('apikey'),
            'username': self.username,
            'password': password,
            'source': 'Desktop'
            }

        res = getattr(self.session, method)(url, params=payload)

        if res.status_code == 200:
            return True

        hellraiser(res)

    @login_required
    def logout(self):
        """Logout of filemail and closing the session."""

        # Check if all transfers are complete before logout
        self.transfers_complete

        payload = {
            'apikey': self.config.get('apikey'),
            'logintoken': self.session.cookies.get('logintoken')
            }

        method, url = get_URL('logout')
        res = getattr(self.session, method)(url, params=payload)

        if res.status_code == 200:
            self.session.cookies['logintoken'] = None
            return True

        hellraiser(res)

    @property
    def transfers_complete(self):
        """Check if all transfers are completed."""

        for transfer in self.transfers:
            if not transfer.is_complete:
                error = {
                    'errorcode': 4003,
                    'errormessage': 'You must complete transfer before logout.'
                    }
                hellraiser(error)

    @login_required
    def get_sent(self, expired=False, for_all=False):
        """Retreve information on previously sent transfers.

        :param expired: Whether or not to return expired transfers.
        :param for_all: Get transfers for all users.
         Requires a Filemail Business account.
        :type for_all: bool
        :type expired: bool
        :rtype: ``list`` of :class:`pyfilemail.Transfer` objects
        """

        method, url = get_URL('get_sent')

        payload = {
            'apikey': self.session.cookies.get('apikey'),
            'logintoken': self.session.cookies.get('logintoken'),
            'getexpired': expired,
            'getforallusers': for_all
            }

        res = getattr(self.session, method)(url, params=payload)

        if res.status_code == 200:
            return self._restore_transfers(res)

        hellraiser(res.json())

    @login_required
    def get_user_info(self, save_to_config=True):
        """Get user info and settings from Filemail.

        :param save_to_config: Whether or not to save settings to config file
        :type save_to_config: ``bool``
        :rtype: ``dict`` containig user information and default settings.
        """

        method, url = get_URL('user_get')

        payload = {
            'apikey': self.config.get('apikey'),
            'logintoken': self.session.cookies.get('logintoken')
            }

        res = getattr(self.session, method)(url, params=payload)

        if res.status_code == 200:
            settings = res.json()['user']

            if save_to_config:
                self.config.update(settings)

            return settings

        hellraiser(res)

    @login_required
    def update_user_info(self, **kwargs):
        """Update user info and settings.

        :param **kwargs: settings to be merged with :func:`User.get_configfile`
         setings and sent to Filemail.
        :rtype: ``bool``
        """

        if kwargs:
            self.config.update(kwargs)

        method, url = get_URL('user_update')

        res = getattr(self.session, method)(url, params=self.config)

        if res.status_code == 200:
            return True

        hellraiser(res)

    @login_required
    def get_received_files(self, age=None, for_all=True):
        """Retrieve a list of transfers sent to you or your company
         from other people.

        :param age: between 1 and 90 days.
        :param for_all: If ``True`` will return received files for
         all users in the same business. (Available for business account
         members only).
        :type age: ``int``
        :type for_all: ``bool``
        :rtype: ``list`` of :class:`Transfer` objects.
        """

        method, url = get_URL('received_get')

        if age:
            if not isinstance(age, int) or age < 0 or age > 90:
                raise FMBaseError('Age must be <int> between 0-90')

            past = datetime.utcnow() - timedelta(days=age)
            age = timegm(past.utctimetuple())

        payload = {
            'apikey': self.config.get('apikey'),
            'logintoken': self.session.cookies.get('logintoken'),
            'getForAllUsers': for_all,
            'from': age
            }

        res = getattr(self.session, method)(url, params=payload)

        if res.status_code == 200:
            return self._restore_transfers(res)

        hellraiser(res)

    def _restore_transfers(self, response):
        """Restore transfers from josn retreived Filemail
        :param response: response object from request
        :rtype: ``list`` with :class:`Transfer` objects
        """

        transfers = []
        for transfer_data in response.json()['transfers']:
            user = transfer_data['from']
            if user == self.username:
                user = self

            transfer = Transfer(user, _restore=True)
            transfer.transfer_info.update(transfer_data)
            transfer.get_files()
            transfers.append(transfer)

        return transfers

    @login_required
    def get_contacts(self):
        """Get contacts from Filemail. Usually people you've sent files
         to in the past.
        :rtype: ``list`` of ``dict`` objects containing contact information
        """

        method, url = get_URL('contacts_get')

        payload = {
            'apikey': self.config.get('apikey'),
            'logintoken': self.session.cookies.get('logintoken')
            }

        res = getattr(self.session, method)(url, params=payload)

        if res.status_code == 200:
            return res.json()['contacts']

        hellraiser(res)

    @login_required
    def get_contact(self, email):
        """Get Filemail contact based on email.

        :param email: address of contact
        :type email: ``str``, ``unicode``
        :rtype: ``dict`` with contact information
        """

        contacts = self.get_contacts()
        for contact in contacts:
            if contact['email'] == email:
                return contact

        msg = 'No contact with email: "{email}" found.'
        raise FMBaseError(msg.format(email=email))

    @login_required
    def update_contact(self, contact):
        """Update name and/or email for contact.

        :param contact: with updated info
        :type contact: ``dict``
        :rtype: ``bool``
        """

        if not isinstance(contact, dict):
            raise AttributeError('contact must be a <dict>')

        method, url = get_URL('contacts_update')

        payload = {
            'apikey': self.config.get('apikey'),
            'logintoken': self.session.cookies.get('logintoken'),
            'contactid': contact.get('contactid'),
            'name': contact.get('name'),
            'email': contact.get('email')
            }

        res = getattr(self.session, method)(url, params=payload)

        if res.status_code == 200:
            return True

        hellraiser(res)

    @login_required
    def add_contact(self, name, email):
        """Add new contact.

        :param name: name of contact
        :param email: email of contact
        :type name: ``str``, ``unicode``
        :type email: ``str``, ``unicode``
        :returns: contact information for new current user
        :rtype: ``dict``
        """

        method, url = get_URL('contacts_add')

        payload = {
            'apikey': self.config.get('apikey'),
            'logintoken': self.session.cookies.get('logintoken'),
            'name': name,
            'email': email
            }

        res = getattr(self.session, method)(url, params=payload)

        if res.status_code == 200:
            return res.json()['contact']

        hellraiser(res)

    @login_required
    def delete_contact(self, contact):
        """Delete contact.

        :param contact: with `contactid`
        :type contact: ``dict``
        :rtype: ``bool``
        """

        if not isinstance(contact, dict):
            raise AttributeError('contact must be a <dict>')

        method, url = get_URL('contacts_delete')

        payload = {
            'apikey': self.config.get('apikey'),
            'logintoken': self.session.cookies.get('logintoken'),
            'contactid': contact.get('contactid')
            }

        res = getattr(self.session, method)(url, params=payload)

        if res.status_code == 200:
            return True

        hellraiser(res)
