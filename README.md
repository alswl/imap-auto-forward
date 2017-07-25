# imap-auto-forward

Reading email message by IMAP/EXCHANGE protocol, forward(origin message) to another by senmail.

## Use case

Using Gmail to manage a third email, buy Gmail only support POP3,
not support IMAP.
And third email do not support POP3 only support IMAP.
So I use this script to forward(redirect) all new message to Gmail.

## Usage

```
python3 imap-auto-forward.py -u username@from.com -s mail.from.com -r to@gmail.com
// or
python3 exchange-auto-forward.py -u username@from.com -s mail.from.com -r to@gmail.com
```
