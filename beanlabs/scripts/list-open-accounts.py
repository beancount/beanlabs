#!/usr/bin/env python3
"""List all open accounts.

This is a script that can produce a comprehensive list of all open accounts.
This is helpful when you want to revise your ledger to find accounts that should
have been closed.
"""
__copyright__ = "Copyright (C) 2022  Martin Blais"
__license__ = "GNU GPLv2"

import argparse
import re
import pprint
import datetime as dt

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


def last(it):
    for elem in it:
        pass
    return elem


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("filename", help="Filename.")
    args = parser.parse_args()

    entries, errors, options_map = loader.load_file(args.filename)
    acctypes = options.get_account_types(options_map)
    real = realization.realize(entries, compute_balance=True)

    ocmap = getters.get_account_open_close(entries)
    accounts = [
        (account, open_.date) for account, (open_, close) in ocmap.items() if not close
    ]

    def get_last_date(account):
        real_account = realization.get(real, account)
        last_txn_posting = last(realization.iter_children(real_account))
        last_posting = last_txn_posting.txn_postings[-1]
        if isinstance(last_posting, TxnPosting):
            return last_posting.txn.date
        else:
            return last_posting.date

    def get_balance(account):
        balance = realization.get(real, account).balance
        return balance.reduce(convert.get_units)

    def get_sort_key(rec):
        account_type = account_types.get_account_type(rec.account)
        if account_type in (acctypes.assets,
                            acctypes.liabilities,
                            acctypes.income):
            return (0, rec.account_sans, rec.type)
        else:
            return (1, rec.type, rec.account_sans)

    one_day = dt.timedelta(days=1)

    def get_close(rec):
        close_date = rec.last_date + one_day
        return f"{close_date} close {rec.account}"

    table = petl.wrap([("account", "open_date")] + accounts)
    today = dt.date.today()
    table = (
        table.addfield("type", lambda r: account_types.get_account_type(r.account))
        .addfield("account_sans", lambda r: account.sans_root(r.account))
        .addfield("sortkey", get_sort_key)
        .addfield("postings", lambda r: sum(1 if isinstance(tp, TxnPosting) else 0
                                            for tp in realization.get(real, r.account).txn_postings))
        .addfield("last_date", lambda r: get_last_date(r.account))
        .addfield("days_open", lambda r: (today - r.open_date).days)
        .addfield("days_active", lambda r: (r.last_date - r.open_date).days)
        .addfield("days_since", lambda r: (today - r.last_date).days)
        .addfield("balance", lambda r: get_balance(r.account))
        .addfield("close", get_close)
        .cutout("account")
        .movefield("close", 0)
        .movefield("type", 1)
        .movefield("account_sans", 2)
        .sort("sortkey")
        .cutout("sortkey")
    )
    print(table.lookallstr())


if __name__ == "__main__":
    main()
