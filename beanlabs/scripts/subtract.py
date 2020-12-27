#!/usr/bin/env python3
"""Subtract transactions from a file which can be found in another, by link.

This script loads two Beancount files, and for each of the transactions in the
first file, it looks for transactions in the other file which also contain at
least one of the links. No other content of the transaction is compared. It
prints the remaining unmatched transactions.
"""
__copyright__ = "Copyright (C) 2013-2018  Martin Blais"
__license__ = "GNU GPLv2"

import argparse
import collections
import logging
import re

from beancount import loader
from beancount import utils
from beancount.core import data
from beancount.parser import printer


def main():
    optparser = argparse.ArgumentParser(description=__doc__)
    optparser.add_argument('filename', help='Transactions to be considered')
    optparser.add_argument('filename_diff', help='Transactions to be removed')

    optparser.add_argument('-q', '--quiet', action='store_true',
                           help="Don't print file or line numbers.")

    args = optparser.parse_args()

    # Parse the ledger files.
    entries, errors, options = loader.load_file(args.filename,
                                                log_errors=logging.error)
    entries_diff, errors_diff, options_diff = loader.load_file(args.filename_diff,
                                                               log_errors=logging.error)

    # Create a mapping from links to lists of transactions to find.
    link_map = collections.defaultdict(list)
    for entry in data.filter_txns(entries_diff):
        for link in entry.links:
            link_map[link].append(entry)

    # Filter out the transactions.
    filtered_entries = []
    for entry in data.filter_txns(entries):
        for link in entry.links:
            if link in link_map:
                break
        else:
            filtered_entries.append(entry)

    # Print out something about each entry.
    for entry in filtered_entries:
        if not args.quiet:
            print()
            print('{}'.format(printer.render_source(entry.meta)))
            print()
        print(printer.format_entry(entry))


if __name__ == '__main__':
    main()
