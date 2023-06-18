#!/usr/bin/env python3
#
# SMTP Traffic Generator
#
# Configurable traffic volume - set here:
daily_volume_target = 1000000

import random, os, sys, time, names, asyncio, math

from email.message import EmailMessage
from email.headerregistry import Address
from aiosmtplib import SMTP
from aiosmtplib.errors import SMTPException
from typing import Iterator

from zoneinfo import ZoneInfo
from datetime import datetime

#Print to stderr - see https://stackoverflow.com/a/14981125/8545455
def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


def stripEnd(h, s):
    if h.endswith(s):
        h = h[:-len(s)]
    return h

# -----------------------------------------------------------------------------------------
# Configurable email content, recipients etc
# -----------------------------------------------------------------------------------------

class EmailContent:
    def __init__(self):
        self.htmlLink = 'http://example.com/index.html'

        self.content = [
            {'X-Job': 'Todays_Sales', 'subject': 'Today\'s sales'},
            {'X-Job': 'Newsletter', 'subject': 'Newsletter'},
            {'X-Job': 'Last Minute Savings', 'subject': 'Savings'},
            {'X-Job': 'Password_Reset', 'subject': 'Password reset'},
            {'X-Job': 'Welcome_Letter', 'subject': 'Welcome letter'},
            {'X-Job': 'Holiday_Bargains', 'subject': 'Holiday bargains'}
        ]

        self.htmlTemplate = \
'''<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <title>test mail</title>
  </head>
  <body>
    Click <a href="{}">{}</a>
  </body>
</html>'''

        self.textTemplate = \
'''
Plain text - URL here {}
'''

    def rand_job_subj_text_html(self):
        # Contents include a valid http(s) link with custom link name
        c = random.choice(self.content)
        text = self.textTemplate.format(self.htmlLink)
        html = self.htmlTemplate.format(self.htmlLink, self.htmlLink)
        return c['X-Job'], c['subject'], text, html


class RandomRecips:
    def __init__(self, size):
        # Prepare a local list of actual random names
        self.names = []
        for i in range(size):
            self.names.append({'first': names.get_first_name(), 'last': names.get_last_name()})

        self.domains = [
            "not-gmail.com",
            "not-yahoo.com",
            "not-yahoo.co.uk",
            "not-hotmail.com",
            "not-hotmail.co.uk",
            "not-aol.com",
            "not-orange.fr",
            "not-mail.ru",
        ]

    def rand_name(self):
       # Compose a real readable name from the pre-built two-part list l.  Randomise first and last names separately, giving more variety
       return random.choice(self.names)['first'], random.choice(self.names)['last']

    def rand_recip(self):
        first, last = self.rand_name()
        # Most of the time, add a number suffix
        if random.randint(1, 999) > 200:
            suffix = str(random.randint(1, 999))
        else:
            suffix = ''
        return Address(first + ' ' + last, str.lower(first) + '.' + str.lower(last) + suffix + '@' + random.choice(self.domains))


# -----------------------------------------------------------------------------
# Traffic model
# -----------------------------------------------------------------------------

class Traffic:
    def __init__(self):
        # typical triggered email busy hour curve (from 00:00 to 23:00 each day)
        triggered_volume_per_hour = [6, 4, 3, 3, 3, 2, 2, 4, 5, 10, 19, 27, 29, 28, 28, 26, 25, 24, 22, 19, 16, 14, 11, 8]
        # normalise, so that the sum of all the hourly volume would be ~ 1.0
        total = sum(triggered_volume_per_hour)
        self.normalised_triggered_volume_per_hour = [v / total for v in triggered_volume_per_hour]
        # set a window for random variability
        variability = 0.3
        self.high_v = 1 + variability
        self.low_v = 1 - variability

    def volume_this_minute(self, t: datetime, daily_vol: float):
        c = t.astimezone(ZoneInfo('America/New_York'))
        # interpolate the volume between the value for this hour and the next hour (wrapping around)
        this_hour_vol = self.normalised_triggered_volume_per_hour[c.hour]
        next_hour_vol = self.normalised_triggered_volume_per_hour[(c.hour + 1) % 24]
        assert (c.minute >= 0) and (c.minute <=59)
        next_hour_fraction = c.minute / 60
        this_hour_fraction = 1 - next_hour_fraction
        this_minute_vol = daily_vol * (this_hour_vol * this_hour_fraction + next_hour_vol * next_hour_fraction) / 60
        # Add random 'dither' to ensure we sometimes send somethiing, even on low daily volume targets
        vary = random.uniform(self.low_v, self.high_v)
        this = int(math.floor(this_minute_vol * vary) + random.random())
        return this


