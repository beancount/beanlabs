#!/usr/bin/env python3
"""Given an account with child account names, move the leaves to metadata.

For example, if you have been using leaf subaccounts for particular channels,
like this:

   Expenses:Online:Media:AbroadInJapan
   Expenses:Online:Media:DavidHoffman
   Expenses:Online:Media:NYTimes
   Expenses:Online:Media:WSJ

You can use this script to remove the subaccounts and move the leaves to
metadata. I call these "channels" by default. The payee field is probably
inappropriate, because it'll be an intermediary usually (e.g. Patreon).
"""
__copyright__ = "Copyright (C) 2022  Martin Blais"
__license__ = "GNU GPLv2"

import argparse
import collections
import datetime as dt
import functools
import pprint
import re

import petl

petl.config.look_style = "minimal"
petl.config.failonerror = True

from beancount import loader
from beancount.core import account
from beancount.core import account_types
from beancount.core import convert
from beancount.core import data
from beancount.core import getters
from beancount.core import realization
from beancount.core.data import TxnPosting
from beancount.parser import options
from beancount.parser import printer


def main():
    parser = argparse.ArgumentParser(description=__doc__.strip())
    parser.add_argument("filename", help="Ledger filename")
    parser.add_argument("parent_account", help="Name of parent account")
    args = parser.parse_args()

    parent_account = args.parent_account
    entries, errors, options_map = loader.load_file(args.filename)

    amendments = collections.defaultdict(list)
    for entry in data.filter_txns(entries):
        for posting in entry.postings:
            if posting.account.startswith(parent_account):
                channel = posting.account[len(parent_account) :].lstrip(account.sep)
                if not channel:
                    continue
                amendments[entry.meta["filename"]].append(
                    (posting.meta["lineno"], channel)
                )

    for filename, pairs in amendments.items():
        pairsmap = dict(pairs)
        with open(filename) as fin:
            with open(filename + ".new", "w") as fout:
                pr = functools.partial(print, file=fout, end="")
                for index, line in enumerate(fin, 1):
                    pr(re.sub(rf"{parent_account}:\S+", parent_account, line))
                    channel = pairsmap.get(index)
                    if channel:
                        pr(f'    channel: "{channel}"\n')


if __name__ == "__main__":
    main()
