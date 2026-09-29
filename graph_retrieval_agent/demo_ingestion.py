from __future__ import annotations

import argparse
from pathlib import Path

from .ingestion_agent import ingestion_agent


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Preview or ingest semi-structured Harness context."
    )
    parser.add_argument(
        "--source",
        default=None,
        help="Optional source markdown/text file. Defaults to the bundled Customer Onboarding sample.",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="After extraction/validation, upsert the normalized graph into Neo4j.",
    )
    args = parser.parse_args()

    source_path = (
        Path(args.source)
        if args.source
        else Path(__file__).parent / "data" / "customer_onboarding_source.md"
    )

    preview = ingestion_agent.preview_file(source_path)
    print(preview.model_dump_json(indent=2))

    if preview.validation_warnings:
        raise SystemExit(
            "Ingestion stopped because validation warnings are present. "
            "Review the preview before writing to Neo4j."
        )

    if args.write:
        print("\nWriting validated graph to Neo4j...")
        result = ingestion_agent.ingest_file(source_path)
        # Avoid printing the complete normalized graph a second time.
        result.pop("normalized_graph", None)
        print(result)
    else:
        print("\nPreview only. No Neo4j changes were made.")
        print("Run again with --write when the preview is correct.")


if __name__ == "__main__":
    main()
