#!/usr/bin/env python3
"""Load up a ledger and match against various parts of the entries in a way
that one can iterate with Emacs.
"""
__copyright__ = "Copyright (C) 2013-2018  Martin Blais"
__license__ = "GNU GPLv2"

import re

from beancount import load
from beancount import utils
from beancount.core import data


def main():
    import argparse
    optparser = argparse.ArgumentParser(description=__doc__)
    optparser.add_argument('filename', help='Filename.')

    optparser.add_argument('-q', '--quiet', action='store_true',
                           help="Don't print file or line numbers.")

    optparser.add_argument('-a', '--account', metavar='REGEXP', action='store',
                           help="Match against the account names.")

    optparser.add_argument('-t', '--tag', metavar='REGEXP', action='store',
                           help="Match against the tag names of Transactions.")

    optparser.add_argument('-i', '--invert', action='store_true',
                           help="Invert signs on all the postings.")

    opts = optparser.parse_args()

    # Parse the input file.
    entries, errors, options = load(opts.filename)

    # Create a mapping from a unique value (we're using the fileloc) to the
    # entry objects.
    entry_map = {entry.fileloc: entry for entry in entries}

    # Initialized the reduced list to the entire set of keys.
    filtered_keys = set(entry_map.keys())

    # Filter by matching a regexp against the account name.
    if opts.account:
        account_keys = set()
        regexp = re.compile(opts.account)
        for entry in entries:
            # Iterate over all references to accounts.
            for account in utils.get_tuple_typed_values(entry, data.Account):
                if regexp.match(account.name):
                    account_keys.add(entry.fileloc)

        filtered_keys = filtered_keys.intersection(account_keys)

    # Filter by matching a regexp against the tags.
    if opts.tag:
        tag_keys = set()
        regexp = re.compile(opts.tag)
        for entry in utils.filter_type(entries, data.Transaction):
            if any(map(regexp.match, entry.tags)):
                tag_keys.add(entry.fileloc)

        filtered_keys = filtered_keys.intersection(tag_keys)

    # Print out the match results that have filtered through.
    filtered_entries = list(map(entry_map.get, filtered_keys))

    # Sort the entries by date, and then by location in the file.
    filtered_entries.sort(key=lambda entry: (entry.date, entry.fileloc))

    # Invert the signs if requested; this is convenient for undoing entries.
    for entry in utils.filter_type(filtered_entries, data.Transaction):
        for posting in entry.postings:
            # Note: modify in-place; there's nothing interesting going on there
            # after.
            posting.position.number = -posting.position.number

    # Print out something about each entry.
    for entry in filtered_entries:
        if not opts.quiet:
            print()
            print('{}'.format(data.render_fileloc(entry.fileloc)))
            print()
        print(data.format_entry(entry))


if __name__ == '__main__':
    main()
