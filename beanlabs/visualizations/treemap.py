#!/usr/bin/env python3
"""Generate a JavaScript treemap of balances for a subtree of accounts.
"""
__copyright__ = "Copyright (C) 2016  Martin Blais"
__license__ = "GNU GPLv2"

import re
import datetime
import json

from beancount import loader
from beancount.core import data
from beancount.parser import options
from beancount.parser import printer
from beancount.ops import summarize
from beancount.core import realization
from beancount.core import convert



def main():
    import argparse
    optparser = argparse.ArgumentParser(description=__doc__)

    optparser.add_argument('filename',
                           help='Filename.')

    optparser.add_argument('--account', '--prefix', default='Expenses',
                           help='Prefix of accounts to create treemap for.')

    # FIXME: This should eventually be converted into a filter expression.
    optparser.add_argument('--year', type=int,
                           help='Year to filter by.')

    optparser.add_argument('--currency', default='USD',
                           help='Render costs in the given currency only.')

    global opts
    opts = optparser.parse_args()

    if not opts.year:
        opts.year = datetime.date.today().year

    # Parse the input file.
    entries, _, options_map = loader.load(opts.filename)

    # Create a view for the current year.
    begin_date = datetime.date(opts.year, 1, 1)
    end_date = datetime.date(opts.year+1, 1, 1)
    year_entries, index = summarize.clamp_with_options(
        entries, begin_date, end_date, options_map)

    # Realize it into a tree.
    real_root = realization.realize(year_entries)
    real_account = real_root[opts.account]

    # Convert this into a dict suitable for JSON conversion.
    json_dict = fill(opts.account, real_account)

    output = json.dumps(json_dict, indent=1)
    print(output)


def fill(name, real_account):
    result = {"name": name}
    number = real_account.balance.reduce(convert.get_cost).get_amount(opts.currency).number
    # FIXME: TODO - convert all the amounts to a currency.

    # Note: For now we don't deal with negative numbers. We should just ignore
    # them.
    if number < 0:
        number = 0

    if len(real_account) == 0:
        result["value"] = float(number)
    if len(real_account) != 0:
        result["children"] = children = []
        if number:
            # Add a subnode for itself if a non-leaf node has a non-zero amount.
            children.append({"name": "*",
                             "value": float(number)})
        for child_name, child_account in real_account.items():
            children.append(fill(child_name, child_account))
    return result


if __name__ == '__main__':
    main()
