#!/usr/bin/env python3
#
# SMTP Traffic Generator
#
# Configurable traffic volume per minute
# Uses redis to communicate results to webReporter
#
import random, os, sys, time, json, names, asyncio, aiosmtplib
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import email
from aiosmtplib.errors import SMTPException

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
class Recipients:
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
        return str.lower(first) + '.' + str.lower(last) + '@' + random.choice(self.domains)

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

async def send_mail_async(msg, **params):
    # Contact SMTP server and send Message
    mail_params = params.get("mail_params")
    host = mail_params.get('host', 'localhost')
    port = mail_params.get('port')
    try:
        # Don't attempt SSL from start of connection, but allow STARTTLS (default) with loose certs
        smtp = aiosmtplib.SMTP(hostname=host, port=port, use_tls=False, validate_certs=False)
        await smtp.connect()
        errors, res_text = await smtp.send_message(msg)
        # errors, res_text = await smtp.send_message(msg)
        if errors:
            # this happens if mutltiple recipients, and some are accepted & some rejected - see
            # https://aiosmtplib.readthedocs.io/en/latest/reference.html#aiosmtplib.SMTP.sendmail
            eprint(errors)
        else:
            print(res_text)
        pass

    except SMTPException as e:
        t = type(e)
        eprint('{}: {}'.format(t, str(e)))

    finally:
        try:
            await smtp.quit()
        finally:
            # Should now be closed as we asked to QUIT, but if it's not, then force closure
            if smtp.is_connected:
                smtp.close()

# -----------------------------------------------------------------------------
# Main code
# -----------------------------------------------------------------------------

if __name__ == "__main__":
    r = Recipients(100)
    print(r.rand_recip())

    # port 25 for direct to the sink
    # port 2525 for queue_to_sink listener
    # port 587  for email submission that will be delivered to MXs
    mail_params = {'host': 'localhost', 'port': 25}

    # Prepare message
    from_email = 'test@espops.com'
    to_email = 'steve.tuck@halon.io'
    #msg = MIMEMultipart()
    msg = email.message.EmailMessage()
    msg['Subject'] = 'A python test message'
    msg['From'] = from_email
    msg['To'] = to_email
    msg['X-Bounce-Me'] = '432 4.2.1 bouncing a message from Python smtp code'
    msg['X-Bounce-Percentage'] = '5'
    msg.set_content('Test 1 Message')

    co1 = send_mail_async(msg, mail_params = mail_params)
    co2 = send_mail_async(msg, mail_params = mail_params)

    loop = asyncio.get_event_loop()
    loop.run_until_complete(asyncio.gather(co1, co2))
    loop.close()

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