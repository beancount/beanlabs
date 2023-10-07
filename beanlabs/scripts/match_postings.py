#!/usr/bin/env python3
"""Given ledgers and account regexps, match postings of the first to the second.

This essentially creates a cross-referencing matching between the subset of
postings of the left file into the subset of postings of the second. This can be
used to match up transactions between a project or trip ledger to transactions
from a personal ledger.

For example, in a trip ledger, an income contribution may look like this:

  2016-06-15 * "Hertz" "Rental Car" ^753c63a9d5d9
    Expenses:Transportation:Car-Rental    393.13 USD
    Income:Martin:CreditCard

Whereas in one's personal ledger file, the corresponding expense might show up
like this:

  2016-06-15 * "HERTZ CAR RENTAL    800-654-417" ^753c63a9d5d9
    Liabilities:US:Sapphire        -393.13 USD
    Assets:Travel:Pending:France

This scripts make it possible to verify that all the transactions from the first
appear into the second.
"""
__copyright__ = "Copyright (C) 2016-2022  Martin Blais"
__license__ = "GNU GPLv2"

import re
import collections
import itertools
import pprint

import dateutil.parser

from beancount.parser import printer
from beancount.core import amount
from beancount.core import data
from beancount import loader


def get_postings(filename, account_regexp, tag=None):
    if tag:
        match = lambda entry, posting: (
            re.match(account_regexp, posting.account) and tag in entry.tags
        )
    else:
        match = lambda _, posting: (re.match(account_regexp, posting.account))

    entries, _, _ = loader.load_file(filename)
    txn_postings = [
        data.TxnPosting(entry, posting)
        for entry in data.filter_txns(entries)
        for posting in entry.postings
        if match(entry, posting)
    ]
    return txn_postings


def index_postings(txn_postings, func):
    # Note: This is only required because itertools.groupby() is order-related.
    amount_map = collections.defaultdict(list)
    for txn_posting in txn_postings:
        amount_map[func(txn_posting)].append(txn_posting)
    return amount_map


def match_postings(left_postings, rght_postings, keyfun):
    left_map = index_postings(left_postings, keyfun)
    rght_map = index_postings(rght_postings, keyfun)

    common_keys = set(left_map) & set(rght_map)
    matched = []
    for units in common_keys:
        left_postings = left_map[units]
        rght_postings = rght_map[units]
        if len(left_postings) == 1 and len(rght_postings) == 1:
            del left_map[units]
            del rght_map[units]
            continue

        if 1:
            meta = {
                "left": left_postings[0].txn.narration,
                "rght": rght_postings[0].txn.narration,
            }
            txn = data.Transaction(
                meta,
                left_postings[0].txn.date,
                "*",
                None,
                "",
                None,
                None,
                [
                    left_postings[0].posting,
                    rght_postings[0].posting,
                ],
            )
            printer.print_entry(txn)

    left_remain = list(itertools.chain.from_iterable(left_map.values()))
    rght_remain = list(itertools.chain.from_iterable(rght_map.values()))
    return matched, (left_remain, rght_remain)


def print_unmatched(txn_postings, filename, regexp):
    if not txn_postings:
        return
    print()
    print()
    print('=== Ummatched from {}, "{}"'.format(filename, regexp))
    print()
    for txn_posting in sorted(txn_postings, key=lambda tp: tp.txn.date):
        printer.print_entry(txn_posting.txn)


def parse_date(string):
    return dateutil.parser.parse(string).date()


def main():
    import argparse, logging

    logging.basicConfig(level=logging.INFO, format="%(levelname)-8s: %(message)s")
    parser = argparse.ArgumentParser(description=__doc__.strip())
    parser.add_argument("filename_left", help="Left filename")
    parser.add_argument("regexp_left", help="Left account regexp")
    parser.add_argument(
        "--tag", dest="tag_left", help="Tag to filter left file (optional)"
    )
    parser.add_argument("filename_rght", help="Right filename")
    parser.add_argument("regexp_rght", help="Right account regexp")
    parser.add_argument('-d', '--min-date', action='store', type=parse_date,
                        help="Minimum date to consider in the postings.")
    parser.add_argument('-v', '--verbose', action='store_true',
                        help="Verbose output, print out matched transactions.")
    args = parser.parse_args()

    left_postings = get_postings(args.filename_left, args.regexp_left, args.tag_left)
    rght_postings = get_postings(args.filename_rght, args.regexp_rght)
    # print(len(left_postings), len(rght_postings))

    if args.min_date:
        left_postings = [tp for tp in left_postings if tp.txn.date >= args.min_date]
        rght_postings = [tp for tp in rght_postings if tp.txn.date >= args.min_date]
    # print(len(left_postings), len(rght_postings))

    # Progressively try different unique keys to match up postings to each other
    # unambiguously.
    # for keyfun in [lambda tp: amount.abs(tp.posting.units), lambda tp: tp.txn.links]:
    for keyfun in [lambda tp: tp.txn.links]:
        matched, (left_postings, rght_postings) = match_postings(
            left_postings, rght_postings, keyfun
        )
        if args.verbose:
            print()
            print()
            print('=== Matched')
            print()
            printer.print_entries(matched)

    if len(left_postings):
        print(
            "Unmatched from left: {} postings".format(len(left_postings))
        )
        print_unmatched(left_postings, args.filename_left, args.regexp_left)

    if len(rght_postings):
        print(
            "Unmatched from right: {} postings".format(len(rght_postings))
        )
        print_unmatched(rght_postings, args.filename_rght, args.regexp_rght)


if __name__ == "__main__":
    main()
