#!/usr/bin/env python3

import random, names, csv
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
    def __init__(self, bounce_filename):
        self.domain_codes = {}
        self.domains = []
        self.weights = []

        with open(bounce_filename) as bounce_file:
            r = csv.DictReader(bounce_file, fieldnames=['domain', 'code', 'enhanced', 'text']) # Ignore any extra fields such as count
            for row_dict in r:
                if row_dict['domain'] != 'domain': # skip the header row
                    self.add(row_dict['domain'], row_dict['code'], row_dict['enhanced'], row_dict['text'])

            total_domains = len(self.domain_codes)
            msft_domains = ['hotmail.com', 'msn.com', 'hotmail.co.jp', 'live.com', 'outlook.com', 'hotmail.co.uk', 'hotmail.fr', 'live.jp', 'hotmail.de', 
                            'live.co.uk', 'hotmail.es', 'live.fr', 'live.in']
            # give more weight to some domains
            for d, v in self.domain_codes.items():
                self.domains.append(d)
                if d == 'gmail.com':
                    w = 40
                elif d in msft_domains:
                    w = 30/len(msft_domains)
                else:
                    w = 30/total_domains
                self.weights.append(w)

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
            ('{{to}}', bounce_to),
            ('{{verp}}', bounce_verp),
            ('{{ip4addr}}', bounce_ip4addr),
            ('{{datetime_uuid}}', bounce_datetime_uuid),
            ('{{google_uuid}}', bounce_google_uuid),
        ]
        for holder, func in placeholders:
            text = text.replace(holder, func(recip_addr))
        return code, enhanced, text

def bounce_to(t):
    return t

def bounce_verp(t):
    return 'foo'

def bounce_ip4addr(t):
    return '{}.{}.{}.{}'.format(random.randint(0, 255), random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))

def bounce_datetime_uuid(t):
    return 'foo'

def bounce_google_uuid(t):
    return 'foo'

# -----------------------------------------------------------------------------------------
# Configurable email content
# -----------------------------------------------------------------------------------------
class EmailContent:
    def __init__(self):
        self.htmlLink = 'http://example.com/index.html'

        self.content = [
            {'X-Job': 'Todays_Sales', 'subject': 'Today\'s 🔥 sales'},
            {'X-Job': 'Newsletter', 'subject': 'Today\'s Newsletter'},
            {'X-Job': 'Last_Minute_Savings', 'subject': 'Big savings 💰'},
            {'X-Job': 'Password_Reset', 'subject': 'Password reset'},
            {'X-Job': 'Welcome_Letter', 'subject': 'Welcome to our club 🥳'},
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
#TODO: add placeholder text and images
        self.textTemplate = 'Plain text - URL here {}'

        self.sender = [
            {'shortname': 'Acme', 'from': 'alice@acme-adventures.com', 'name': 'Acme Adventures'},
            {'shortname': 'Bobs', 'from': 'bob@burgers.com', 'name': 'Bob\'s Burgers'},
            {'shortname': 'Chaz', 'from': 'charlie@creative-climbing.com', 'name': 'Creative Climbing'},
            {'shortname': 'Dani', 'from': 'dani@dance-studios.com', 'name': 'Dani\'s Dance Studios'},
        ]

    # generate a bunch of random related things for the email
    def rand_job_subj_text_html_from(self):
        s = random.choice(self.sender)
        from_address = Address(s['name'], s['from'])
        # Contents include a valid link
        c = random.choice(self.content)
        text = self.textTemplate.format(self.htmlLink)
        html = self.htmlTemplate.format(self.htmlLink, self.htmlLink)
        job = s['shortname'] + '_' + c['X-Job']
        return job, c['subject'], text, html, from_address


# Generator yielding a list of n randomized messages
def rand_messages(n: int, names: NamesCollection, content: EmailContent, bounces: BounceCollection, bounce_probability: float):
    for i in range(n):
        yield rand_message(names, content, bounces, bounce_probability)


def rand_message(names: NamesCollection, content: EmailContent, bounces: BounceCollection, bounce_probability: float):
        recip_domain = bounces.rand_domain()
        recip_addr = names.rand_recip(recip_domain)
        code, enhanced, bounce_text = bounces.rand_bounce(recip_domain, recip_addr.username)

        msg = EmailMessage()
        x_job, subject, body_text, body_html, from_addr = content.rand_job_subj_text_html_from()
        msg['Subject'] = subject
        msg['From'] = from_addr
        msg['To'] = recip_addr
        msg['X-Job'] = x_job
        # check and mark the message to bounce in the header
        if random.random() <= bounce_probability:
            msg['X-Bounce-Me'] = f'{code} {enhanced} {bounce_text}'
        # msg['X-Bounce-Percentage'] = '5' # Don't let the sink choose the bounce percentage
        msg.set_content(body_text)
        msg.add_alternative(body_html, subtype='html')
        return msg

# -----------------------------------------------------------------------------
# Main code - for testing
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    bounces = BounceCollection('demo_bounces.csv')
    content = EmailContent()
    nNames = 50
    names = NamesCollection(nNames) # Get some pseudorandom recipients
    msgs = rand_messages(100, names, content, bounces, 1.0) # 0.05)
    for m in msgs:
        #print(m['from'],m['to'],m['subject'])
        print(m['X-Bounce-Me'])