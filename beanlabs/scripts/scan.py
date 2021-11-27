#!/usr/bin/env python3
"""Scanning a list of entries and yielding partial realizations at requested timestamps.

This is an example related to
https://groups.google.com/d/msgid/beancount/20211127101046.tw5yy4x6b4ooxvmp%40upsilon.cc
"""

from beancount import loader
from beancount.core import data
from beancount.core.data import Account
from beancount.core.inventory import Inventory

import argparse
import collections
import datetime
import logging
from pprint import pprint
from typing import Callable, Dict, Iterator, List, Set, Optional, Tuple


def gen_dates(entries, num_periods) -> List[datetime.date]:
    """Generate 'num_periods' dates over entries."""

    min_date, max_date = datetime.date(3000, 1, 1), datetime.date(1970, 1, 1)
    for entry in data.filter_txns(entries):
        if entry.date < min_date:
            min_date = entry.date
        if entry.date > max_date:
            max_date = entry.date

    min_days = min_date.toordinal()
    max_days = max_date.toordinal()
    days_interval = int((max_days - min_days) / num_periods)
    return [datetime.date.fromordinal(day)
            for day in range(min_days, max_days, days_interval)] + [max_date]


def scan(
        entries: data.Entries,
        dates: List[datetime.date],
        accounts_filter: Optional[Callable[[Account], bool]] = None
) -> Iterator[Tuple[datetime.date, Dict[Account, Inventory]]]:
    """Scan through 'entries' yielding a dict of balances at the given dates."""

    if not entries:
        return

    balances = collections.defaultdict(Inventory)
    date_iter = iter(dates)
    next_date = next(date_iter)
    for entry in data.filter_txns(entries):
        if entry.date >= next_date:
            clean_dict = {account: inv
                          for account, inv in balances.items()
                          if not inv.is_empty()}
            yield next_date, clean_dict
            try:
                next_date = next(date_iter)
            except StopIteration:
                break
        for posting in entry.postings:
            if accounts_filter and not accounts_filter(posting.account):
                continue
            balances[posting.account].add_position(posting)


def main():
    logging.basicConfig(level=logging.INFO, format='%(levelname)-8s: %(message)s')
    parser = argparse.ArgumentParser(description=__doc__.strip())
    parser.add_argument('filename', help='Beancount filename')
    parser.add_argument('-n', '--num-periods', action='store', type=int, default=10,
                        help="Number of periods to choose")

    args = parser.parse_args()

    entries, errors, options_map = loader.load_file(args.filename)

    dates = gen_dates(entries, args.num_periods)
    for date, balances in scan(entries, dates, lambda a: a.startswith('Asset')):
        pprint((date, balances))


if __name__ == '__main__':
    main()
