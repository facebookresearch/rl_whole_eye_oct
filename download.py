#!/usr/bin/env python3
# Copyright (c) Meta Platforms, Inc. and affiliates.
# This source code is licensed under the CC-BY-NC 4.0 license found in the
# LICENSE file in the root directory of this source tree.

"""
Download script for the Whole-Eye OCT Dataset.

Usage:
    python download.py --url-file urls.txt --output-dir ./data

The URL file should contain one CDN URL per line, obtained from:
https://www.meta.com/emerging-tech/eye-tracking/

The URL list contains data chunks named:
  rloct_<category>_<YYYYMMDD>_batch_<NNN>.zip

Categories: raw_data, annotations.
Use --filter to select a category, e.g. --filter rloct_raw_data.
"""

import argparse
import hashlib
import os
import sys
from concurrent.futures import as_completed, ThreadPoolExecutor
from pathlib import Path
from typing import List, Optional
from urllib.parse import unquote, urlparse

try:
    import requests
    from tqdm import tqdm
except ImportError:
    print("Error: Required packages not installed.")
    print("Please run: pip install requests tqdm")
    sys.exit(1)


def parse_filename_from_url(url: str) -> str:
    """Extract filename from CDN URL."""
    parsed = urlparse(url)
    # Try to get filename from path
    path = unquote(parsed.path)
    filename = os.path.basename(path)

    # If filename is empty or generic, try query params
    if not filename or filename in ["download", "file"]:
        # Try Content-Disposition style filename in query
        query = parsed.query
        if "filename=" in query:
            for param in query.split("&"):
                if param.startswith("filename="):
                    filename = unquote(param.split("=", 1)[1])
                    break

    return filename if filename else "unknown_file"


def download_file(
    url: str,
    output_dir: Path,
    chunk_size: int = 8192,
    timeout: int = 30,
    retries: int = 3,
) -> tuple[str, bool, str]:
    """
    Download a single file from URL.

    Returns:
        Tuple of (filename, success, message)
    """
    filename = parse_filename_from_url(url)
    output_path = output_dir / filename

    # Skip if already downloaded AND size matches the server's Content-Length.
    # If the local file exists but is smaller (e.g. interrupted earlier run),
    # fall through and re-download from scratch.
    if output_path.exists():
        local_size = output_path.stat().st_size
        try:
            head = requests.head(url, allow_redirects=True, timeout=timeout)
            head.raise_for_status()
            cl = head.headers.get("Content-Length")
            expected_size = int(cl) if cl is not None else None
        except (requests.exceptions.RequestException, ValueError):
            expected_size = None

        if expected_size is None:
            # Server didn't tell us the size; trust the existing file.
            return (
                filename,
                True,
                f"Already exists ({local_size / 1e6:.1f} MB); "
                "size check skipped (server returned no Content-Length)",
            )
        if local_size == expected_size:
            return (
                filename,
                True,
                f"Already exists ({local_size / 1e6:.1f} MB), size matches; skipped",
            )
        # Size mismatch → likely a partial download; remove and re-fetch.
        output_path.unlink()
        # fall through to download below

    for attempt in range(retries):
        try:
            response = requests.get(url, stream=True, timeout=timeout)
            response.raise_for_status()

            # Get file size if available
            total_size = int(response.headers.get("content-length", 0))

            # Create parent directories if needed
            output_path.parent.mkdir(parents=True, exist_ok=True)

            # Download with progress
            with open(output_path, "wb") as f:
                if total_size > 0:
                    with tqdm(
                        total=total_size,
                        unit="B",
                        unit_scale=True,
                        desc=filename[:40],
                        leave=False,
                    ) as pbar:
                        for chunk in response.iter_content(chunk_size=chunk_size):
                            if chunk:
                                f.write(chunk)
                                pbar.update(len(chunk))
                else:
                    for chunk in response.iter_content(chunk_size=chunk_size):
                        if chunk:
                            f.write(chunk)

            return filename, True, f"Downloaded ({total_size / 1e6:.1f} MB)"

        except requests.exceptions.RequestException as e:
            if attempt < retries - 1:
                continue
            # Clean up partial download
            if output_path.exists():
                output_path.unlink()
            return filename, False, f"Failed: {str(e)}"

    return filename, False, "Failed: Max retries exceeded"


def download_parallel(
    urls: List[str],
    output_dir: Path,
    num_workers: int = 4,
) -> tuple[int, int]:
    """
    Download multiple files in parallel.

    Returns:
        Tuple of (success_count, failure_count)
    """
    success_count = 0
    failure_count = 0

    with ThreadPoolExecutor(max_workers=num_workers) as executor:
        futures = {
            executor.submit(download_file, url.strip(), output_dir): url
            for url in urls
            if url.strip()
        }

        with tqdm(total=len(futures), desc="Total progress") as pbar:
            for future in as_completed(futures):
                filename, success, message = future.result()
                if success:
                    success_count += 1
                    tqdm.write(f"[OK] {filename}: {message}")
                else:
                    failure_count += 1
                    tqdm.write(f"[FAIL] {filename}: {message}")
                pbar.update(1)

    return success_count, failure_count


def main():
    parser = argparse.ArgumentParser(
        description="Download the Whole-Eye OCT Dataset",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Download all files from URL list
    python download.py --url-file urls.txt --output-dir ./data

    # Download with more parallel workers
    python download.py --url-file urls.txt --output-dir ./data --workers 8

    # Download only the raw_data category (TIF + waveform CSVs)
    python download.py --url-file urls.txt --output-dir ./data --filter rloct_raw_data

    # Download only the annotations category (bundled .npy)
    python download.py --url-file urls.txt --output-dir ./data --filter rloct_annotations

Notes:
    - Get your URL list from https://www.meta.com/emerging-tech/eye-tracking/
    - Existing files are automatically skipped
    - Failed downloads can be retried by running the script again
        """,
    )

    parser.add_argument(
        "--url-file",
        type=Path,
        help="Path to file containing URLs (one per line). If not provided, reads from stdin.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("./data"),
        help="Output directory for downloaded files (default: ./data)",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=4,
        help="Number of parallel download workers (default: 4)",
    )
    parser.add_argument(
        "--filter",
        type=str,
        help=(
            "Only download URLs containing this substring. "
            "Examples: 'rloct_raw_data' for the raw_data category, "
            "'rloct_annotations' for the annotations category."
        ),
    )

    args = parser.parse_args()

    # Read URLs
    if args.url_file:
        if not args.url_file.exists():
            print(f"Error: URL file not found: {args.url_file}")
            sys.exit(1)
        with open(args.url_file) as f:
            urls = f.readlines()
    else:
        # Read from stdin
        if sys.stdin.isatty():
            print("Reading URLs from stdin (paste URLs, then Ctrl+D to finish):")
        urls = sys.stdin.readlines()

    # Filter URLs if requested
    if args.filter:
        urls = [u for u in urls if args.filter in u]

    urls = [u.strip() for u in urls if u.strip() and not u.strip().startswith("#")]

    if not urls:
        print("No URLs to download.")
        sys.exit(0)

    print(f"Found {len(urls)} files to download")
    print(f"Output directory: {args.output_dir}")
    print(f"Workers: {args.workers}")
    print()

    # Create output directory
    args.output_dir.mkdir(parents=True, exist_ok=True)

    # Download
    success, failed = download_parallel(urls, args.output_dir, args.workers)

    print()
    print(f"Download complete: {success} succeeded, {failed} failed")

    if failed > 0:
        print("Run the script again to retry failed downloads.")
        sys.exit(1)


if __name__ == "__main__":
    main()
