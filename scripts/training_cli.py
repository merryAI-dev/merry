#!/usr/bin/env python3
"""
Training data collection CLI.

Manage fine-tuning dataset collection and export.
"""

import argparse
import json
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from shared.storage_backend import get_default_storage
from shared.training_logger import get_training_stats


def cmd_stats(args):
    """Show training data collection statistics."""
    if args.task_type:
        stats = get_training_stats(args.task_type)
        print(f"\nTask: {args.task_type}")
        print(f"  Samples: {stats.get('sample_count', 0):,}")
        print(f"  Files: {stats.get('file_count', 0)}")
        print(f"  Size: {stats.get('total_size_mb', 0):.2f} MB")
        if stats.get("date_range"):
            print(f"  Date range: {stats['date_range']['start']} ~ {stats['date_range']['end']}")
    else:
        stats = get_training_stats()
        print(f"\nTraining Data Collection Status")
        print(f"  Enabled: {stats.get('training_enabled')}")
        print(f"  Total tasks: {stats.get('total_tasks', 0)}")
        print()

        for task_name, task_stats in stats.get("tasks", {}).items():
            print(f"  {task_name}:")
            print(f"    Samples: {task_stats.get('sample_count', 0):,}")
            print(f"    Files: {task_stats.get('file_count', 0)}")
            print(f"    Size: {task_stats.get('total_size_mb', 0):.2f} MB")
            if task_stats.get("date_range"):
                dr = task_stats["date_range"]
                print(f"    Date range: {dr['start']} ~ {dr['end']}")


def cmd_list(args):
    """List training samples."""
    storage = get_default_storage()
    samples = storage.list_samples(args.task_type, start_date=None, end_date=None)

    print(f"\nTraining samples for {args.task_type}:")
    for path in samples:
        print(f"  {path}")

    print(f"\nTotal: {len(samples)} files")


def cmd_export(args):
    """Export training data to a single JSONL file."""
    storage = get_default_storage()
    samples = storage.list_samples(args.task_type, start_date=None, end_date=None)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    total_samples = 0
    with open(output_path, "w", encoding="utf-8") as out_f:
        for sample_file in samples:
            try:
                data = storage.read_sample(sample_file)
                for sample in data.get("samples", []):
                    out_f.write(json.dumps(sample, ensure_ascii=False) + "\n")
                    total_samples += 1
            except Exception as e:
                print(f"Error reading {sample_file}: {e}", file=sys.stderr)

    print(f"\nExported {total_samples:,} samples to {output_path}")
    print(f"Size: {output_path.stat().st_size / (1024*1024):.2f} MB")


def cmd_validate(args):
    """Validate training data for PII."""
    from shared.pii_scrubber import validate_no_pii

    storage = get_default_storage()
    samples = storage.list_samples(args.task_type, start_date=None, end_date=None)

    total_samples = 0
    total_warnings = 0

    for sample_file in samples:
        try:
            data = storage.read_sample(sample_file)
            for sample in data.get("samples", []):
                total_samples += 1
                warnings = validate_no_pii(sample)
                if warnings:
                    total_warnings += len(warnings)
                    if args.verbose:
                        print(f"\n{sample_file} (sample {total_samples}):")
                        for warning in warnings:
                            print(f"  - {warning}")
        except Exception as e:
            print(f"Error validating {sample_file}: {e}", file=sys.stderr)

    print(f"\nValidation Summary:")
    print(f"  Total samples: {total_samples:,}")
    print(f"  PII warnings: {total_warnings}")
    if total_warnings == 0:
        print("  ✓ No PII detected")
    else:
        print(f"  ⚠ {total_warnings} potential PII issues found")
        print("  Run with --verbose to see details")


def main():
    parser = argparse.ArgumentParser(description="Training data collection CLI")
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Stats command
    stats_parser = subparsers.add_parser("stats", help="Show collection statistics")
    stats_parser.add_argument("--task-type", help="Filter by task type")

    # List command
    list_parser = subparsers.add_parser("list", help="List training samples")
    list_parser.add_argument("task_type", help="Task type to list")

    # Export command
    export_parser = subparsers.add_parser("export", help="Export to single JSONL")
    export_parser.add_argument("task_type", help="Task type to export")
    export_parser.add_argument("output", help="Output JSONL path")

    # Validate command
    validate_parser = subparsers.add_parser("validate", help="Validate for PII")
    validate_parser.add_argument("task_type", help="Task type to validate")
    validate_parser.add_argument("--verbose", action="store_true", help="Show details")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == "stats":
        cmd_stats(args)
    elif args.command == "list":
        cmd_list(args)
    elif args.command == "export":
        cmd_export(args)
    elif args.command == "validate":
        cmd_validate(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
