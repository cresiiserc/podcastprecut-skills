#!/usr/bin/env python3
"""
Multi-Person Podcast Background Audio Processing - Main Entry Point

Complete pipeline for processing multi-person podcast recordings:
1. Align audio tracks from multiple speakers
2. Detect and suppress background noise
3. Detect laugh segments
4. Apply dynamic compression to multi-person laughs

Usage:
    # Step 1: Align audio
    python3 main.py align \
        --input speaker1.wav speaker2.wav speaker3.wav speaker4.wav \
        --output aligned_audio/

    # Step 2: Process aligned audio (background + laughs)
    python3 main.py process \
        --input aligned_audio/ \
        --output processed_podcast.wav \
        --report report.json

    # Or use the combined workflow
    python3 main.py full \
        --input speaker1.wav speaker2.wav speaker3.wav speaker4.wav \
        --output processed_podcast.wav \
        --report report.json
"""

import argparse
import json
import sys
from pathlib import Path

import numpy as np

# Import processing modules
from audio_alignment import load_and_align_audio, save_aligned_audio
from podcast_background_cleanup import MultiTrackAudioProcessor


def cmd_align(args):
    """Handle audio alignment subcommand."""
    print("=" * 60)
    print("STEP 1: Audio Alignment & Preprocessing")
    print("=" * 60)

    # Load and align
    print(f"\nLoading and aligning {len(args.input)} audio files...")
    aligned_audio, sr, metadata = load_and_align_audio(args.input, args.sample_rate)

    # Save results
    save_aligned_audio(aligned_audio, sr, args.output, metadata)

    print("\n" + "=" * 60)
    print("Alignment Complete!")
    print("=" * 60)
    print(f"Total duration: {metadata['total_length_seconds']:.2f} seconds")
    print(f"Sample rate: {sr} Hz")
    print(f"Tracks: {metadata['num_tracks']}")


def cmd_process(args):
    """Handle background/laugh processing subcommand."""
    print("=" * 60)
    print("STEP 2: Background Suppression & Laugh Compression")
    print("=" * 60)

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: Input directory not found: {args.input}", file=sys.stderr)
        sys.exit(1)

    metadata_file = input_path / "alignment_metadata.json"
    if not metadata_file.exists():
        print(f"Error: Metadata file not found: {metadata_file}", file=sys.stderr)
        print("Make sure to run 'align' step first.", file=sys.stderr)
        sys.exit(1)

    # Initialize processor
    print("\nInitializing processor...")
    processor = MultiTrackAudioProcessor(str(metadata_file))

    # Load and process
    processor.load_tracks(args.input)
    processor.create_mixed_audio()

    if not args.skip_background:
        processor.detect_background_noise()
        processor.suppress_background_noise()

    if not args.skip_laugh:
        # Recreate mixed audio after background suppression
        processor.create_mixed_audio()
        processor.detect_laugh_sounds()
        processor.apply_laugh_dynamic_compression()

    # Create final output
    processor.create_final_mixed_audio()
    processor.save_output(args.output, args.report)

    print("\n" + "=" * 60)
    print("Processing Complete!")
    print("=" * 60)


def cmd_full(args):
    """Handle full pipeline subcommand."""
    print("=" * 60)
    print("FULL PIPELINE: Alignment + Processing")
    print("=" * 60)

    # Step 1: Alignment
    align_args = argparse.Namespace(
        input=args.input,
        output=args.temp_dir,
        sample_rate=args.sample_rate,
    )
    cmd_align(align_args)

    # Step 2: Processing
    process_args = argparse.Namespace(
        input=args.temp_dir,
        output=args.output,
        report=args.report,
        skip_background=args.skip_background,
        skip_laugh=args.skip_laugh,
    )
    cmd_process(process_args)

    print("\n" + "=" * 60)
    print("FULL PIPELINE Complete!")
    print("=" * 60)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Multi-person podcast background audio processing",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Align audio from 4 speakers
  python3 main.py align -i s1.wav s2.wav s3.wav s4.wav -o aligned/

  # Process aligned audio
  python3 main.py process -i aligned/ -o output.wav -r report.json

  # Full pipeline in one command
  python3 main.py full -i s1.wav s2.wav s3.wav s4.wav -o output.wav
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Align subcommand
    align_parser = subparsers.add_parser("align", help="Align audio tracks from multiple speakers")
    align_parser.add_argument(
        "-i", "--input",
        nargs="+",
        required=True,
        help="Input audio file paths (at least 2)"
    )
    align_parser.add_argument(
        "-o", "--output",
        default="./aligned_audio",
        help="Output directory for aligned audio"
    )
    align_parser.add_argument(
        "-sr", "--sample-rate",
        type=int,
        default=16000,
        help="Target sample rate in Hz (default: 16000)"
    )
    align_parser.set_defaults(func=cmd_align)

    # Process subcommand
    process_parser = subparsers.add_parser("process", help="Process aligned audio (background + laughs)")
    process_parser.add_argument(
        "-i", "--input",
        required=True,
        help="Input directory with aligned audio (from align step)"
    )
    process_parser.add_argument(
        "-o", "--output",
        required=True,
        help="Output audio file path (WAV)"
    )
    process_parser.add_argument(
        "-r", "--report",
        help="Output JSON report path"
    )
    process_parser.add_argument(
        "--skip-background",
        action="store_true",
        help="Skip background noise detection and suppression"
    )
    process_parser.add_argument(
        "--skip-laugh",
        action="store_true",
        help="Skip laugh detection and compression"
    )
    process_parser.set_defaults(func=cmd_process)

    # Full pipeline subcommand
    full_parser = subparsers.add_parser("full", help="Full pipeline: align + process in one command")
    full_parser.add_argument(
        "-i", "--input",
        nargs="+",
        required=True,
        help="Input audio file paths (at least 2)"
    )
    full_parser.add_argument(
        "-o", "--output",
        required=True,
        help="Output audio file path (WAV)"
    )
    full_parser.add_argument(
        "-r", "--report",
        help="Output JSON report path"
    )
    full_parser.add_argument(
        "-sr", "--sample-rate",
        type=int,
        default=16000,
        help="Target sample rate in Hz (default: 16000)"
    )
    full_parser.add_argument(
        "--temp-dir",
        default="./.temp_aligned",
        help="Temporary directory for aligned audio (will be cleaned up)"
    )
    full_parser.add_argument(
        "--skip-background",
        action="store_true",
        help="Skip background noise suppression"
    )
    full_parser.add_argument(
        "--skip-laugh",
        action="store_true",
        help="Skip laugh compression"
    )
    full_parser.set_defaults(func=cmd_full)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    try:
        args.func(args)
    except Exception as e:
        print(f"\nError: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
