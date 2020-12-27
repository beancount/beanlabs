#!/usr/bin/env python3
"""Various tests for beancount.

(This is the main test program I fiddle with during development.)
"""
__copyright__ = "Copyright (C) 2013-2018  Martin Blais"
__license__ = "GNU GPLv2"

import datetime
import argparse
import contextlib
import io
import re
import sys
import time
import logging
from collections import defaultdict, namedtuple
from decimal import Decimal

import pandas
import matplotlib #; matplotlib.use('qt4agg')
from matplotlib import pyplot

from beancount.core import data
from beancount.core.data import Transaction, Price
from beancount.core import realization
from beancount.core import convert
from beancount.ops import summarize
from beancount.ops import validation
from beancount.core.data import render_fileloc, format_entry
from beancount.core.inventory import Inventory
from beancount.core.realization import dump_tree_balances
from beancount import load
from beancount import parser
from beancount import utils
from beancount.utils.bisect_key import bisect_left_withkey
from beancount.core import prices
from beancount.core.account import account_type, account_name_sortkey



# A generic tuple to return various data by account type.
AccountTypeData = namedtuple('AccountTypeData', 'Assets Liabilities Equity Income Expenses')



def compute_balance_by_type(real_accounts, date):
    """Compute the total balance for each account type, evaluated at the given
    date. Returns a tuple with an inventor for each accoutn type."""

    balances = {typename: Inventory()
                for typename in AccountTypeData._fields}
    for real_account in real_accounts:
        if real_account.postings:
            typename = account_type(real_account.fullname)
            assert False, "FIXME: This doesn't work anymore; we need to use the entries in order to compute the balance at a specific date."
            balance = realization.find_balance(real_account, date)
            balances[typename] += balance

    return AccountTypeData(**balances)


def compute_yearly_balances(real_accounts):
    """Given a realization, compute the yearly balances of each account type."""

    data = {}
    for balance_date in (datetime.date(year, 1, 1) for year in range(2004, 2015)):
        balances = compute_balance_by_type(real_accounts, balance_date)
        rows = []
        for account_type, balance in balances._asdict().items():
            costs = balance.reduce(convert.get_cost).get_amounts()
            index = [cost.currency for cost in costs]
            series = pandas.Series([cost.number for cost in costs], index=index)
            rows.append(series)
        date_data = pandas.DataFrame(rows, index=AccountTypeData._fields)
        data[balance_date] = date_data

    return pandas.Panel.from_dict(data)


def check_equity_balances(real_accounts):
    """Try to figure out which method is best to summarize income/expenses into equity.
    Comparing (I+X) with (A+L), they really should be equal."""

    year_range = range(2004, 2015)
    for balance_date in (datetime.date(year, 1, 1) for year in year_range):
        print('------------------------', balance_date)
        balances = compute_balance_by_type(real_accounts, balance_date)

        balsheet_inventory = balances.Assets + balances.Liabilities + balances.Equity
        income_inventory = balances.Income + balances.Expenses

        print('A+L+E     (cost): {}'.format(balsheet_inventory.reduce(convert.get_cost)))
        print('I+X       (cost): {}'.format(income_inventory.reduce(convert.get_cost)))
        print('A+L+E+I+X (cost): {}'.format((balsheet_inventory +
                                             income_inventory).reduce(convert.get_cost)))

        # We need to synthesize a transaction here instead of doing this.
        conversions = -(balsheet_inventory + income_inventory)
        print('Conversions:   {}'.format(conversions.reduce(convert.get_cost)))
        balsheet_inventory += conversions.reduce(convert.get_cost)

        assert (balsheet_inventory + income_inventory).reduce(convert.get_cost).is_empty()
        # print('A+L+E+I+X (pos) ', (balsheet_inventory + income_inventory))
        print('A+L+E+I+X (cost)', (balsheet_inventory +
                                   income_inventory).reduce(convert.get_cost))

        balances_fwd = compute_balance_by_type(real_accounts, balance_date + datetime.timedelta(days=365))
        print('balances_fwd', balances_fwd)
        conversions_fwd = -(balances_fwd.Assets +
                            balances_fwd.Liabilities +
                            balances_fwd.Equity +
                            balances_fwd.Income +
                            balances_fwd.Expenses)
        print('conversions_fwd', conversions_fwd)
        print('conversions_diff', (conversions.reduce(convert.get_cost) +
                                   (-conversions_fwd).reduce(convert.get_cost)))


#-------------------------------------------------------------------------------


