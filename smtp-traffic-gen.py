#!/usr/bin/env python3
#
# SMTP Traffic Generator
#
# Configurable traffic volume per minute
# Uses redis to communicate results to webReporter
#
import random, os, sys, time, json, names, asyncio
from datetime import datetime, timezone

from email.message import EmailMessage
from email.headerregistry import Address
from aiosmtplib import SMTP
from aiosmtplib.errors import SMTPException
from typing import Iterator

def eprint(*args, **kwargs):
    """
    Print to stderr - see https://stackoverflow.com/a/14981125/8545455
    """
    print(*args, file=sys.stderr, **kwargs)


# -----------------------------------------------------------------------------------------
# Configurable recipient domains, recipient substitution data, html clickable link, campaign, subject etc
# -----------------------------------------------------------------------------------------

htmlLink = 'http://example.com/index.html'

content = [
    {'X-Job': 'Todays_Sales', 'subject': 'Today\'s sales', 'linkname': 'Deal of the Day'},
    {'X-Job': 'Newsletter', 'subject': 'Newsletter', 'linkname': 'More Daily News'},
    {'X-Job': 'Last Minute Savings', 'subject': 'Savings', 'linkname': 'Last Minute Savings'},
    {'X-Job': 'Password_Reset', 'subject': 'Password reset', 'linkname': 'Password Reset'},
    {'X-Job': 'Welcome_Letter', 'subject': 'Welcome letter', 'linkname': 'Contact Form'},
    {'X-Job': 'Holiday_Bargains', 'subject': 'Holiday bargains', 'linkname': 'Holiday Bargains'}
]

# -----------------------------------------------------------------------------
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
        return Address(first + ' ' + last, str.lower(first) + '.' + str.lower(last) + '@' + random.choice(self.domains))

htmlTemplate = \
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

textTemplate = \
'''
Plain text version - Click {}
'''

# Contents include a valid http(s) link with custom link name
def randomContents():
    c = random.choice(content)
    htmlBody = htmlTemplate.format(htmlLink, htmlLink)
    return c['campaign'], c['subject'], htmlBody

# Inject the messages for a batch of recipients
def sendToRecips(recipBatch, sendObj):
    startT = time.time()

def timeStr(t):
    utc = datetime.fromtimestamp(t, timezone.utc)
    return datetime.isoformat(utc, sep='T', timespec='seconds')

def stripEnd(h, s):
    if h.endswith(s):
        h = h[:-len(s)]
    return h

#---------

# Send a list of messages via the specified SMTP server
async def send_msgs_async(msgs: list, host='localhost', port='25'):
    try:
        # Don't attempt SSL from start of connection, but allow STARTTLS (default) with loose certs
        smtp = SMTP(hostname=host, port=port, use_tls=False, validate_certs=False)
        await smtp.connect()
        for msg in msgs:
            errors, etext = await smtp.send_message(msg)
            # errors, res_text = await smtp.send_message(msg)
            if errors:
                # this happens if mutltiple recipients, and some are accepted & some rejected - see
                # https://aiosmtplib.readthedocs.io/en/latest/reference.html#aiosmtplib.SMTP.sendmail
                eprint(errors, etext)

    except SMTPException as e:
        eprint('{}: {}'.format(type(e), str(e)))

    finally:
        try:
            await smtp.quit()
        finally:
            # Should now be closed as we asked to QUIT, but if it's not, then force closure
            if smtp.is_connected:
                await smtp.close()


# Generator yielding a list of n randomized messages
def messages(n: int, r: RandomRecips):
    for i in range(n):
        from_email = Address('Test sender', 'test@espops.com')
        recip = r.rand_recip()
        msg = EmailMessage()
        msg['Subject'] = 'A python test message'
        msg['From'] = from_email
        msg['To'] = recip
        msg['X-Bounce-Me'] = '432 4.2.1 bouncing a message from Python smtp code'
        msg['X-Bounce-Percentage'] = '5'
        msg.set_content(textTemplate)
        msg.add_alternative(htmlTemplate, subtype='html')
        yield msg


