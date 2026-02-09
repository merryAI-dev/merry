"""
Synthetic data generator for Korean number parsing.

Generates 2000+ training examples for Korean number normalization.
Useful for fine-tuning models on Korean financial text.
"""

import json
import random
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

try:
    from .logging_config import get_logger
    logger = get_logger("synthetic_korean_numbers")
except ImportError:
    # Direct execution
    import logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("synthetic_korean_numbers")

# Korean number units and their values
UNITS = {
    "조": 1_000_000_000_000,      # trillion
    "억": 100_000_000,            # hundred million
    "천만": 10_000_000,           # ten million
    "백만": 1_000_000,            # million
    "만": 10_000,                 # ten thousand
    "천": 1_000,                  # thousand
    "백": 100,                    # hundred
    "십": 10,                     # ten
}


def generate_korean_number(
    min_value: int = 1,
    max_value: int = 10_000_000_000_000,
    units_count: int = None,
) -> Tuple[str, int]:
    """Generate a random Korean number string and its numeric value.

    Args:
        min_value: Minimum value
        max_value: Maximum value
        units_count: Number of units to use (if None, random)

    Returns:
        (korean_text, numeric_value) tuple
    """
    value = random.randint(min_value, max_value)
    korean = format_korean_number(value, units_count)
    return korean, value


def format_korean_number(value: int, max_units: int = None) -> str:
    """Format a numeric value as Korean text.

    Args:
        value: Numeric value
        max_units: Maximum number of units to use (for variation)

    Returns:
        Korean number string
    """
    if value == 0:
        return "0"

    parts = []
    remaining = value

    # Process from largest to smallest unit
    for unit_name, unit_value in UNITS.items():
        if remaining >= unit_value:
            count = remaining // unit_value
            remaining = remaining % unit_value

            # Add coefficient (skip 1 for some units in Korean)
            if count > 1 or unit_name in ("조", "억", "만"):
                parts.append(f"{count}{unit_name}")
            else:
                parts.append(unit_name)

            if max_units and len(parts) >= max_units:
                break

    # Add remaining as digits if any
    if remaining > 0 and not parts:
        parts.append(str(remaining))

    return "".join(parts)


def generate_variations(base_value: int) -> List[Tuple[str, int]]:
    """Generate variations of a number with different formats.

    Args:
        base_value: Base numeric value

    Returns:
        List of (korean_text, numeric_value) tuples
    """
    variations = []

    # Standard format
    variations.append((format_korean_number(base_value), base_value))

    # With "원" suffix
    korean = format_korean_number(base_value)
    variations.append((f"{korean}원", base_value))

    # With spaces
    korean_parts = []
    for i, char in enumerate(korean):
        korean_parts.append(char)
        # Add space after units
        if char in "조억만천백십" and i < len(korean) - 1:
            korean_parts.append(" ")
    variations.append(("".join(korean_parts), base_value))

    return variations


def generate_dataset(
    sample_count: int = 2000,
    output_path: Path = None,
) -> List[Dict[str, any]]:
    """Generate synthetic Korean number dataset.

    Args:
        sample_count: Number of samples to generate
        output_path: Optional path to save JSONL

    Returns:
        List of training samples
    """
    samples = []

    # Value ranges for different categories
    ranges = [
        (1, 999, 200),                          # Small (백 이하)
        (1_000, 9_999, 200),                    # 천 단위
        (10_000, 999_999, 200),                 # 만 단위
        (1_000_000, 99_999_999, 300),           # 백만~천만 단위
        (100_000_000, 9_999_999_999, 400),      # 억 단위
        (10_000_000_000, 999_999_999_999, 300), # 백억~천억 단위
        (1_000_000_000_000, 99_999_999_999_999, 200), # 조 단위
    ]

    # Add common financial values
    common_values = [
        50_000_000,      # 5천만
        100_000_000,     # 1억
        300_000_000,     # 3억
        500_000_000,     # 5억
        1_000_000_000,   # 10억
        3_000_000_000,   # 30억
        5_000_000_000,   # 50억
        10_000_000_000,  # 100억
        50_000_000_000,  # 500억
        100_000_000_000, # 1000억
        1_000_000_000_000, # 1조
    ]

    for min_val, max_val, count in ranges:
        for _ in range(count):
            if random.random() < 0.1 and common_values:
                # 10% chance: use common value
                value = random.choice(common_values)
                korean = format_korean_number(value)
            else:
                # Generate random value in range
                value = random.randint(min_val, max_val)
                korean = format_korean_number(value)

            # Add variations
            for korean_var, value_var in generate_variations(value):
                sample = {
                    "input": korean_var,
                    "output": value_var,
                    "task": "korean_number_parsing",
                }
                samples.append(sample)

                if len(samples) >= sample_count:
                    break

            if len(samples) >= sample_count:
                break

        if len(samples) >= sample_count:
            break

    # Shuffle
    random.shuffle(samples)
    samples = samples[:sample_count]

    # Add metadata
    for i, sample in enumerate(samples):
        sample["id"] = f"korean_num_{i:05d}"
        sample["generated_at"] = datetime.now().isoformat()

    # Save if path provided
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            for sample in samples:
                f.write(json.dumps(sample, ensure_ascii=False) + "\n")
        logger.info(f"Saved {len(samples)} synthetic samples to {output_path}")

    return samples


