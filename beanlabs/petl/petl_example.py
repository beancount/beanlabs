#!/usr/bin/env python3
"""Example processing postings using petl.
"""

from beancount import loader
from beancount.core import data

import argparse
import itertools
import petl

petl.config.look_style = "minimal"
petl.config.failonerror = True


HEADER = ["txn", "posting", "date", "account", "units", "cost"]


def rows(entries):
    for txn in data.filter_txns(entries):
        for posting in txn.postings:
            yield (txn, posting, txn.date, posting.account, posting.units, posting.cost)


def main():
    parser = argparse.ArgumentParser(description=__doc__.strip())
    parser.add_argument("filename", help="Ledger filename")
    args = parser.parse_args()

    entries, errors, options_map = loader.load_file(args.filename)
    table = petl.wrap(itertools.chain([HEADER], rows(entries)))
    print(table.cut(["date", "account", "units"]).lookallstr())


if __name__ == "__main__":
    main()
