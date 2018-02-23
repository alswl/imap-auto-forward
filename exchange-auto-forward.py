# coding=utf-8

from __future__ import unicode_literals

import os
import argparse
import email
import logging.config
import getpass
import socket
import subprocess
import re

import requests
from apscheduler.schedulers.blocking import BlockingScheduler
from exchangelib import DELEGATE, Account, Credentials, Configuration
from exchangelib.errors import UnauthorizedError
from requests import ReadTimeout
from urllib3.exceptions import ReadTimeoutError

DEFAULT_INTERVAL_SECONDS = 10

MAIL_PATTERN = re.compile(".*<(.+@.+)>|([^<>]+)")
SENDMAIL_BIN_PATH = "/usr/sbin/sendmail"  # full path!
DEFAULT_SOCKET_TIMEOUT = 10
WORKER_SIZE = 1
DSN_TOKEN = os.environ.get('EXCHANGE_AUTO_FORWARD_DSN')

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'defaultFormatter': {
            'format': '%(levelname)s %(asctime)s %(module)s:%(lineno)d %(message)s ',
            'datefmt': '%m-%d %H:%M:%S',
        }
    },
    'handlers': {
        'defaultHandler': {
            'class': 'logging.handlers.RotatingFileHandler',
            'formatter': 'defaultFormatter',
            'filename': 'exchange-auto-forward.log',
            'maxBytes': 1024 * 1024 * 5,
            'backupCount': 5,
        },
        'sentryHandler': {
            'level': 'ERROR',
            'class': 'raven.handlers.logging.SentryHandler',
            'dsn': DSN_TOKEN,
        },
        'consoleHandler': {
            'class': 'logging.StreamHandler',
        },
    },
    'loggers': {
        '': {
            'handlers': ['defaultHandler', 'sentryHandler'],
            'level': 'INFO',
            # 'level': 'DEBUG',
        },
        'console': {
            'handlers': ['consoleHandler'],
            'level': 'INFO',
            # 'level': 'DEBUG',
            'propagate': False,
        },
    },
}


logging.config.dictConfig(LOGGING)

logger = logging.getLogger(__name__)
console = logging.getLogger('console')

socket.setdefaulttimeout(DEFAULT_SOCKET_TIMEOUT)

scheduler = BlockingScheduler()


def send_mail_via_sendmail(from_addr, to_addr, subject, message):
    p = subprocess.Popen([SENDMAIL_BIN_PATH, "-f", from_addr, to_addr],
                         stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = p.communicate(input=message.encode('utf-8'))
    if stdout or stderr:
        logger.error("Failed forwarding message '%s'\nSendmail stdout:%s\nSendmail stderr:%s\n" % (
            subject, stdout, stderr))
        return


def forward(redirect_to, email_data):
    message = email.message_from_string(email_data)
    m = MAIL_PATTERN.match(message.get('From', 'unkown-from@domain.com'))
    m1, m2 = m.groups()
    from_mail = m1 or m2
    subject = message.get("Subject", "")
    send_mail_via_sendmail(from_mail, redirect_to, subject, message.as_string())
    logger.info('Processed, from: %s, to: %s, subject: %s' % (from_mail, redirect_to, subject))


def search_and_forward(account, redirect_to):
    for message in account.inbox.filter(is_read=False)[:]:
        data = message.mime_content
        email_data = data.decode('UTF-8')
        forward(redirect_to, email_data)
        message.is_read = True
        message.save(update_fields=['is_read'])
        console.debug('>')
    console.debug('.')


def run(host, username, password, redirect_to):
    credentials = Credentials(username=username, password=password)
    try:
        config = Configuration(server=host, credentials=credentials)
    except UnauthorizedError as e:
        logger.error('Login failed, message: %s' % e)
        return
    try:
        account = Account(primary_smtp_address=username, config=config, autodiscover=False,
                          access_type=DELEGATE)
        search_and_forward(account, redirect_to)
    except (ConnectionResetError, requests.exceptions.ConnectionError, TimeoutError,
            ReadTimeoutError, ReadTimeout) as e:
        logger.debug(e)
        console.info('!')
        return


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--username', '-u', required=True)
    parser.add_argument('--server', '-s', required=True)
    parser.add_argument('--redirectto', '-r', required=True)
    args = parser.parse_args()
    password = os.environ.get('EXCHANGE_AUTO_FORWARD_PASSWORD')
    if password is None:
        password = getpass.getpass('EXCHANGE password:')

    scheduler.add_job(run, 'interval', max_instances=WORKER_SIZE, seconds=DEFAULT_INTERVAL_SECONDS,
                      args=[args.server, args.username, password, args.redirectto])
    try:
        scheduler.start()
    except KeyboardInterrupt:
        pass
    scheduler.shutdown()


if __name__ == '__main__':
    main()
