#!/usr/bin/env python3
"""Figure out rounding precision for prices and rewrite the input file for cleanup.
"""

from decimal import Decimal
import argparse
import collections
import logging
import pprint
import re

from beancount import loader
from beancount.core import data
from beancount.core import number


def price_reformat(line: str) -> str:
    match = re.match(r"(;?\d{4}-\d{2}-\d{2}\s+price\s+[A-Z0-9_-]+)\s+([\d.]+)\s+([A-Z0-9_-]+)",
                     line)
    if not match:
        return line
    dirprefix, number, currency = match.groups()
    index = number.find('.')
    if index == -1: index = len(number)
    padding = ' ' * (10 - (len(number) - index))
    return "{:32} {:>17} {}\n".format(dirprefix, str(number) + padding, currency)


def main():
    parser = argparse.ArgumentParser(description=__doc__.strip())
    parser.add_argument('filename', help='Filenames')
    args = parser.parse_args()

    entries, errors, options_map = loader.load_file(args.filename)

    # Gather all the price directives.
    prices_map = collections.defaultdict(list)
    for entry in entries:
        if not isinstance(entry, data.Price):
            continue
        # Ignore automatically calculated prices.
        if '__implicit_prices__' in entry.meta:
            continue
        base_quote = (entry.currency, entry.amount.currency)
        prices_map[base_quote].append((entry.meta, entry.amount.number))

    # Read all the input file contents.
    filenames = {meta["filename"]
                 for base_quote, meta_number_list in prices_map.items()
                 for meta, _ in meta_number_list}
    filemap = {filename: open(filename).readlines()
               for filename in sorted(filenames)}

    # Infer the right quantization and quantize the price numbers.
    ten = Decimal("10")
    max_digits = 5
    for base_quote, meta_number_list in prices_map.items():
        prices_list = [price for _, price in  meta_number_list]
        exponent = number.infer_quantum_from_list(prices_list)
        exponent = max(exponent, -max_digits)
        qua = ten ** exponent
        for meta, price in meta_number_list:
            filename = meta["filename"]
            lineno = meta["lineno"]-1
            qprice = price.quantize(qua)
            qtuple = qprice.as_tuple()
            if (qtuple.exponent < price.as_tuple().exponent or
                -qtuple.exponent == 0):
                continue
            newline = re.sub(str(price), str(qprice), filemap[filename][lineno])
            filemap[filename][lineno] = newline

    # Reformat price lines.
    for filename, lines in filemap.items():
        lines[:] = [price_reformat(line) for line in lines]

    # Write out modified files.
    for filename, lines in filemap.items():
        with open(filename + ".fixed", "w") as outfile:
            for line in lines:
                outfile.write(line)


if __name__ == '__main__':
    main()
