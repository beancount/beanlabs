#!/usr/bin/env python3.8
"""Simple prototype of processing Beancount entries using Beam.
"""

import argparse
import re
import json
import logging
import time
from typing import Iterable, Iterator, List, Tuple

import apache_beam as beam

from apache_beam.options import pipeline_options
from apache_beam.portability import python_urns
from apache_beam.portability.api import beam_runner_api_pb2
from apache_beam.runners.portability import fn_api_runner

from beancount.core.data import Posting
from beancount import loader
from beancount.core import data
from beancount.core import convert
from beancount.core import prices
from beancount.core.inventory import Inventory
from beancount.core.position import Position

from beanlabs.beam import beanbeam


def FinalRow(item: Tuple[str, Inventory],
             price_map: prices.PriceMap) -> Tuple[Position, Position]:
    account, inv = item
    conv = lambda i: i.reduce(convert.convert_position,
                              "USD", price_map).get_only_position()
    cost = inv.reduce(convert.get_cost)
    value = inv.reduce(convert.get_value, price_map)
    return account, conv(cost), conv(value)


def CreatePipeline(pipeline_args):
    poptions = pipeline_options.PipelineOptions(
        pipeline_args,
        runner="directrunner",
        direct_running_mode="multi_threading")
    return beam.Pipeline(options=poptions)


def main():
    logging.basicConfig(level=logging.INFO, format='%(levelname)-8s: %(message)s')
    parser = argparse.ArgumentParser(description=__doc__.strip())
    parser.add_argument('filename', help='Beancount ledger filename')
    args, pipeline_args = parser.parse_known_args()

    # Read the ledger.
    logging.info("Reading ledger.")
    t1 = time.time()
    entries, errors, options_map = loader.load_file(args.filename)
    price_map = prices.build_price_map(entries)
    t2 = time.time()
    logging.info("Read ledger in %.1fsecs.", t2-t1)

    with CreatePipeline(pipeline_args) as pipeline:
        _ = (pipeline
             | beam.Create(entries)
             | beam.FlatMap(beanbeam.GetPostings)
             | beam.Filter(lambda p: re.match(r"Assets:", p.account))
             | beam.Map(lambda p: (p.account, p))
             | beam.CombinePerKey(beanbeam.SumPostings)
             | beam.Map(FinalRow, price_map)
             | beam.Map(print))


if __name__ == '__main__':
    main()
