"""Add trading commissions to cost of positions.
"""
__copyright__ = "Copyright (C) 2013-2017  Martin Blais"
__license__ = "GNU GPLv2"

import collections

from beancount.core import data


__plugins__ = ('gains_without_cost',)


FLAG_SANSCOST = 'C'


SansCostError = collections.namedtuple('SansCostError',
                                       'fileloc message entry')


def gains_without_cost(entries, options_map):
    """Fold trading commissions into position costs.

    This is used to implement tracking of capital gains into the acquisition
    costs of positions,

    This function looks for entries with a particular flag on one of their
    postings, and then folds amounts from these flagged postings into another
    posting, one held with a cost (the transactions must have a single posting
    with an amount held at cost, otherwise that is an error).

    For example, the following transaction:

        2014-02-10 * "Buy" #gains-no-costs
          Assets:US:Invest:Cash           -5009.95 USD
          Expenses:Commissions                9.95 USD
          Assets:US:Invest:GOOG              10.00 GOOG {500.00 USD}

     Will be replaced by one like this:

        2014-02-10 * "Buy" #gains-no-costs
          Assets:US:Invest:Cash           -5009.95 USD
          Expenses:Commissions                9.95 USD
          Assets:US:Invest:GOOG              10.00 GOOG {500.995 USD}
          Income:US:Invest:Rebates           -9.95 USD

    Args:
      entries: A list of data directives.
      options_map: A dict of options, that confirms to beancount.parser.options.
    Returns:
      A list of transformed directives.
    """
    errors = []

    sans_entries = []
    for entry in entries:
        if (isinstance(entry, data.Transaction) and
            any(posting.flag == FLAG_SANSCOST
                for posting in entry.postings)):

            entry, error = fold_commissions_in_cost(entry)
            if error is not None:
                errors.append(error)
        sans_entries.append(entry)

    return sans_entries, errors


def fold_commissions_in_cost(entry):
    """Fold the commissions in a single position cost leg.

    Args:
      entry: A Transaction entry.
    Returns:
      A modified directive and an error (or None), in most cases.
    """
    # FIXME: TODO - see test.
    return entry, None
