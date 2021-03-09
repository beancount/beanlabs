#!/usr/bin/env python3
"""In Beancount v2, there is no built-in support for annotating trade matches.

However, you can iterate over the transactions to extract and produce them.

That is, reductions from an inventory should generate (buy, sell) pairs, or more
generally, pairs of (augmentation, reduction).
"""
__copyright__ = "Copyright (C) 2021  Martin Blais"
__license__ = "GNU GPLv2"


import argparse
import collections
import datetime

import dateutil.parser
import petl
petl.config.look_style = 'minimal'

from beancount import loader
from beancount.core import data
from beancount.core import inventory
from beancount.core import position


def main():
    date_parser = lambda s: dateutil.parser.parse(s).date()
    parser = argparse.ArgumentParser(description=__doc__.strip())

    parser.add_argument('-s', '--start-date', action='store', type=date_parser,
                        help="Start date to timespan to filter")
    parser.add_argument('-e', '--end-date', action='store', type=date_parser,
                        help="End date of timespan to filter")

    parser.add_argument('filename', help='Beancount ledger file')
    args = parser.parse_args()

    entries, _, options_map = loader.load_file(args.filename)

    if args.start_date:
        entries = (entry for entry in entries if entry.date >= args.start_date)
    if args.end_date:
        entries = (entry for entry in entries if entry.date < args.end_date)

    balances = collections.defaultdict(inventory.Inventory)
    rows = [('open_date', 'open_posting', 'close_date', 'close_posting', 'close_price')]
    for entry in data.filter_txns(entries):
        for posting in entry.postings:
            account_balance = balances[posting.account]
            closing = position.get_position(posting)
            price = posting.price
            opening, booking = account_balance.add_position(posting)
            if posting.cost is not None and booking == inventory.MatchResult.REDUCED:
                rows.append((opening.cost.date, opening, entry.date, closing, price))

    table = petl.wrap(rows)
    print(table.lookallstr())


if __name__ == '__main__':
    main()
