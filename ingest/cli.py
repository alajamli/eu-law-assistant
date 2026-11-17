"""Ingestion CLI.

    python -m ingest.cli download            # fetch + cache the 6 EUR-Lex pages
    python -m ingest.cli parse               # HTML -> units (JSONL, inspectable)
    python -m ingest.cli index --embedding-backend hashing
    python -m ingest.cli all

`parse` writes an inspectable JSONL per document on purpose: the Week 1 failure
mode is a parser that silently drops articles, and you only see it by reading the
output.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from ingest import chunk as chunker
from ingest import fetch as fetcher
from ingest import parse as parser
from ingest import sources as registry
from ingest import store
from ingest.embed import get_embedder
from ingest.models import Source

PROCESSED_DIR = Path("data/processed")


def _selected(slugs: list[str] | None) -> list[Source]:
    if not slugs:
        return registry.sources()
    out: list[Source] = []
    for slug in slugs:
        out.extend(registry.by_slug(slug))
    return out


def cmd_download(args: argparse.Namespace) -> int:
    for source in _selected(args.slug):
        path, checksum = fetcher.fetch(source, force=args.force)
        print(
            f"[download] {source.slug:9s} {source.lang} {path}  "
            f"sha256={checksum[:12]}  {path.stat().st_size:,} B"
        )
    return 0


def cmd_parse(args: argparse.Namespace) -> int:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    for source in _selected(args.slug):
        path = fetcher.target_path(source)
        if not path.exists():
            print(f"[parse] missing {path} — run `download` first", file=sys.stderr)
            return 1
        units = parser.parse_html(path.read_text(encoding="utf-8"), source.title)
        out = PROCESSED_DIR / f"{source.slug}_{source.lang.lower()}.units.jsonl"
        with out.open("w", encoding="utf-8") as fh:
            for unit in units:
                fh.write(json.dumps(unit.__dict__, ensure_ascii=False) + "\n")
        print(
            f"[parse] {source.slug:9s} {source.lang} units={len(units):4d} "
            f"articles={parser.count_articles(units):3d} -> {out}"
        )
    return 0


def cmd_index(args: argparse.Namespace) -> int:
    embedder = get_embedder(args.embedding_backend)
    print(f"[index] embedder={embedder.name} dim={embedder.dim}")
    conn = store.connect(args.database_url)
    try:
        for source in _selected(args.slug):
            path = fetcher.target_path(source)
            if not path.exists():
                print(f"[index] missing {path} — run `download` first", file=sys.stderr)
                return 1
            units = parser.parse_html(path.read_text(encoding="utf-8"), source.title)
            chunks = chunker.units_to_chunks(units, source.slug, source.title, source.lang.lower())
            doc_id = store.upsert_document(conn, source, fetcher.sha256_of(path))
            inserted = store.upsert_chunks(conn, doc_id, chunks, embedder)
            print(f"[index] {source.slug:9s} {source.lang} doc_id={doc_id} chunks={inserted}")
        print(json.dumps(store.stats(conn), indent=2, default=str))
    finally:
        conn.close()
    return 0


def cmd_stats(args: argparse.Namespace) -> int:
    conn = store.connect(args.database_url)
    try:
        print(json.dumps(store.stats(conn), indent=2, default=str))
    finally:
        conn.close()
    return 0


def cmd_schema(args: argparse.Namespace) -> int:
    conn = store.connect(args.database_url)
    try:
        store.apply_schema(conn)
        print("[schema] applied")
    finally:
        conn.close()
    return 0


def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--slug", action="append", help="ai-act | gdpr | data-act (repeatable)")
    common.add_argument("--database-url", default=None)

    ap = argparse.ArgumentParser(prog="ingest", description=__doc__)
    sub = ap.add_subparsers(dest="command", required=True)

    p = sub.add_parser("download", parents=[common], help="fetch and cache raw EUR-Lex HTML")
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=cmd_download)

    p = sub.add_parser("parse", parents=[common], help="HTML -> structured units (JSONL)")
    p.set_defaults(func=cmd_parse)

    p = sub.add_parser("index", parents=[common], help="chunk + embed + upsert into pgvector")
    p.add_argument(
        "--embedding-backend",
        default="local",
        choices=["local", "hashing"],
        help="'hashing' is a dev stand-in with no model download",
    )
    p.set_defaults(func=cmd_index)

    p = sub.add_parser("stats", parents=[common], help="row counts per document")
    p.set_defaults(func=cmd_stats)

    p = sub.add_parser("schema", parents=[common], help="apply db/init/01_schema.sql")
    p.set_defaults(func=cmd_schema)
    return ap


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
