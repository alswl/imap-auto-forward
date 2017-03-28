# coding=utf-8

import sys
import argparse
import imaplib
import email
import smtplib
import logging
import logging.config
import time
import getpass

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
            'filename': 'imap-auto-forward.log',
            'maxBytes': 1024*1024*5,
            'backupCount': 5,
        },
        'consoleHandler': {
            'class': 'logging.StreamHandler',
        },
    },
    'loggers': {
        'console': {
            'handlers': ['consoleHandler'],
            'level': 'INFO',
        },
    },
}

logging.config.dictConfig(LOGGING)

logger = logging.getLogger(__name__)
console = logging.getLogger('console')


def forward():
    pass


def mark_seen():
    pass


def search():
    pass


def main():
    pass

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--username', '-u', required=True)
    # parser.add_argument('--password', '-p', required=True)
    parser.add_argument('--server', '-s', required=True)
    parser.add_argument('--redirectto', '-r', required=True)
    args = parser.parse_args()
    password = getpass.getpass()
    main(username=args.username, password=password, imap_server=args.server,
         redirect_to=args.redirectto)
