
import random, names, csv
from email.headerregistry import Address

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
            handles = set()
            for row_dict in r:
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

    # Record DSN diags as a grouped, nested structure in the form
    # { domain { code { enhanced { text : count }}}}
    def add(self, domain, code, enhanced, text):
        if not domain in self.domain_codes:
            self.domain_codes[domain] = []
        self.domain_codes[domain].append( (code, enhanced, text) )

    # Return domain, code, enhanced, text
    def random(self):
        dlist = random.choices(self.domains, self.weights)
        domain = dlist[0]
        codes = self.domain_codes[domain] # note this returns a list, so have to dereference it
        code, enhanced, text = random.choice(codes) # pick from the codes with an even distribution
        # Fill in placeholders, if any

        placeholders = [
            ('{{verp}}', rand_verp),
            ('{{ip4addr}}', rand_ip4addr),
            ('{{datetime_uuid}}', rand_datetime_uuid),
            ('{{to}}', rand_to),
            ('{{google_uuid}}', rand_google_uuid)
        ]
        for holder, func in placeholders:
            text = text.replace(holder, func())

        return domain, code, enhanced, text

def rand_verp():
    return 'foo'

def rand_ip4addr():
    return 'foo'

def rand_datetime_uuid():
    return 'foo'

def rand_to():
    return 'foo'

def rand_google_uuid():
    return 'foo'

# -----------------------------------------------------------------------------------------
# Configurable email content, recipients, etc
# -----------------------------------------------------------------------------------------
class EmailContent:
    def __init__(self):
        self.htmlLink = 'http://example.com/index.html'

        self.content = [
            {'X-Job': 'Todays_Sales', 'subject': 'Today\'s sales'},
            {'X-Job': 'Newsletter', 'subject': 'Newsletter'},
            {'X-Job': 'Last_Minute_Savings', 'subject': 'Savings'},
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

#TODO: add placeholder text and images

        self.textTemplate = \
'''
Plain text - URL here {}
'''
        self.sender = [
            {'from': 'alice@acme-adventures.com', 'name': 'Acme Adventures'},
            {'from': 'bob@burgers.com', 'name': 'Bob\'s Burgers'},
            {'from': 'charlie@creative-climbing.com', 'name': 'Creative Climbing'},
            {'from': 'danii@dance-studios.com', 'name': 'Dance Studios'},
        ]


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

