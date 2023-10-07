#!/usr/bin/env python3
"""Extract and convert tagged transactions from a Google Spreadsheet.

This script reads a Beancount file, extracts all transactions with a tag, and
rewrites them to convert its inflows to a single account.
"""

# TODO(blais): Turn the ability to read or write a spreadsheet to/from a petl dataframe into a library from this code.

from decimal import Decimal
from os import path
from typing import Dict, List, Tuple, Generator, Optional, Any
import argparse
import collections
import contextlib
import datetime
import enum
import logging
import os
import pprint
import re
import sys
import typing

import petl
from apiclient import discovery
import gapis  # See http://github.com/blais/gapis
import dateutil.parser

from beancount import loader
from beancount.core.number import D
from beancount.core.number import ZERO
from beancount.core import data
from beancount.core import amount
from beancount.core import account
from beancount.core import flags
from beancount.parser import printer

from beanlabs.google import sheets_upload


petl.config.look_style = "minimal"
petl.config.failonerror = True


@contextlib.contextmanager
def tag(tagname: Optional[str]):
    if tagname:
        print("pushtag #{}".format(tagname))
        print()
    try:
        yield
    finally:
        if tagname:
            print()
            print("poptag #{}".format(tagname))


Sheet = typing.NamedTuple("Sheet", [("docid", str), ("id", int), ("name", str)])


def get_sheets(service: discovery.Resource, docid: str) -> List[Sheet]:
    "Get the sheet titles and ids of the given spreadsheet."
    resp = service.spreadsheets().get(spreadsheetId=docid).execute()
    return [
        Sheet(docid, sheet["properties"]["sheetId"], sheet["properties"]["title"])
        for sheet in resp["sheets"]
    ]


def select_sheet(service: discovery.Resource, docid: str, sheet_re: str) -> Sheet:
    "Select a particular sheet from a list."
    sheets = get_sheets(service, docid)
    if len(sheets) > 1 and sheet_re:
        regexp = ".*{}.*".format(re.escape(sheet_re))
        sheets = [
            sheet
            for sheet in sheets
            if (
                re.match(regexp, sheet.name, re.I)
                or re.match(regexp, str(sheet.id), re.I)
            )
        ]
    if len(sheets) != 1:
        raise SystemExit(
            "Could not match a single unambiguous sheet: {}".format(sheets)
        )
    return sheets[0]


def get_sheet_size(service: discovery.Resource, sheet: Sheet):
    "Get the size of a spreadsheet."
    resp = (
        service.spreadsheets()
        .get(spreadsheetId=sheet.docid, ranges=sheet.name)
        .execute()
    )
    grid_props = resp["sheets"][0]["properties"]["gridProperties"]
    return (grid_props["rowCount"], grid_props["columnCount"])


def iter_sheet(
    service: discovery.Resource, sheet: Sheet
) -> Generator[List[str], None, None]:
    "Iterate over the contents of a particular sheet."
    size = get_sheet_size(service, sheet)
    resp = (
        service.spreadsheets()
        .values()
        .batchGet(
            spreadsheetId=sheet.docid,
            ranges=sheets_upload.sheet_range(size[0], size[1], sheet.name),
        )
        .execute()
    )
    for row in resp["valueRanges"][0]["values"]:
        yield row


def find_unique_column(table: petl.Table, simple_name: str) -> str:
    """Find the column for a date."""
    fieldnames = table.fieldnames()
    matching = [
        field for field in fieldnames if re.search(rf"\b{simple_name}\b", field, re.I)
    ]
    if len(matching) != 1:
        raise ValueError(f"Could not find unique field for {simple_name}.")
    return matching[0]


def parse_number(string: str) -> Decimal:
    return Decimal(string.replace("$", "").replace(",", ""))


def create_entry(
    row: petl.Record,
    inflows_account: str,
    currency: str,
    docid: str,
    index: int,
    default_account: str = "Expenses:Uncategorized",
):
    "Create a new entry based on the row contents and inferred types."
    date = row["date"]
    number = row["amount"]
    units = amount.Amount(number, "USD")
    account = row.get("account", default_account)
    payee = row.get("payee", None)
    narration = row.get("narration", None)
    pflag = flags.FLAG_WARNING if account == default_account else None
    txn = data.Transaction(
        data.new_metadata(docid, index),
        date,
        flags.FLAG_OKAY,
        payee,
        narration,
        data.EMPTY_SET,
        data.EMPTY_SET,
        [
            data.Posting(account, units, None, None, pflag, None),
            data.Posting(inflows_account, -units, None, None, None, None),
        ],
    )
    return txn


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)-8s: %(message)s")
    parser = argparse.ArgumentParser(description=__doc__.strip())

    parser.add_argument("docid", action="store", help="Google Sheets document id")

    parser.add_argument(
        "inflows_account",
        action="store",
        help="Inflows account to use for the rewritten transactions",
    )

    parser.add_argument(
        "--sheet",
        dest="sheet_re",
        action="store",
        help="Google Sheets sheets name regexp",
    )

    parser.add_argument(
        "--uncategorized_account",
        action="store",
        default="Expenses:Uncategorized",
        help="Name of uncategorized account if missing",
    )

    parser.add_argument(
        "--program-key",
        default="personal-accounting",
        action="store",
        help="Program key for Google API key",
    )

    parser.add_argument(
        "-t", "--tag", action="store", help="Tag all entries with the given tag string"
    )

    parser.add_argument(
        "--scope",
        action="store",
        help="Filter by Scope column value",
    )

    args = parser.parse_args()

    scope = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = gapis.get_credentials(scope, args.program_key)
    service = discovery.build("sheets", "v4", credentials=creds)

    # Select the sheet.
    sheet = select_sheet(service, args.docid, args.sheet_re)
    logging.info("Selected sheet: {.name}".format(sheet))

    # Read contents and categorize them.
    rows = list(iter_sheet(service, sheet))
    # coltypes = infer_columns(rows)
    table = petl.wrap(list(iter_sheet(service, sheet)))

    # Map field names.
    colmap = {
        "date": find_unique_column(table, "(date)"),
        "account": find_unique_column(table, "(category|account)"),
        "payee": find_unique_column(table, "(payee|provider)"),
        "narration": find_unique_column(table, "(narration|description)"),
        "amount": find_unique_column(table, "(amount)"),
    }
    if args.scope:
        colmap.update({"scope": find_unique_column(table, "(scope)")})

    # Select and rename fields, convert types.
    table = (
        table.cut(list(colmap.values()))
        .rename({value: key for (key, value) in colmap.items()})
        .convert("date", lambda v: dateutil.parser.parse(v).date())
        .convert("amount", parse_number)
    )

    if args.scope:
        index = [name.lower() for name in table.fieldnames()].index("scope")
        if index == -1:
            raise ValueError("Scope field not found in sheet.")
        field = table.fieldnames()[index]
        table = table.selecteq(field, args.scope)

    entries = []
    for index, row in enumerate(table.records()):
        entry = create_entry(
            row,
            args.inflows_account,
            "USD",
            args.docid,
            index,
            args.uncategorized_account,
        )
        if entry is not None:
            entries.append(entry)

    entries = data.sorted(entries)
    with tag(args.tag):
        printer.print_entries(entries, file=sys.stdout)


if __name__ == "__main__":
    main()
