#!/usr/bin/env python3
"""
Download helper for local voice models (MMS TTS / Piper).
"""

from __future__ import annotations

import argparse
import os
import pathlib
import urllib.request


def _download(url: str, out_path: pathlib.Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    print(f"Downloading {url} -> {out_path}")
    with urllib.request.urlopen(url, timeout=60) as r:
        data = r.read()
    with open(out_path, "wb") as f:
        f.write(data)


def _download_mms(model_id: str) -> None:
    try:
        from transformers import pipeline
    except ImportError as exc:
        raise SystemExit("transformers is required to download MMS models.") from exc

    print(f"Downloading MMS model: {model_id}")
    pipeline("text-to-speech", model=model_id, device=-1)
    print("Done. Model cached in the local HF cache.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Download local voice models.")
    parser.add_argument("--mms", action="store_true", help="Download MMS TTS model")
    parser.add_argument("--mms-model-id", default="facebook/mms-tts-kss", help="MMS model id")
    parser.add_argument("--piper-model-url", help="Piper .onnx model URL")
    parser.add_argument("--piper-config-url", help="Piper .json config URL")
    parser.add_argument("--output-dir", default="models/piper", help="Output dir for Piper files")

    args = parser.parse_args()

    if args.mms:
        _download_mms(args.mms_model_id)

    output_dir = pathlib.Path(args.output_dir)
    if args.piper_model_url:
        filename = os.path.basename(args.piper_model_url)
        _download(args.piper_model_url, output_dir / filename)

    if args.piper_config_url:
        filename = os.path.basename(args.piper_config_url)
        _download(args.piper_config_url, output_dir / filename)

    if not args.mms and not args.piper_model_url and not args.piper_config_url:
        print("No download options provided. Use --mms or --piper-*-url.")


if __name__ == "__main__":
    main()
