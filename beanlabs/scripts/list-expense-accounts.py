#!/usr/bin/env python3
"""List all the Expenses accounts.
"""
__copyright__ = "Copyright (C) 2022  Martin Blais"
__license__ = "GNU GPLv2"

import re
import pprint

from beancount import loader
from beancount.core import data
from beancount.core import getters
from beancount.core import account_types


def main():
    import argparse
    optparser = argparse.ArgumentParser(description=__doc__)
    optparser.add_argument('filename', help='Filename.')
    opts = optparser.parse_args()

    entries, errors, options = loader.load_file(opts.filename)
    accounts = getters.get_accounts(entries)
    expenses_accounts = {a for a in accounts
                         if account_types.is_account_type('Expenses', a)}

    for a in sorted(expenses_accounts):
        print(a)


if __name__ == '__main__':
    main()
