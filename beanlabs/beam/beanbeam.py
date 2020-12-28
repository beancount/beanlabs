#!/usr/bin/env python3.8
"""Beancount utilities for Apache Beam.
"""

from typing import Iterable, Iterator

from beancount.core.data import Posting
from beancount.core import data
from beancount.core.inventory import Inventory


def GetPostings(entry: data.Directive) -> Iterator[Posting]:
    """Extract postings from a Beancount directive."""
    if isinstance(entry, data.Transaction):
        for posting in entry.postings:
            yield posting


def SumPostings(postings: Iterable[Posting]) -> Inventory:
    """Aggregate all the positions for the given postings."""
    acc = Inventory()
    for elem in postings:
        # Note: 'elem' can be a Posting or an Inventory (the intermediate result
        # from a subcombiner).
        if isinstance(elem, Inventory):
            acc.add_inventory(elem)
        else:
            assert isinstance(elem, Posting)
            acc.add_position(elem)
    return acc
