# imap-auto-forward

Reading email message by IMAP/EXCHANGE protocol, forward(origin message) to another by senmail.

## Use Case

I want using Gmail to manage a third email, but Gmail only support POP3,
do not support IMAP.
And the third email only support IMAP,
so I use this script to forward(redirect) all new message to Gmail.

## Usage

```
python3 imap-auto-forward.py -u username@from.com -s mail.from.com -r to@gmail.com
// or
python3 exchange-auto-forward.py -u username@from.com -s mail.from.com -r to@gmail.com
```
