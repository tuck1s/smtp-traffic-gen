#!/usr/bin/env python3
#
# SMTP Traffic Generator

import sys, time, asyncio, datetime, argparse
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
async def send_msgs_async(msgs: list, host='localhost', port='25', snooze = 0.0):
    try:
        # Don't attempt SSL from start of connection, but allow STARTTLS (default) with loose certs
        smtp = SMTP(hostname=host, port=port, use_tls=False, validate_certs=False)
        await smtp.connect()
        for msg in msgs:
            t1 = time.perf_counter()
            errors, etext = await smtp.send_message(msg)
            if snooze > 0:
                # Adjust for elapsed time to send message
                t2 = time.perf_counter()
                this_snooze = max(0, snooze - t2 + t1)
                time.sleep(this_snooze)
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
    parser = argparse.ArgumentParser(
        description='Generate SMTP traffic with headers to cause some messages to bounce back from the sink')
    parser.add_argument('--bounces', type=argparse.FileType('r'), required=True, help='bounce configuration file (csv)')
    parser.add_argument('--sender-subjects', type=argparse.FileType('r'), required=True, help='senders and subjects configuration file (csv)')
    parser.add_argument('--html-content', type=argparse.FileType('r'), required=True, help='html email content with placeholders')
    parser.add_argument('--txt-content', type=argparse.FileType('r'), required=True, help='plain text email content with placeholders')
    parser.add_argument('--daily-volume', type=int, required=True, help='daily volume')
    parser.add_argument('--yahoo-backoff', type=float, help='Yahoo-specific bounce rates to cause backoff mode')
    parser.add_argument('--max-connections', type=int, default=20, help='Maximum number of SMTP connections to open')
    parser.add_argument('--duration', type=int, default = 0, help='duration to cadence this send, default is "as fast as possible"')
    args = parser.parse_args()
    bounces = BounceCollection(args.bounces, args.yahoo_backoff)
    content = EmailContent(args.sender_subjects, args.html_content, args.txt_content)
    traffic_model = Traffic()
    batch_size = traffic_model.volume_this_minute(datetime.datetime.now(), daily_vol = args.daily_volume)

    nNames = 100 # should be enough for batches up to a few thousand
    print('Getting {} randomized real names from US 1990 census data'.format(nNames))
    startTime = time.time()
    names = NamesCollection(nNames) # Get some pseudorandom recipients
    print('Done in {0:.1f}s.'.format(time.time() - startTime))
    print('Yahoo backoff bounce probability', args.yahoo_backoff)

    if args.duration > 0:
        snooze = args.duration / (batch_size / args.max_connections)
    else:
        snooze = 0
    # port 2525 direct to the sink
    # port 25   queue_to_sink listener (passes messages through the MTA to show stats etc)
    mail_params = {
        'host': 'localhost',
        'port': 25,
        'messages_per_connection': 100,
        'max_connections': args.max_connections,
        'snooze': snooze,
    }

    startTime = time.time()
    msgs = rand_messages(batch_size, names, content, bounces)
    print('Sending {} emails over max {} SMTP connections, {} max messages per connection, cadence {:0.4f} seconds per mail'
        .format(batch_size, mail_params['max_connections'], mail_params['messages_per_connection'], mail_params['snooze']))
    asyncio.run(send_batch(msgs, **mail_params))
    print('Done in {0:.1f}s.'.format(time.time() - startTime))
