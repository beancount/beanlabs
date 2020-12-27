#!/usr/bin/env python3
"""Sort transactions read from stdin, output to stdout.
"""
__copyright__ = "Copyright (C) 2018  Martin Blais"
__license__ = "GNU GPLv2"

import sys
import argparse

from beancount import loader
from beancount.parser import printer
from beancount.core import data


def main():
    argparser = argparse.ArgumentParser(description=__doc__)
    argparser.add_argument('infile', type=argparse.FileType('r'),
                           help='Filename or "-" for stdin')
    args = argparser.parse_args()

    # Read input from stdin or a given filename.
    entries, errors, options = loader.load_string(args.infile.read())

    # Print out sorted entries.
    for entry in data.sorted(entries):
        printer.print_entry(entry)


if __name__ == '__main__':
    main()
