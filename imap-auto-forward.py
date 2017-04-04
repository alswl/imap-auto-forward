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

import subprocess
from concurrent.futures import ThreadPoolExecutor
import re

MAIL_PATTERN = re.compile(".*<(.+@.+)>|([^<>]+)")
SENDMAIL_BIN_PATH = "/usr/sbin/sendmail"  # full path!

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
        },
    },
}

logging.config.dictConfig(LOGGING)

logger = logging.getLogger(__name__)
console = logging.getLogger('console')


WORKER_SIZE = 4
executor = ThreadPoolExecutor(max_workers=WORKER_SIZE)


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


def send_mail(smtp_client_factory, from_addr, to_addr, message):
    smtp_client = smtp_client_factory.get_smtp_client_with_login()
    # Client does not have permissions to send as this sender  # XXX
    senderrs = smtp_client.sendmail(from_addr, [to_addr], message.encode('utf-8'))
    smtp_client.quit()


def send_mail_via_sendmail(from_addr, to_addr, subject, message):
    p = subprocess.Popen([SENDMAIL_BIN_PATH, "-f", from_addr, to_addr],
                         stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    # __import__('pdb').set_trace()
    stdout, stderr = p.communicate(input=message.encode('utf-8'))
    if stdout or stderr:
        logger.error("Failed forwarding message '%s'\nSendmail stdout:%s\nSendmail stderr:%s\n" % (
            subject, stdout, stderr))
        return


def forward(smtp_client_factory, redirect_to, email_data):
    message = email.message_from_string(email_data)
    # message.replace_header("From", from_addr)
    #message.replace_header("To", redirect_to)
    m = MAIL_PATTERN.match(message.get('From', 'unkown-from@domain.com'))
    m1, m2 = m.groups()
    from_mail = m1 or m2
    subject = message.get("Subject", "")
    #executor.submit(send_mail, smtp_client_factory, from_mail, redirect_to, message)
    #send_mail(smtp_client_factory, from_mail, redirect_to, message.as_string())
    send_mail_via_sendmail(from_mail, redirect_to, subject, message.as_string())
    logger.info('Processed, from: %s, to: %s, subject: %s' % (from_mail, redirect_to, subject))


def search_and_forward(imap_client, smtp_client_factory, redirect_to):
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
        forward(smtp_client_factory, redirect_to, email_data)
        console.info('📧')
    console.info('Search and forwad done.')
    imap_client.close()


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
    # if smtp_password is None:
    #     smtp_password = getpass.getpass('SMTP password:')

    smtp_client_factory = SMTPClientFactory(None, None, None, 'NO', True)
    # smtp_client_factory = SMTPClientFactory(args.smtphost, args.smtpport, args.smtpusername,
    #                                         'NO', True)

    imap_client = imaplib.IMAP4_SSL(host=args.server)
    typ, message = imap_client.login(args.username, password)
    if typ != 'OK':
        logger.error('Login failed, message: %s' % message)
        return
    try:
        while True:
            try:
                search_and_forward(imap_client, smtp_client_factory, args.redirectto)
            except TimeoutError as e:
                logger.error(e)
                console.info('🔄')
            except imaplib.IMAP4.abort as e:
                logger.error(e)
                console.info('🔄')
            except imaplib.IMAP4.error as e:
                logger.error(e)
                console.info('🔄')
            time.sleep(10)
    except InterruptedError:
        pass
    finally:
        imap_client.logout()
        executor.shutdown(True)


if __name__ == '__main__':
    main()
