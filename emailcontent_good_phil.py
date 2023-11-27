#!/usr/bin/env python3

import random, names, csv, datetime, string, io
from email.headerregistry import Address
from email.message import EmailMessage

# -----------------------------------------------------------------------------------------
# First and last names from 1990 US Census data
# -----------------------------------------------------------------------------------------
class NamesCollection:
    def __init__(self, size):
        # Prepare a local list of actual random names
        self.names = []
        for i in range(size):
            self.names.append({'first': names.get_first_name(), 'last': names.get_last_name()})

    def rand_name(self):
       # Compose a real readable name from the pre-built two-part list l.  Randomise first and last names separately, giving more variety
       return random.choice(self.names)['first'], random.choice(self.names)['last']

    def rand_recip(self, domain):
        first, last = self.rand_name()
        # Most of the time, add a number suffix
        if random.randint(1, 999) > 200:
            suffix = str(random.randint(1, 999))
        else:
            suffix = ''
        return Address(first + ' ' + last, str.lower(first) + '.' + str.lower(last) + suffix + '@' + domain)

# -----------------------------------------------------------------------------------------
# Realistic bounce codes
# -----------------------------------------------------------------------------------------
class BounceCollection:
    def __init__(self, bounce_file: io.BufferedReader, yahoo_backoff: float):
        self.yahoo_backoff = yahoo_backoff # Special bounce rate for these domains
        self.domain_codes = {}
        self.domains = []
        self.weights = []
        r = csv.DictReader(bounce_file, fieldnames=['domain', 'code', 'enhanced', 'text']) # Ignore any extra fields such as count
        for row_dict in r:
            if row_dict['domain'] != 'domain': # skip the header row
                self.add(row_dict['domain'], row_dict['code'], row_dict['enhanced'], row_dict['text'])

        # give more weight to some domains. Note the numerators should add up to 100
        for d, v in self.domain_codes.items():
            self.domains.append(d)
            weights = [
                (self.is_google, 40),
                (self.is_microsoft, 30),
                (self.is_yahoo, 20),
                (self.is_others, 10)]
            for is_test, weight in weights:
                t, n = is_test(d)
                if t:
                    self.weights.append(weight/n)
                    break

    # Record DSN diags as a grouped, nested structure in the form [ domain ( ..) ]
    def add(self, domain, code, enhanced, text):
        if not domain in self.domain_codes:
            self.domain_codes[domain] = []
        self.domain_codes[domain].append( (code, enhanced, text) )

    def rand_domain(self):
        dlist = random.choices(self.domains, self.weights)
        return dlist[0]

    # Return a random bounce (code, enhanced, text) for a given domain and recipient
    def rand_bounce(self, domain, recip_addr:str):
        codes = self.domain_codes[domain] # note this returns a list, so have to dereference it
        code, enhanced, text = random.choice(codes) # pick from the codes with an even distribution
        # Fill in placeholders
        placeholders = [
            ('{{to}}', self.bounce_to),
            ('{{verp}}', self.bounce_verp),
            ('{{ip4addr}}', self.bounce_ip4addr),
            ('{{datetime}}', self.bounce_datetime),
            ('{{datetime_uuid}}', self.bounce_datetime_uuid),
            ('{{google_uuid}}', self.bounce_google_uuid),
        ]
        for holder, func in placeholders:
            text = text.replace(holder, func(recip_addr))
        return code, enhanced, text

    def bounce_to(self, t):
        return t

    # e.g. <corrina244443-taylordavidg=shaw.ca@promonearme.com>
    # wikipedians-owner+bob=example.org@example.net
    def bounce_verp(self, t):
        localpart, domainpart = t.split('@')
        v = '<mylist123-owner+' + localpart + '=' + domainpart + '@example.com>'
        return v

    def bounce_ip4addr(self, t):
        return '{}.{}.{}.{}'.format(random.randint(0, 255), random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))

    # e.g. 2023-06-13T23:35:18.453Z
    def bounce_datetime(self, t):
        return datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.000Z")

    # e.g. 08DB6BB234EB8972
    def bounce_datetime_uuid(self, t):
        n = random.randint(0, 16**15)
        return f'0{n:15X}'

    # e.g. b5-20020a1709062b4500b0096f6a9105absi8004221ejg.48, zm10-20020a170906994a00b009745adb3c21si7135862ejb.428
    def bounce_google_uuid(self, t):
        n = random.randint(0, 16**15)
        n2 = random.randint(0, 16**15)
        s = rand_ascii_letter() + rand_digit() + '-' + f'0{n:15x}' + rand_ascii_letter() + rand_ascii_letter() + rand_ascii_letter() + f'0{n2:15x}' +\
            rand_ascii_letter() + rand_ascii_letter() + rand_ascii_letter() + '.' + str(random.randint(0,999))
        return s

    def is_google(self, d):
        domains = ['gmail.com']
        return (d in domains), len(domains)

    def is_microsoft(self, d):
        domains = ['hotmail.com', 'msn.com', 'hotmail.co.jp', 'live.com', 'outlook.com', 'hotmail.co.uk', 'hotmail.fr', 'live.jp', 'hotmail.de',
            'live.co.uk', 'hotmail.es', 'live.fr', 'live.in']
        return (d in domains), len(domains)

    def is_yahoo(self, d):
        domains = ['yahoo.ca', 'yahoo.co.in', 'yahoo.co.jp', 'yahoo.co.uk', 'yahoo.com', 'yahoo.com.br', 'yahoo.de', 'yahoo.es', 'yahoo.gr', 
            'yahoo.ie', 'yahoo.in', 'yahoo.it']
        return (d in domains), len(domains)

    def is_others(self, d):
        return True, len(self.domain_codes) # Note this is slightly on the low side 


