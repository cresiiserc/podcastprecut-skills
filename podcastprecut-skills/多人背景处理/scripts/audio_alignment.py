#!/usr/bin/env python3
"""
Phase 0: Audio Alignment Preprocessing

Load multiple audio files, detect silence segments, unify sample rate to 16kHz,
and align all tracks to start at the same point. Pad shorter audio with zeros
to match the longest track length.

Usage:
    python3 audio_alignment.py --input audio1.wav audio2.wav audio3.wav audio4.wav --output aligned/
"""

import argparse
import json
from pathlib import Path
from typing import List, Tuple

import librosa
import numpy as np
import soundfile as sf


def detect_silence_start(y: np.ndarray, sr: int, top_db: float = 40, duration_ms: float = 500) -> float:
    """
    Detect the start of actual audio content by finding where silence ends.

    Args:
        y: Audio signal
        sr: Sample rate
        top_db: Threshold in dB below reference
        duration_ms: Minimum duration of silence to consider as silence

    Returns:
        Time in seconds where actual audio starts
    """
    intervals = librosa.effects.split(y, top_db=top_db)
    if len(intervals) == 0:
        return 0.0

    # First interval is the first sound segment
    first_sound_start = intervals[0][0]
    silence_start_time = first_sound_start / sr

    return silence_start_time


def load_and_align_audio(
    audio_paths: List[str],
    target_sr: int = 16000
) -> Tuple[List[np.ndarray], int, dict]:
    """
    Load multiple audio files and align them.

    Args:
        audio_paths: List of paths to audio files
        target_sr: Target sample rate (default 16kHz)

    Returns:
        Tuple of:
        - List of aligned audio arrays (same length)
        - Sample rate (unified)
        - Metadata dict with alignment info
    """
    audio_data = []
    silence_starts = []
    original_durations = []

    # Load all audio files
    for path in audio_paths:
        print(f"Loading: {path}")
        y, sr = librosa.load(path, sr=target_sr, mono=True)
        audio_data.append(y)

        # Detect silence start for alignment
        silence_start = detect_silence_start(y, target_sr)
        silence_starts.append(silence_start)
        original_durations.append(librosa.get_duration(y=y, sr=sr))

        print(f"  Duration: {librosa.get_duration(y=y, sr=sr):.2f}s, "
              f"Audio starts at: {silence_start:.3f}s")

    # Find the minimum silence start point (earliest actual audio)
    min_silence_start = min(silence_starts)

    # Align all audio to start at the same point
    aligned_audio = []
    align_info = []

    for i, (audio, silence_start) in enumerate(zip(audio_data, silence_starts)):
        # Calculate samples to skip
        skip_samples = int((silence_start - min_silence_start) * target_sr)

        if skip_samples > 0:
            # Prepend silence (zeros) to match the earliest starting audio
            aligned = np.concatenate([np.zeros(skip_samples), audio])
        elif skip_samples < 0:
            # Trim leading silence
            aligned = audio[-skip_samples:]
        else:
            aligned = audio

        aligned_audio.append(aligned)
        align_info.append({
            "file": str(Path(audio_paths[i]).name),
            "original_duration": original_durations[i],
            "silence_start_original": silence_start,
            "alignment_offset_samples": skip_samples,
            "alignment_offset_seconds": skip_samples / target_sr,
        })

    # Pad all audio to the same length (length of the longest after alignment)
    max_length = max(len(audio) for audio in aligned_audio)
    padded_audio = []

    for audio in aligned_audio:
        if len(audio) < max_length:
            padded = np.concatenate([audio, np.zeros(max_length - len(audio))])
        else:
            padded = audio
        padded_audio.append(padded)

    # Create metadata
    metadata = {
        "target_sample_rate": target_sr,
        "num_tracks": len(audio_paths),
        "alignment_reference": f"earliest_audio_start at {min_silence_start:.3f}s",
        "total_length_samples": max_length,
        "total_length_seconds": max_length / target_sr,
        "tracks": align_info,
    }

    return padded_audio, target_sr, metadata


def save_aligned_audio(
    aligned_audio: List[np.ndarray],
    sr: int,
    output_dir: str,
    metadata: dict
) -> None:
    """
    Save aligned audio files and metadata.

    Args:
        aligned_audio: List of aligned audio arrays
        sr: Sample rate
        output_dir: Output directory
        metadata: Metadata dictionary
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Save each track separately
    for i, audio in enumerate(aligned_audio):
        track_path = output_path / f"track_{i:02d}_aligned.wav"
        sf.write(track_path, audio, sr)
        print(f"Saved: {track_path}")

    # Save metadata
    metadata_path = output_path / "alignment_metadata.json"
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)
    print(f"Saved metadata: {metadata_path}")

    # Save mixed audio (sum of all tracks)
    mixed = np.sum(aligned_audio, axis=0) / len(aligned_audio)
    mixed_path = output_path / "mixed_aligned.wav"
    sf.write(mixed_path, mixed, sr)
    print(f"Saved mixed audio: {mixed_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Audio alignment preprocessing for multi-track podcast"
    )
    parser.add_argument(
        "--input", "-i",
        nargs="+",
        required=True,
        help="Input audio file paths (at least 2)"
    )
    parser.add_argument(
        "--output", "-o",
        default="./aligned_audio",
        help="Output directory for aligned audio files"
    )
    parser.add_argument(
        "--sample-rate", "-sr",
        type=int,
        default=16000,
        help="Target sample rate in Hz (default: 16000)"
    )

    args = parser.parse_args()

    if len(args.input) < 2:
        parser.error("At least 2 input audio files are required")

    # Check all files exist
    for path in args.input:
        if not Path(path).exists():
            parser.error(f"File not found: {path}")

    # Load and align
    print(f"Loading and aligning {len(args.input)} audio files...")
    aligned_audio, sr, metadata = load_and_align_audio(args.input, args.sample_rate)

    # Save results
    save_aligned_audio(aligned_audio, sr, args.output, metadata)

    print(f"\nAlignment complete!")
    print(f"Total length: {metadata['total_length_seconds']:.2f} seconds")
    print(f"Sample rate: {sr} Hz")
    print(f"Tracks: {metadata['num_tracks']}")


if __name__ == "__main__":
    main()
