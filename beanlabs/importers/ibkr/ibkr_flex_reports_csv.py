"""Extractor for Interactive Brokers Activity Report in CSV format.

  Login > Reports > Flex Report > (period) > Run

You need to select "Statement of Funds" to produce everything as a single table,
and enable all the columns, and it has to be done from a Flex query. This is the
way to do this properly; in fact, the only way I've found.

"Custom reports" from the first page are joint reports (includes many tables in
a single CSV file with a prefix column), they have an option to output the
statement of funds table, but it doesn't contain the stock detail. You want a
"Flex report", which has joins between the tables, e.g., the statement of funds
and the trades table.

Note that during the weekends you may not be able to download up to the day's
date (an error about the report/statement not being ready to download will be
shown). Simply select a Custom Date Range, and select the last valid market open
date / business date in order to produce a valid report.
"""

import collections
import csv
import datetime
import re
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

import dateutil.parser

from beancount.core.number import D
from beancount.core.amount import Amount
from beancount.core import data
from beancount.core import flags
from beancount.core import position
from beancount.core import account as accountlib

from beangulp import testing
from beangulp.importers.mixins import filing
from beangulp.importers.mixins import identifier
from beangulp.importers.mixins import config as configlib


Rows = List[List[str]]


class Importer(identifier.IdentifyMixin, filing.FilingMixin, configlib.ConfigMixin):
    """Importer for IBKR Flex Reports (Statement of Funds table)."""

    REQUIRED_CONFIG = {
        'root'               : 'Root of account',
        'asset_cash'         : 'Cash sub-account',
        'interest'           : 'Interest income',
        'fees'               : 'Expense fees account',
        'commissions'         : 'Expense commissions account',
        'transfer'           : 'Other account for inter-bank transfers',
    }

    # Note: Sometimes the filename downloads as the name of the flex query, it's
    # inconsistent, so you can't use the filename.
    #           ('filename', r'/U[\d_]{6,}.*\.txt$'),
    matchers = [('mime', 'text/plain|text/csv'),
                ('content', r'.*\bClientAccountID\b')]

    def extract(self, file, existing_entries=None):
        rows = iter(csv.reader(open(file.name)))
        header = next(rows)

        new_entries = []
        for rowlist in rows:
            row = create_row(header, rowlist)
            description = row["ActivityDescription"]
            for hndlr in HANDLERS:
                if re.match(hndlr.regex, description):
                    entry = hndlr(row, self.config)
                    if entry:
                        new_entries.append(entry)
                    break
            else:
                raise TypeError("Unknown transaction: {}".format(description))
        return new_entries


# This is useful for the other joint reports.
#
#  subsheets = split_by_column(list(csv.reader(open(file.name))))
#  header, body = split_header_and_data(subsheets['Statement of Funds'])
#
def split_by_column(rows: Rows, column_index: int = 0) -> Dict[str, Rows]:
    """Split a list or CSV rows by some column value."""
    outmap = collections.defaultdict(list)
    for row in rows:
        key = row.pop(column_index)
        outmap[key].append(row)
    return outmap


# This is useful for the other joint reports.
def split_header_and_data(rows: Rows) -> Tuple[List[str], Rows]:
    """Take off the first column, splitting out the header and data rows."""
    header = None
    body = []
    for row in rows:
        coltype = row.pop(0)
        if coltype == "Header":
            if not header:
                header = row
        elif coltype == "Data":
            body.append(row)
    return header, body


def parse_number(string) -> Optional[Decimal]:
    """Parse a number to decimal."""
    return D(string.strip()) if string.strip() else None


def parse_date(string) -> Optional[datetime.date]:
    """Parse a date."""
    return dateutil.parser.parse(string.strip()).date() if string.strip() else None


def create_row(header, rowlist) -> Dict[str, Any]:
    """Create a single row dict container with the types converted."""
    row = dict(zip(header, rowlist))
    for col in ["Balance", "Credit", "Debit", "Amount",
                "TradeQuantity", "TradePrice", "TradeGross", "TradeCommission"]:
        row[col] = parse_number(row[col])
    for col in "Date", "ReportDate":
        row[col] = parse_date(row[col])
    return row


HANDLERS = []
def handler(regex):
    """Register a transaction row handler."""
    def deco(func):
        func.regex = regex
        HANDLERS.append(func)
        return func
    return deco