def rand_ascii_letter():
    return random.choice(string.ascii_lowercase)


def rand_digit():
    return random.choice(string.digits)


# -----------------------------------------------------------------------------------------
# Configurable email content
# -----------------------------------------------------------------------------------------
class EmailContent:
    def __init__(self, sender_subjects_file, html_file, txt_file: io.BufferedReader):
        self.content = []
        # Ignore any extra fields such as count
        r = csv.DictReader(sender_subjects_file, fieldnames=['x_job', 'from_name', 'from_addr', 'bounce_rate', 'subject'])
        for row_dict in r:
            if row_dict['x_job'] != 'x_job': # skip the header row
                self.add(row_dict)

        self.htmlTemplate = html_file.read()
        self.textTemplate = txt_file.read()

    def add(self, sender_subject):
        self.content.append(sender_subject)

    # generate a bunch of random related things for the email
    def rand_job_subj_text_html_from(self):
        s = random.choice(self.content)
        from_address = Address(s['from_name'], s['from_addr'])
        # Contents include a valid link
        text = self.textTemplate.replace('{{top}}', s['x_job']).replace('{{name}}', s['from_name'])
        html = self.htmlTemplate.replace('{{top}}', s['x_job']).replace('{{name}}', s['from_name'])
        return s['x_job'], s['subject'], text, html, from_address, float(s['bounce_rate'])


# Generator yielding a list of n randomized messages
def rand_messages(n: int, names: NamesCollection, content: EmailContent, bounces: BounceCollection):
    for i in range(n):
        yield rand_message(names, content, bounces)


def rand_message(names: NamesCollection, content: EmailContent, bounces: BounceCollection):
        recip_domain = bounces.rand_domain()
        recip_addr = names.rand_recip(recip_domain)
        msg = EmailMessage()
        x_job, subject, body_text, body_html, from_addr, bounce_rate = content.rand_job_subj_text_html_from()
        msg['Subject'] = subject
        msg['From'] = from_addr
        msg['To'] = recip_addr
        msg['X-Job'] = x_job
        # special configurable bounce rates for Yahoo domains
        percent = 40
        if x_job == 'Phil':
            percent = 40
        if bounces.yahoo_backoff:
            t, _ = bounces.is_yahoo(recip_domain)
            if t:
                bounce_rate = bounces.yahoo_backoff
        # check and mark the message to bounce in the header
        if random.random() <= bounce_rate:
            code, enhanced, bounce_text = bounces.rand_bounce(recip_domain, recip_addr.username)
            msg['X-Bounce-Me'] = f'{code} {enhanced} {bounce_text}'
            msg['X-Bounce-Percentage'] = str(percent) # Pass in a <100 bounce percentage, so that deferred messages will eventually clear
        msg.set_content(body_text)
        msg.add_alternative(body_html, subtype='html')
        return msg

# -----------------------------------------------------------------------------
# Main code - for testing
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    with open('demo_bounces.csv', 'r') as bounce_file:
        bounces = BounceCollection(bounce_file, yahoo_backoff = 0.8)
        with open('sender_subjects.csv', 'r') as sender_subjects_file:
            with open('emailcontent.html', 'r') as html_file:
                with open('emailcontent.txt', 'r') as txt_file:
                    content = EmailContent(sender_subjects_file, html_file, txt_file)
                    nNames = 50
                    names = NamesCollection(nNames) # Get some pseudorandom recipients
                    msgs = rand_messages(100, names, content, bounces)
                    for m in msgs:
                        print(m['from'],m['to'],m['subject'])
