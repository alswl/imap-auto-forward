# coding=utf-8
from __future__ import unicode_literals

import os
import sys
import argparse
import imaplib
import email
import smtplib
import logging
import logging.config
import time
import getpass
import socket


import subprocess
import re
from apscheduler.schedulers.blocking import BlockingScheduler

DEFAULT_INTERVAL_SECONDS = 10

MAIL_PATTERN = re.compile(".*<(.+@.+)>|([^<>]+)")
SENDMAIL_BIN_PATH = "/usr/sbin/sendmail"  # full path!
DEFAULT_SOCKET_TIMEOUT = 10
WORKER_SIZE = 1

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
            'maxBytes': 1024 * 1024 * 5,
            'backupCount': 5,
        },
        'consoleHandler': {
            'class': 'logging.StreamHandler',
        },
    },
    'loggers': {
        '': {
            'handlers': ['defaultHandler'],
            'level': 'INFO',
        },
        'console': {
            'handlers': ['consoleHandler'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}

logging.config.dictConfig(LOGGING)

logger = logging.getLogger(__name__)
console = logging.getLogger('console')

socket.setdefaulttimeout(DEFAULT_SOCKET_TIMEOUT)

scheduler = BlockingScheduler()


class SMTPClientFactory(object):

    def __init__(self, host, port, username, password, is_tls):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.is_tls = is_tls

    def get_smtp_client_with_login(self):
        smtp_client = smtplib.SMTP(self.host, self.port)
        if self.is_tls:
            smtp_client.starttls()
        smtp_client.login(self.username, self.password)
        return smtp_client


def send_mail_via_smtp(smtp_client_factory, from_addr, to_addr, message):
    """
    ignore, many SMTP service provider do NOT allow send with other email address
    """
    smtp_client = smtp_client_factory.get_smtp_client_with_login()
    # Client does not have permissions to send as this sender  # XXX
    senderrs = smtp_client.sendmail(from_addr, [to_addr], message.encode('utf-8'))
    smtp_client.quit()


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
    #executor.submit(send_mail_via_smtp, smtp_client_factory, from_mail, redirect_to, message)
    #send_mail_via_smtp(smtp_client_factory, from_mail, redirect_to, message.as_string())
    send_mail_via_sendmail(from_mail, redirect_to, subject, message.as_string())
    logger.info('Processed, from: %s, to: %s, subject: %s' % (from_mail, redirect_to, subject))


def search_and_forward(imap_client, redirect_to):
    typ, data = imap_client.select(mailbox='INBOX')
    if typ != 'OK':
        logger.error('Select inbox failed, message: %s' % data)
        imap_client.close()
        return
    typ, data = imap_client.search(None, 'UNSEEN')
    if typ != 'OK':
        logger.error('Search mail failed, message: %s' % data)
        imap_client.close()
        return
    for message_number in data[0].split():
        _, data = imap_client.fetch(message_number, '(RFC822)')
        email_data = data[0][1].decode('UTF-8')
        forward(redirect_to, email_data)
        console.debug('>')
    console.debug('.')
    imap_client.close()


def run(host, username, password, redirect_to):
    imap_client = None  # TODO pull up to global

    try:
        if imap_client is None:
            imap_client = imaplib.IMAP4_SSL(host=host)
            typ, message = imap_client.login(username, password)
            if typ != 'OK':
                logger.error('Login failed, message: %s' % message)
                return
        try:
            search_and_forward(imap_client, redirect_to)
        except TimeoutError as e:
            imap_client = None
            logger.error(e)
            console.debug('!')
        except imaplib.IMAP4.abort as e:
            imap_client = None
            logger.debug(e)
            console.info('!')
        except imaplib.IMAP4.error as e:
            imap_client = None
            logger.error(e)
            console.debug('!')
    finally:
        if imap_client is not None:
            imap_client.logout()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--username', '-u', required=True)
    parser.add_argument('--server', '-s', required=True)
    parser.add_argument('--redirectto', '-r', required=True)
    # parser.add_argument('--smtphost', '-sh', required=True)
    # parser.add_argument('--smtpport', '-sp', required=True)
    # parser.add_argument('--smtpusername', '-su', required=True)
    args = parser.parse_args()
    password = os.environ.get('IMAP_AUTO_FORWARD_PASSWORD')
    # smtp_password = os.environ.get('IMAP_AUTO_FORWARD_SMTP_PASSWORD')
    if password is None:
        password = getpass.getpass('IMAP password:')

    scheduler.add_job(run, 'interval', max_instances=WORKER_SIZE, seconds=DEFAULT_INTERVAL_SECONDS,
                      args=[args.server, args.username, password, args.redirectto])
    try:
        scheduler.start()
    except KeyboardInterrupt:
        pass
    scheduler.shutdown()


if __name__ == '__main__':
    main()