def generate_edge_cases() -> List[Dict[str, any]]:
    """Generate edge cases for Korean number parsing.

    Returns:
        List of edge case samples
    """
    edge_cases = [
        # Zero
        ("0", 0),
        ("0원", 0),
        # Single units
        ("1", 1),
        ("10", 10),
        ("100", 100),
        ("백", 100),
        ("천", 1_000),
        ("만", 10_000),
        ("십만", 100_000),
        ("백만", 1_000_000),
        ("천만", 10_000_000),
        ("억", 100_000_000),
        ("십억", 1_000_000_000),
        ("백억", 10_000_000_000),
        ("천억", 100_000_000_000),
        ("조", 1_000_000_000_000),
        # Compound (critical test cases)
        ("5억2천만", 520_000_000),
        ("1조3천억", 1_300_000_000_000),
        ("32억4500만", 3_245_000_000),
        ("3천억", 300_000_000_000),
        ("5천만", 50_000_000),
        ("2천500", 2_500),
        # With 원
        ("5억2천만원", 520_000_000),
        ("3천억원", 300_000_000_000),
        # With spaces
        ("5억 2천만", 520_000_000),
        ("1조 3천억", 1_300_000_000_000),
        # Large numbers
        ("99조9999억9999만9999", 99_999_999_999_999),
        ("10조", 10_000_000_000_000),
        ("50조", 50_000_000_000_000),
    ]

    samples = []
    for i, (korean, value) in enumerate(edge_cases):
        samples.append({
            "id": f"edge_case_{i:03d}",
            "input": korean,
            "output": value,
            "task": "korean_number_parsing",
            "category": "edge_case",
            "generated_at": datetime.now().isoformat(),
        })

    return samples


# CLI interface
if __name__ == "__main__":
    import sys

    # Generate main dataset
    output_dir = Path(__file__).parent.parent / "data" / "training" / "synthetic"
    output_dir.mkdir(parents=True, exist_ok=True)

    print("Generating synthetic Korean number dataset...")
    samples = generate_dataset(
        sample_count=2000,
        output_path=output_dir / "korean_numbers.jsonl",
    )
    print(f"✓ Generated {len(samples)} samples")

    # Generate edge cases
    print("\nGenerating edge cases...")
    edge_cases = generate_edge_cases()
    edge_path = output_dir / "korean_numbers_edge_cases.jsonl"
    with open(edge_path, "w", encoding="utf-8") as f:
        for sample in edge_cases:
            f.write(json.dumps(sample, ensure_ascii=False) + "\n")
    print(f"✓ Generated {len(edge_cases)} edge cases")

    print(f"\nDataset saved to: {output_dir}")
    print(f"  - korean_numbers.jsonl: {len(samples)} samples")
    print(f"  - korean_numbers_edge_cases.jsonl: {len(edge_cases)} edge cases")

    # Show sample
    print("\nSample data:")
    for sample in samples[:5]:
        print(f"  {sample['input']} → {sample['output']:,}")
