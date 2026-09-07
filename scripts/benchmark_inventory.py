#!/usr/bin/env python3
"""Offline body-fetch workload model; not a tracker latency benchmark."""
import argparse
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.ai_first.inventory import refresh_inventory


def benchmark(size=10000, writes=10):
    if size < 1 or writes < 1:
        raise ValueError('Positive inventory size and write count required')
    listing = [dict(id=f'ado:fixture/project/{i}', revision=1) for i in range(size)]
    fetched = [dict(**entry, item=dict(id=entry['id'], body='fixture body')) for entry in listing]
    started = time.perf_counter()
    result = refresh_inventory(listing, fetched, inventory_complete=True, strong_revisions=True)
    downloads = size
    for i in range(writes):
        entry = listing[i % size]
        entry['revision'] += 1
        pending = refresh_inventory(listing, [], result['cache'], inventory_complete=True, strong_revisions=True)
        assert pending['fetch_ids'] == [entry['id']]
        fetched = [dict(**entry, item=dict(id=entry['id'], body=f'changed {i}'))]
        result = refresh_inventory(listing, fetched, pending['cache'], inventory_complete=True, strong_revisions=True)
        assert result['complete']
        downloads += 1
    return dict(mode='synthetic-strong-revision-workload', items=size, writes=writes,
                naive_body_fetches=size * (writes + 1), cached_body_fetches=downloads,
                authoritative_listing_records=size * (writes + 1),
                elapsed_seconds=round(time.perf_counter() - started, 4),
                limitation='Listings remain O(N) per write; no network or live server latency measured.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--items', type=int, default=10000)
    parser.add_argument('--writes', type=int, default=10)
    args = parser.parse_args()
    print(json.dumps(benchmark(args.items, args.writes), indent=2))