# Generator yielding a list of n randomized messages
def messages(n: int, r: RandomRecips, c: EmailContent):
    for i in range(n):
        from_email = Address('Test sender', 'test@espops.com')
        recip = r.rand_recip()
        msg = EmailMessage()
        x_job, subject, text, html = c.rand_job_subj_text_html()
        msg['Subject'] = subject
        msg['From'] = from_email
        msg['To'] = recip
        msg['X-Job'] = x_job
        msg['X-Bounce-Me'] = '432 4.2.1 bouncing a message from Python smtp code'
        msg['X-Bounce-Percentage'] = '5'
        msg.set_content(text)
        msg.add_alternative(html, subtype='html')
        yield msg


# -----------------------------------------------------------------------------
# async SMTP email sending
# -----------------------------------------------------------------------------
async def send_msgs_async(msgs: list, host='localhost', port='25'):
    try:
        # Don't attempt SSL from start of connection, but allow STARTTLS (default) with loose certs
        smtp = SMTP(hostname=host, port=port, use_tls=False, validate_certs=False)
        await smtp.connect()
        for msg in msgs:
            errors, etext = await smtp.send_message(msg)
            if errors:
                # this happens if mutltiple recipients, with some accepted & some rejected - see
                # https://aiosmtplib.readthedocs.io/en/latest/reference.html#aiosmtplib.SMTP.sendmail
                eprint(errors, etext)

    except SMTPException as e:
        eprint('{}: {}'.format(type(e), str(e)))

    finally:
        try:
            await smtp.quit()
        finally:
            # Should be closed as we asked to QUIT, but if it's not, then close now
            if smtp.is_connected:
                await smtp.close()


# f = an iterator (such as a generator function) that will yield the messages to be sent.
# Per-connection settings such as host and port are passed onwards via kwargs.
async def send_batch(f: Iterator, messages_per_connection = 100, max_connections = 20, **kwargs):
    this_batch = []
    coroutines = []
    for i in f:
        this_batch.append(i)
        if len(this_batch) >= messages_per_connection:
            coroutines.append(send_msgs_async(this_batch, **kwargs))
            this_batch = []
        # when max connections are ready, dispatch them
        if len(coroutines) >= max_connections:
            await asyncio.gather(*coroutines)
            coroutines = []
    # handle any remnant
    if this_batch:
        coroutines.append(send_msgs_async(this_batch, **kwargs))
    if(coroutines):
        await asyncio.gather(*coroutines)


# -----------------------------------------------------------------------------
# Main code
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    traffic_model = Traffic()
    batch_size = traffic_model.volume_this_minute(datetime.now(), daily_vol = daily_volume_target)

    nNames = 200
    print('Getting {} randomized real names from US 1990 census data'.format(nNames))
    startTime = time.time()
    recips = RandomRecips(nNames) # Get some pseudorandom recipients
    print('Done in {0:.1f}s.'.format(time.time() - startTime))

    content = EmailContent()
    # port 25   direct to the sink
    # port 2525 queue_to_sink listener (passes messages through the MTA to show stats etc)
    # port 587  for email submission that will be delivered to real MXs
    mail_params = {
        'host': 'localhost',
        'port': 2525,
        'messages_per_connection': 100,
        'max_connections': 20,
    }
    print('Sending {} emails over max {} SMTP connections, {} max messages per connection'
        .format(batch_size, mail_params['max_connections'], mail_params['messages_per_connection']))
    startTime = time.time()
    asyncio.run(send_batch(messages(batch_size, recips, content), **mail_params))
    print('Done in {0:.1f}s.'.format(time.time() - startTime))

exit(0)
msgPerMinLow = os.getenv('MESSAGES_PER_MINUTE_LOW', '')
if msgPerMinLow.isnumeric():
    msgPerMinLow = int(msgPerMinLow)
    if msgPerMinLow < 0 or msgPerMinLow > 10000:
        print('Invalid MESSAGES_PER_MINUTE_LOW setting - must be number 1 to 10000')
        exit(1)
else:
    print('Invalid MESSAGES_PER_MINUTE_LOW setting - must be number 1 to 10000')
    exit(1)

msgPerMinHigh = os.getenv('MESSAGES_PER_MINUTE_HIGH', '')
if msgPerMinHigh.isnumeric():
    msgPerMinHigh = int(msgPerMinHigh)
    if msgPerMinHigh < 0 or msgPerMinHigh > 10000:
        print('Invalid MESSAGES_PER_MINUTE_HIGH setting - must be number 1 to 10000')
        exit(1)
else:
    print('Invalid MESSAGES_PER_MINUTE_HIGH setting - must be number 1 to 10000')
    exit(1)


# Send every n minutes, between low and high traffic rate
thisRunSize = int(random.uniform(msgPerMinLow * sendInterval, msgPerMinHigh * sendInterval))
