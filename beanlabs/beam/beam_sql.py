#!/usr/bin/env python3.8
"""Prototype processing Beancount entries using Beam w/ ZetaSQL.

Beancount's postings are provided as rows.
We'll try to define a custom aggregator, if at all possible.
"""

# THIS WOULD BE GREAT. The next thing would be to insert custom aggregators.
# Unfortunately, this doesn't appear to work today with Python/ZetaSQL, it requires Java.

import argparse
import re
import json
import logging
import time
from typing import Iterable, Iterator, List, Tuple

import apache_beam as beam
from apache_beam.transforms.sql import SqlTransform

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


def CreatePipeline(pipeline_args):
    poptions = pipeline_options.PipelineOptions(
        pipeline_args,
        runner="directrunner",
        direct_running_mode="multi_threading")
    # (options.viewas(BeamSqlPipelineOptions)
    #  .setPlannerName("org.apache.beam.sdk.extensions.sql.zetasql.ZetaSQLQueryPlanner"))
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
    postings = (posting
                for entry in data.filter_txns(entries)
                for posting in entry.postings)
    price_map = prices.build_price_map(entries)
    t2 = time.time()
    logging.info("Read ledger in %.1fsecs.", t2-t1)

    with CreatePipeline(pipeline_args) as pipeline:
        _ = (pipeline
             | beam.Create(postings)
             | SqlTransform("""
                 SELECT account FROM PCOLLECTION
             """, "zetasql")
             | beam.Map(print))


if __name__ == '__main__':
    main()
