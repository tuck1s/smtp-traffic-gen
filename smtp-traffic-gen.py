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
async def send_msgs_async(msgs: list, host='localhost', port=25, snooze = 0.0, username=None, password=None):
    try:
        # Don't attempt SSL from start of connection, but allow STARTTLS (default) with loose certs
        smtp = SMTP(hostname=host, port=port, use_tls=False, validate_certs=False)
        await smtp.connect()
        if username and password:
            code, msg = await smtp.auth_login(username, password)
            if code <200 or code >299:
                raise(code, msg)

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
    batch = [[] for _ in range(max_connections)]
    b_id = 0 # round-robin distribution of messages to batch
    coroutines = []
    for i in f:
        batch[b_id].append(i)
        if len(batch[b_id]) >= messages_per_connection:
            coroutines.append(send_msgs_async(batch[b_id], **kwargs))
            batch[b_id] = []
        b_id = (b_id+1) % max_connections
        # when a full set of coroutines are ready, dispatch them
        if len(coroutines) >= max_connections:
            await asyncio.gather(*coroutines)
            coroutines = []

    # handle any remnant
    for this_batch in batch:
        coroutines.append(send_msgs_async(this_batch, **kwargs))
    if(coroutines):
        await asyncio.gather(*coroutines)


# -----------------------------------------------------------------------------
# Main code
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    start_time = time.perf_counter()
    parser = argparse.ArgumentParser(
        description='Generate SMTP traffic with headers to cause some messages to bounce back from the sink')
    parser.add_argument('--bounces', type=argparse.FileType('r'), required=True, help='bounce configuration file (csv)')
    parser.add_argument('--sender-subjects', type=argparse.FileType('r'), required=True, help='senders and subjects configuration file (csv)')
    parser.add_argument('--html-content', type=argparse.FileType('r'), required=True, help='html email content with placeholders')
    parser.add_argument('--txt-content', type=argparse.FileType('r'), required=True, help='plain text email content with placeholders')
    parser.add_argument('--daily-volume', type=int, required=True, help='daily volume')
    parser.add_argument('--yahoo-backoff', type=float, help='Yahoo-specific bounce rates to cause backoff mode')
    parser.add_argument('--max-connections', type=int, default=20, help='Maximum number of SMTP connections to open')
    parser.add_argument('--messages-per-connection', type=int, default=100, help='Maximum number of messages to send on a connection')
    parser.add_argument('--duration', type=int, default = 0, help='duration to cadence this send, default is "as fast as possible"')
    parser.add_argument('--server', type=str, default = 'localhost:25', help='server:port to inject messages to')
    parser.add_argument('--auth-user', type=str, help='authentication user name')
    parser.add_argument('--auth-pass', type=str, help='authentication password')
    args = parser.parse_args()
    bounces = BounceCollection(args.bounces, args.yahoo_backoff)
    content = EmailContent(args.sender_subjects, args.html_content, args.txt_content)
    traffic_model = Traffic()
    batch_size = traffic_model.volume_this_minute(datetime.datetime.now(), daily_vol = args.daily_volume)

    nNames = 100 # should be enough for batches up to a few thousand
    print('Getting {} randomized real names from US 1990 census data'.format(nNames))
    names = NamesCollection(nNames) # Get some pseudorandom recipients

    print('Done in {0:.3f}s.'.format(time.perf_counter() - start_time))
    print('Yahoo backoff bounce probability', args.yahoo_backoff)

    if args.duration > 0:
        elapsed_time = max(0, time.perf_counter() - start_time) # ensure monotonic
        snooze = (args.duration - elapsed_time) / (batch_size / args.max_connections)
    else:
        snooze = 0

    # Get host & port from the --server param
    if ':' in args.server:
        host, port = args.server.split(':')
    else:
        host = args.server
        port = '25'
 
    mail_params = {
        'host': host,
        'port': int(port),
        'messages_per_connection': args.messages_per_connection,
        'max_connections': args.max_connections,
        'snooze': snooze,
        'username': args.auth_user,
        'password': args.auth_pass,
    }

    start_time = time.time()
    msgs = rand_messages(batch_size, names, content, bounces)
    print(f"Sending {batch_size} messages, with auth-user: {mail_params['username']}, auth-pass: {mail_params['password']}")
    print(f"Max {mail_params['max_connections']} SMTP connections to {mail_params['host']}:{mail_params['port']},"
          f"{mail_params['messages_per_connection']} max messages per connection, cadence {mail_params['snooze']:.4f} seconds per mail")

    asyncio.run(send_batch(msgs, **mail_params))
    print(f"Done in {time.time() - start_time:.1f}s.")
