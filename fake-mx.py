#!/usr/bin/env python3
#
# Create fake MX and A records for recipient domains to enable loopback to a sink via a local "unbound" DNS resolver

import argparse, dns.resolver
from typing import Iterable
from emailcontent import *

class myDNS:
    def __init__(self, domains:Iterable):
        self.domains = domains
        self.mx_records = []
        self.exchanges = []
        self.width = 60 # column width for domain names
        # Merge a list of real MX records, collecting the exchanges as we go
        for domain in domains:
            result = dns.resolver.resolve(domain, 'MX')
            self.mx_records += list(self.mx_record_gen(domain, result))

    # Return each MX as a simple tuple
    def mx_record_gen(self, domain:string, result:tuple):
        for answer in result:
            preference, exchange = answer.preference, answer.exchange.to_text()
            self.exchanges.append(exchange)
            yield (domain, preference, exchange)

    def print(self, prefix:string, suffix:string):
        fake_ip = '127.0.0.1'
        for domain in self.exchanges:
            print(f'{prefix}{domain:<{self.width}} IN A    {fake_ip}{suffix}')

        for (domain, preference, exchange) in self.mx_records:
            print(f'{prefix}{domain:<{self.width}} IN MX {preference:<5} {exchange}{suffix}')

# -----------------------------------------------------------------------------
# Main code
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description='Create fake MX and A records for recipient domains to enable loopback to a sink via a local "unbound" DNS resolver')
    parser.add_argument('--bounces', type=argparse.FileType('r'), required=True, help='bounce configuration file (csv)')
    args = parser.parse_args()

    bounces = BounceCollection(args.bounces)
    # List of all domains, deduped and alphabetically sorted
    my_records = myDNS(sorted(set(bounces.all_domains())))
    my_records.print('  local-data: "', '"')