#!/usr/bin/env python3
"""Print the lots in an account, sort in descending order.

If given a size, match that much of the size from the top.
"""

from decimal import Decimal
import argparse

from beancount import loader
from beancount.core import inventory
from beancount.core import data


def main():
    parser = argparse.ArgumentParser(description=__doc__.strip())
    parser.add_argument('filename', help='Beancount ledger filename.')
    parser.add_argument('account', help='Account name.')
    parser.add_argument('size', nargs='?', type=Decimal,
                        help='Size to match at highest cost.')
    args = parser.parse_args()

    entries, errors, options_map = loader.load_file(args.filename)

    # Accumulate lots from account.
    balance = inventory.Inventory()
    for entry in data.filter_txns(entries):
        for posting in entry.postings:
            if posting.account == args.account:
                balance.add_position(posting)

    # Book most expensive shares.
    remaining_size = args.size
    booked = []
    for pos in sorted(balance, key=lambda pos: pos.cost.number, reverse=True):
        print(pos)
        if remaining_size:
            booked_size = min(remaining_size, pos.units.number)
            booked.append((booked_size, pos))
            remaining_size -= booked_size

    # Print out booked ones, if a size was specified.
    if booked:
        print()
        print("Booked:")
        for booked_size, pos in booked:
            if booked_size != pos.units.number:
                pos = pos._replace(units=pos.units._replace(number=booked_size))
            print("  {:50}  {}".format(args.account, -pos))


if __name__ == '__main__':
    main()