def main():
    argparser = argparse.ArgumentParser(description=__doc__)

    argparser.add_argument('filename',
                        help='Beancount input filename.')

    opts = argparser.parse_args()

    with utils.log_time('load', logging.info):
        entries, errors, options = load(opts.filename, logging.info)

    for entry in entries:
        print(format_entry(entry))
    raise SystemExit

    with utils.log_time('compute_total_balance', logging.info):
        summarize.compute_total_balance(entries)

    with utils.log_time('realize', logging.info):
        real_accounts = realization.realize(entries)

    print('LEN', len(entries))

    with utils.log_time('clamp', logging.info):
        previous_accounts = parser.parser.get_previous_accounts(options)
        entries, index = summarize.clamp(entries,
                                         datetime.date(2013, 1, 1),
                                         datetime.date(2014, 1, 1),
                                         options,
                                         *previous_accounts)


    if 0:
        # Test out summarization.
        real_log = open('/tmp/real.log', 'w')
        dump_tree_balances(real_accounts, real_log)
        total_balance = summarize.compute_total_balance(entries)
        # print("TRIAL_BALANCE", total_balance, file=real_log)
        # print("TRIAL_BALANCE (cost)", total_balance.reduce(convert.get_cost), file=real_log)

        with utils.log_time('summarize', logging.info):
            account_opening = data.Account('Equity:OpeningBalances', 'Equity')
            sum_entries, _ = summarize.summarize(entries, datetime.date(2012, 1, 1), account_opening)
            sumreal_accounts = realization.realize(sum_entries)

            sum_log = open('/tmp/sum.log', 'w')
            dump_tree_balances(sumreal_accounts, sum_log)
            total_balance = summarize.compute_total_balance(sum_entries)
            # print("TRIAL_BALANCE", total_balance, file=sum_log)
            # print("TRIAL_BALANCE (cost)", total_balance.reduce(convert.get_cost), file=sum_log)


    if 0:
        check_equity_balances(real_accounts)

    if 0:
        yearly = compute_yearly_balances(real_accounts)

        print(yearly.to_frame().to_string())
        # print(yearly.major_xs('Assets').to_string())
        USD = yearly.minor_xs('USD')
        CAD = yearly.minor_xs('CAD')
        total = USD + CAD
        print(total.to_string())
        # print(yearly.minor_xs('CAD').to_string())

        sums = total.sum(axis=0)
        print(sums.to_string())
        total.plot()
        pyplot.show()


def print_debug_account(real_account):
    for posting in real_account.postings:
        print('{} {:48} {:72}'.format(posting.entry.date,
                                      ' | '.join([posting.entry.payee or '', posting.entry.narration]),
                                      posting.position,
                                      ))

def pretty_transaction(txn):
    """Format nicely a transaction for printing. Returns a string"""
    lines = ["{} {} {} | {} {}".format(txn.date, txn.flag, txn.payee or '', txn.description,
                                         ','.join(txn.tags))]
    for post in txn.postings:
        lines.append("  {:1} {:58s} {} {} {}".format(
            chr(post.flag) if post.flag else '', post.account.name, post.position.number, post.position.lot, post.price or ''))
    return '\n'.join(lines)


def print_locations(entries):
    for e in entries:
        if isinstance(e, Event) and e.type == 'location':
            print(e)


def print_open_close(entries):

    accmap = defaultdict(list)
    for e in entries:
        if isinstance(e, (Open, Close)):
            accmap[e.account].append(e)

    for account, openclose in accmap.items():
        if is_balance_sheet_account(account.name):
            print(account)
            for e in openclose:
                print('  ', e)


def print_tags(entries):

    tagsmap = defaultdict(list)
    for e in entries:
        if isinstance(e, data.Transaction):
            for tag in e.tags:
                tagsmap[tag].append(e)

    for tag, entry_list in tagsmap.items():
        print
        print(tag)
        for e in entry_list:
            print('  ', e)


def unique_alias(account):
    if (account.type == 'Expenses' and
        not re.search(':Taxes:', account.name)):
        return 'Expenses:*'
    else:
        return account.name


def find_unique_templates(entries):
    """Filter out transactions and group them by types of accounts transacted."""

    groups = defaultdict(list)
    for entry in utils.filter_type(entries, data.Transaction):
        account_names = frozenset(sorted(unique_alias(posting.account)
                                         for posting in entry.postings))
        groups[account_names].append(entry)

    print(len(groups))

    for account_names, entry_list in sorted(groups.items(), key=lambda x: len(x[1]), reverse=True):
        print(tuple(sorted(account_names, key=account_name_sortkey)), len(entry_list))



def print_entries_by_date(entries):
    prev_date = None
    for entry in entries:
        if prev_date != entry.date:
            print()
            prev_date = entry.date
        print(entry)

def measure_balance_total(entries):
    # For timing only.
    with utils.log_time('balance_all', logging.info): # 89ms... okay.
        balance = Inventory()
        for entry in utils.filter_type(entries, data.Transaction):
            for posting in entry.postings:
                balance.add_position(posting.position)


def print_real_accounts(real_accounts):
    for real_account in sorted(real_accounts):
        print('{:56} {}'.format(real_account.fullname, real_account.account))


if __name__ == '__main__':
    main()
