#!/usr/bin/env python3
#
# SMTP Traffic Generator
#
# Configurable traffic volume - set here:
daily_volume_target = 40000

import sys, time, asyncio, datetime
from aiosmtplib import SMTP
from aiosmtplib.errors import SMTPException
from typing import Iterator

from emailcontent import *
from trafficmodel import *

#Print to stderr - see https://stackoverflow.com/a/14981125/8545455
def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


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
    bounces = BounceCollection('demo_bounces.csv')
    content = EmailContent('sender_subjects.csv')
    traffic_model = Traffic()
    batch_size = traffic_model.volume_this_minute(datetime.datetime.now(), daily_vol = daily_volume_target)

    nNames = 100 # should be enough for batches up to a few thousand
    print('Getting {} randomized real names from US 1990 census data'.format(nNames))
    startTime = time.time()
    names = NamesCollection(nNames) # Get some pseudorandom recipients
    print('Done in {0:.1f}s.'.format(time.time() - startTime))

    # port 2525 direct to the sink
    # port 25   queue_to_sink listener (passes messages through the MTA to show stats etc)
    # port 587  for email submission that will be delivered to real MXs
    mail_params = {
        'host': 'localhost',
        'port': 25,
        'messages_per_connection': 100,
        'max_connections': 20,
    }

    startTime = time.time()
    msgs = rand_messages(batch_size, names, content, bounces, 0.03) # initial bounce of x%
    print('Sending {} emails over max {} SMTP connections, {} max messages per connection'
        .format(batch_size, mail_params['max_connections'], mail_params['messages_per_connection']))
    asyncio.run(send_batch(msgs, **mail_params))
    print('Done in {0:.1f}s.'.format(time.time() - startTime))
