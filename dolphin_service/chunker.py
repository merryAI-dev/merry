"""
Smart chunking for PDF processing.

Splits pages into chunks based on base64 size and page limits.
Uses greedy packing algorithm to maximize chunk utilization.
"""

import logging
from typing import List, Tuple

from .strategy import ProcessingStrategy

logger = logging.getLogger(__name__)


def estimate_base64_size_mb(images_base64: List[str]) -> float:
    """Estimate total base64 size in MB.

    Args:
        images_base64: List of base64 encoded images

    Returns:
        Estimated size in MB
    """
    if not images_base64:
        return 0.0

    # Calculate total bytes
    total_bytes = sum(len(img) for img in images_base64)
    return total_bytes / (1024 * 1024)


def create_chunks(
    images_base64: List[str],
    strategy: ProcessingStrategy,
) -> List[List[str]]:
    """Split images into chunks based on strategy limits.

    Uses greedy packing to maximize chunk utilization while respecting:
    - max_chunk_mb: Maximum MB per chunk (base64)
    - chunk_pages: Maximum pages per chunk

    Args:
        images_base64: List of base64 encoded page images
        strategy: Processing strategy with limits

    Returns:
        List of chunks, where each chunk is a list of base64 images
    """
    if not images_base64:
        return []

    # If no Vision API, return all pages in one chunk
    if not strategy.use_vision:
        return [images_base64]

    # Greedy packing algorithm
    chunks = []
    current_chunk = []
    current_size_mb = 0.0

    for idx, img_base64 in enumerate(images_base64):
        img_size_mb = len(img_base64) / (1024 * 1024)

        # Check if adding this image would exceed limits
        would_exceed_size = (current_size_mb + img_size_mb) > strategy.max_chunk_mb
        would_exceed_pages = len(current_chunk) >= strategy.chunk_pages

        if current_chunk and (would_exceed_size or would_exceed_pages):
            # Finalize current chunk and start new one
            chunks.append(current_chunk)
            logger.debug(
                f"Chunk {len(chunks)}: {len(current_chunk)} pages, {current_size_mb:.2f} MB"
            )
            current_chunk = []
            current_size_mb = 0.0

        # Add image to current chunk
        current_chunk.append(img_base64)
        current_size_mb += img_size_mb

    # Add final chunk if non-empty
    if current_chunk:
        chunks.append(current_chunk)
        logger.debug(
            f"Chunk {len(chunks)}: {len(current_chunk)} pages, {current_size_mb:.2f} MB"
        )

    logger.info(
        f"Created {len(chunks)} chunks from {len(images_base64)} pages "
        f"(max {strategy.chunk_pages}p or {strategy.max_chunk_mb}MB per chunk)"
    )

    return chunks


def compute_page_offsets(chunks: List[List[str]]) -> List[int]:
    """Compute page number offsets for each chunk.

    Args:
        chunks: List of chunks (each chunk is a list of images)

    Returns:
        List of starting page numbers for each chunk (0-indexed)
    """
    offsets = []
    current_offset = 0
    for chunk in chunks:
        offsets.append(current_offset)
        current_offset += len(chunk)
    return offsets


def merge_chunk_results(chunk_results: List[dict], page_offsets: List[int]) -> dict:
    """Merge results from multiple chunks into single result.

    Args:
        chunk_results: List of results from each chunk
        page_offsets: Starting page numbers for each chunk

    Returns:
        Merged result dictionary
    """
    if not chunk_results:
        return {"success": False, "error": "No chunk results"}

    if len(chunk_results) == 1:
        return chunk_results[0]  # No merging needed

    # Merge logic
    merged = {
        "success": True,
        "content": "",
        "structured_content": {"pages": []},
        "financial_tables": {},
        "processing_method": chunk_results[0].get("processing_method", "unknown"),
        "chunk_count": len(chunk_results),
    }

    # Merge pages (ordered by page number)
    all_pages = []
    for result in chunk_results:
        if "structured_content" in result and "pages" in result["structured_content"]:
            all_pages.extend(result["structured_content"]["pages"])

    # Sort by page number
    all_pages.sort(key=lambda p: p.get("page_num", 0))
    merged["structured_content"]["pages"] = all_pages

    # Merge content (concatenate)
    merged["content"] = "\n\n".join(
        r.get("content", "") for r in chunk_results if r.get("content")
    )

    # Merge financial tables (priority: first found)
    for table_type in ["income_statement", "balance_sheet", "cash_flow", "cap_table"]:
        for result in chunk_results:
            if table_type in result.get("financial_tables", {}):
                table = result["financial_tables"][table_type]
                if table.get("found"):
                    merged.setdefault("financial_tables", {})[table_type] = table
                    break

    # Merge company_info (combine non-null fields)
    merged_company_info = {}
    for result in chunk_results:
        if "structured_content" in result and "company_info" in result["structured_content"]:
            company_info = result["structured_content"]["company_info"]
            for key, value in company_info.items():
                if value and not merged_company_info.get(key):
                    merged_company_info[key] = value

    if merged_company_info:
        merged["structured_content"]["company_info"] = merged_company_info

    logger.info(
        f"Merged {len(chunk_results)} chunks into single result "
        f"({len(all_pages)} pages, {len(merged['content'])} chars)"
    )

    return merged


# Example usage
if __name__ == "__main__":
    import sys
    from .strategy import ProcessingStrategy, DocType, get_strategy

    logging.basicConfig(level=logging.INFO)

    # Test with dummy data
    print("Testing chunker with dummy base64 images...")

    # Create dummy images (1MB each)
    dummy_images = ["x" * (1024 * 1024) for _ in range(50)]  # 50 pages, 50MB total

    # Test with IMAGE_HEAVY strategy (5p or 40MB per chunk)
    strategy = get_strategy(DocType.IMAGE_HEAVY)
    chunks = create_chunks(dummy_images, strategy)

    print(f"\nChunking Result:")
    print(f"  Total pages: {len(dummy_images)}")
    print(f"  Total size: {len(dummy_images)} MB")
    print(f"  Chunks created: {len(chunks)}")
    for i, chunk in enumerate(chunks):
        chunk_size = sum(len(img) for img in chunk) / (1024 * 1024)
        print(f"    Chunk {i+1}: {len(chunk)} pages, {chunk_size:.2f} MB")