def create_meta():
    """Create metadata for all of that's produced here."""
    return dict(filename="<ibkr>", lineno=0)


def create_transaction(row):
    """Create a transaction object."""
    return data.Transaction(
        create_meta(), row["Date"], flags.FLAG_OKAY,
        None, row["ActivityDescription"],
        {row["ActivityCode"]}, {row["TransactionID"]}, [])


@handler("(Opening|Closing|Starting|Ending) Balance")
def create_balance(row, config) -> data.Balance:
    """Create an opening or closing balance entry."""
    return data.Balance(create_meta(),
                        row["ReportDate"], config["asset_cash"],
                        Amount(row["Balance"], row["CurrencyPrimary"]), None, None)

@handler("Balance of Monthly Minimum Fee")
def create_fee_expense(row, config) -> data.Balance:
    """Create a fee expense transaction."""
    assert row["Credit"] is None
    txn = create_transaction(row)
    txn.postings.extend([
        data.Posting(config["asset_cash"], Amount(row["Debit"], row["CurrencyPrimary"]),
                     None, None, None, None),
        data.Posting(config["fees"], Amount(-row["Debit"], row["CurrencyPrimary"]),
                     None, None, None, None),
    ])
    return txn


@handler("USD Credit Interest")
def create_interest_income(row, config) -> data.Balance:
    """Create an interest income transaction."""
    assert row["Debit"] is None
    txn = create_transaction(row)
    txn.postings.extend([
        data.Posting(config["asset_cash"], Amount(row["Credit"], row["CurrencyPrimary"]),
                     None, None, None, None),
        data.Posting(config["interest"], Amount(-row["Credit"], row["CurrencyPrimary"]),
                     None, None, None, None),
    ])
    return txn


@handler(r"(Buy|Sell) (-?[0-9,\.]+) .*")
def create_trade(row, config) -> data.Balance:
    """Create proper trading transactions."""
    txn = create_transaction(row)
    account = accountlib.join(config["root"], row["Symbol"])
    currency = row["CurrencyPrimary"]
    txn.postings.extend([
        data.Posting(account,
                     Amount(row["TradeQuantity"], row["Symbol"]),
                     position.Cost(row["TradePrice"], currency, None, None),
                     None, None, None),
        data.Posting(config["asset_cash"],
                     Amount(row["TradeGross"] + row["TradeCommission"],
                            currency),
                     None, None, None, None),
        data.Posting(config["commissions"],
                     Amount(-row["TradeCommission"], currency),
                     None, None, None, None),
    ])
    return txn


@handler(".*:US CONSOLIDATED SNAPSHOT")
def create_snapshot_misc(row, config) -> data.Balance:
    """Handle the misc snapshot entries."""
    assert bool(row["Debit"]) != bool(row["Credit"])
    amount = row["Debit"] or row["Credit"]
    txn = create_transaction(row)
    txn.postings.extend([
        data.Posting(config["asset_cash"], Amount(amount, row["CurrencyPrimary"]),
                     None, None, None, None),
        data.Posting(config["interest"], Amount(-amount, row["CurrencyPrimary"]),
                     None, None, None, None),
    ])
    return txn


@handler("Electronic Fund Transfer")
def create_funds_transfer(row, config) -> data.Balance:
    """Handle transfers to/from other accounts."""
    assert bool(row["Debit"]) != bool(row["Credit"])
    amount = row["Debit"] or row["Credit"]
    txn = create_transaction(row)
    txn.postings.extend([
        data.Posting(config["transfer"],
                     Amount(-amount, row["CurrencyPrimary"]),
                     None, None, None, None),
        data.Posting(config["asset_cash"],
                     Amount(amount, row["CurrencyPrimary"]),
                     None, None, None, None),
    ])
    return txn


if __name__ == '__main__':
    importer = Importer(filing="Assets:US:IBKR:Main", config={
        'root'        : "Assets:US:IBKR:Main",
        'asset_cash'  : "Assets:US:IBKR:Main:Cash",
        'fees'        : "Expenses:Financial:Fees",
        'commissions' : "Expenses:Financial:Commissions",
        'transfer'    : "Assets:US:TD:Checking",
        'interest'    : 'Income:US:IBKR:Interest',
    })
    testing.main(importer)
