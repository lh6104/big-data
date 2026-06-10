"""Run local news-event and traffic Gold builders in one process.

This is the Docker entrypoint equivalent of `make gold`.
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

import pandas as pd

from build_local_gold_dataset import DEFAULT_PRIMARY_CITY, MIN_TRAIN_ROWS, build as build_gold
from build_local_gold_dataset import normalize_city
from build_news_bronze import build as build_news_bronze
from build_news_event_features import build as build_news_events


def main() -> None:
    parser = argparse.ArgumentParser(description="Build normalized news events and enriched local Gold datasets.")
    parser.add_argument("--raw-dir", default="raw", type=Path)
    parser.add_argument("--output-dir", default="data", type=Path)
    parser.add_argument("--bucket-minutes", default=5, type=int)
    parser.add_argument("--primary-city", default=DEFAULT_PRIMARY_CITY)
    parser.add_argument("--min-train-rows", default=MIN_TRAIN_ROWS, type=int)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    build_news_bronze(args.raw_dir, args.output_dir)
    build_news_events(args.raw_dir, args.output_dir, args.bucket_minutes)
    primary_city = normalize_city(pd.Series([args.primary_city])).iloc[0]
    build_gold(args.raw_dir, args.output_dir, args.bucket_minutes, primary_city, args.min_train_rows)


if __name__ == "__main__":
    main()