# f = an iterator (such as a generator function) that will yield the messages
# per-connection settings such as host and port are passed onwards via kwargs
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

    # handle remnant, if any
    if this_batch:
        coroutines.append(send_msgs_async(this_batch, **kwargs))
    if(coroutines):
        await asyncio.gather(*coroutines)

# -----------------------------------------------------------------------------
# Main code
# -----------------------------------------------------------------------------

if __name__ == "__main__":
    nNames = 200
    print('Getting {} randomized real names from US 1990 census data'.format(nNames))
    startTime = time.time()
    r = RandomRecips(nNames) # Get some pseudorandom recipients
    print('Done in {0:.1f}s.'.format(time.time() - startTime))

    # port 25   direct to the sink
    # port 2525 queue_to_sink listener (passes messages through the MTA to show stats etc)
    # port 587  for email submission that will be delivered to real MXs
    mail_params = {
        'host': 'localhost',
        'port': 2525,
        'messages_per_connection': 100,
        'max_connections': 20,
    }
    batch_size = 200
    print('Sending {} emails over max {} SMTP connections, {} max messages per connection'
        .format(batch_size, mail_params['max_connections'], mail_params['messages_per_connection']))
    startTime = time.time()
    asyncio.run(send_batch(messages(batch_size, r), **mail_params))
    print('Done in {0:.1f}s.'.format(time.time() - startTime))
    exit(0)


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

apiKey = os.getenv('SPARKPOST_API_KEY')        # API key is mandatory
if apiKey == None:
    print('SPARKPOST_API_KEY environment variable not set - stopping.')
    exit(1)

host = hostCleanup(os.getenv('SPARKPOST_HOST', default='api.sparkpost.com'))

fromEmail = os.getenv('FROM_EMAIL')
if fromEmail == None:
    print('FROM_EMAIL environment variable not set - stopping.')
    exit(1)

resultsKey = os.getenv('RESULTS_KEY')
if resultsKey == None:
    print('RESULTS_KEY environment variable not set - stopping.')
    exit(1)

trackOpens = strToBool(os.getenv('TRACK_OPENS', default='True'))
if trackOpens == None:
    print('TRACK_OPENS set to invalid value - should be True or False')
    exit(1)

trackClicks = strToBool(os.getenv('TRACK_CLICKS', default='True'))
if trackClicks == None:
    print('TRACK_CLICKS set to invalid value - should be True or False')
    exit(1)

sp = SparkPost(api_key = apiKey, base_uri = host)
print('Opened connection to', host)

startTime = time.time()                                         # measure run time
res = getResults()                                              # read back results from previous run (if any)
if not res:
    res = {
        'startedRunning': timeStr(startTime),                   # this is the first run - initialise
        'totalSentVolume': 0
    }

# Send every n minutes, between low and high traffic rate
thisRunSize = int(random.uniform(msgPerMinLow * sendInterval, msgPerMinHigh * sendInterval))
print('Sending from {} to {} recipients, TRACK_OPENS={}, TRACK_CLICKS={}'.format(fromEmail, thisRunSize, trackOpens, trackClicks))
recipients = []
countSent = 0
anyError = ''
for i in range(0, thisRunSize):
    if len(recipients) >= batchSize:
        c, err = sendRandomCampaign(sp, recipients, trackOpens=trackOpens, trackClicks=trackClicks)
        countSent += c
        if err:
            anyError = err                      # remember any error codes seen
        recipients=[]
if len(recipients) > 0:                         # Send residual batch
    c, err = sendRandomCampaign(sp, recipients, trackOpens=trackOpens, trackClicks=trackClicks)
    countSent += c
    if err:
        anyError = err                          # remember any error codes seen

# write out results to console and to redis
endTime = time.time()
runTime = endTime - startTime
print('Done in {0:.1f}s.'.format(runTime))
res.update( {
    'lastRunTime': timeStr(startTime),
    'lastRunDuration': round(runTime, 3),
    'lastRunSize': thisRunSize,
    'lastRunSent': countSent,
    'lastRunError': anyError,
    'nextRunTime': timeStr(startTime + 60 *sendInterval)
})
res['totalSentVolume'] += countSent

if setResults(json.dumps(res)):
    print('Results written to redis')