#!/usr/bin/env python3
"""
Phase 2: Background Sound Detection

Detect background noise in each track using energy analysis.
Identifies segments where a speaker's track contains primarily background/ambient sound
(i.e., when that speaker is not actively speaking but the track still has sound from others).

Algorithm:
1. Calculate RMS energy for each track over a sliding window (100ms)
2. Compute energy statistics (median, std dev)
3. Set adaptive threshold: median + factor*std or below threshold = background
4. Identify continuous segments of low energy
5. Merge nearby segments and filter out very short ones
"""

from typing import Dict, List
import numpy as np
import librosa


def calculate_energy_time_series(
    audio: np.ndarray,
    sr: int,
    window_ms: int = 100,
) -> tuple:
    """
    Calculate RMS energy over time.

    Args:
        audio: Audio signal
        sr: Sample rate
        window_ms: Window size in milliseconds

    Returns:
        Tuple of (energy_values, frame_times, hop_length)
    """
    hop_length = int(window_ms / 1000 * sr)

    # Calculate RMS energy
    rms = librosa.feature.rms(y=audio, hop_length=hop_length)[0]

    # Get frame times
    times = librosa.frames_to_time(np.arange(len(rms)), sr=sr, hop_length=hop_length)

    return rms, times, hop_length


def detect_background_in_track(
    audio: np.ndarray,
    sr: int,
    energy_window_ms: int = 100,
    silence_threshold_factor: float = 0.5,
    min_silence_duration_ms: int = 100,
    merge_gap_ms: int = 200,
) -> List[Dict]:
    """
    Detect background noise segments in a single track.

    Args:
        audio: Audio signal
        sr: Sample rate
        energy_window_ms: Window size for energy calculation
        silence_threshold_factor: Threshold factor (< factor * median = background)
        min_silence_duration_ms: Minimum segment duration to keep
        merge_gap_ms: Gap between segments to merge

    Returns:
        List of background segments: [{"start": float, "end": float, "energy_ratio": float}, ...]
    """
    # Calculate energy
    rms, times, hop_length = calculate_energy_time_series(audio, sr, energy_window_ms)

    # Handle edge cases
    if len(rms) == 0:
        return []

    # Convert to dB for better threshold calculation
    rms_db = librosa.power_to_db(rms + 1e-9, ref=np.max(rms))

    # Calculate statistics
    median_db = np.median(rms_db)
    std_db = np.std(rms_db)

    # Adaptive threshold: below median - factor*std = background
    threshold_db = median_db - abs(std_db)

    # Find frames below threshold (background)
    background_mask = rms_db < threshold_db

    # Convert mask to segments
    transitions = np.diff(background_mask.astype(int))
    starts = np.where(transitions == 1)[0] + 1  # Frame index where background starts
    ends = np.where(transitions == -1)[0] + 1    # Frame index where background ends

    # Handle edge cases
    if background_mask[0]:
        starts = np.concatenate([[0], starts])
    if background_mask[-1]:
        ends = np.concatenate([ends, [len(background_mask)]])

    segments = []

    for start_idx, end_idx in zip(starts, ends):
        start_time = times[min(start_idx, len(times) - 1)]
        end_time = times[min(end_idx - 1, len(times) - 1)]

        duration = end_time - start_time

        # Filter by minimum duration
        if duration * 1000 < min_silence_duration_ms:
            continue

        segments.append({
            "start": float(start_time),
            "end": float(end_time),
            "duration": float(duration),
            "energy_ratio": float(np.mean(rms[start_idx:end_idx])),
        })

    # Merge nearby segments
    if not segments:
        return []

    # Sort by start time
    segments.sort(key=lambda x: x["start"])

    merge_gap_samples = merge_gap_ms / 1000.0

    merged = [segments[0]]
    for seg in segments[1:]:
        if seg["start"] - merged[-1]["end"] < merge_gap_samples:
            # Merge segments
            merged[-1]["end"] = seg["end"]
            merged[-1]["duration"] = merged[-1]["end"] - merged[-1]["start"]
        else:
            merged.append(seg)

    return merged


def detect_background_segments(
    tracks: np.ndarray,
    sr: int,
    energy_window_ms: int = 100,
    silence_threshold_factor: float = 0.5,
    min_silence_duration_ms: int = 100,
    merge_gap_ms: int = 200,
) -> Dict[int, List[Dict]]:
    """
    Detect background noise segments for all tracks.

    Args:
        tracks: Multi-track audio array (num_tracks, num_samples)
        sr: Sample rate
        energy_window_ms: Window size for energy calculation
        silence_threshold_factor: Threshold factor
        min_silence_duration_ms: Minimum segment duration
        merge_gap_ms: Gap to merge segments

    Returns:
        Dictionary mapping track_id to list of background segments
    """
    results = {}

    for track_id, audio in enumerate(tracks):
        segments = detect_background_in_track(
            audio,
            sr,
            energy_window_ms=energy_window_ms,
            silence_threshold_factor=silence_threshold_factor,
            min_silence_duration_ms=min_silence_duration_ms,
            merge_gap_ms=merge_gap_ms,
        )
        results[track_id] = segments

    return results


if __name__ == "__main__":
    # Demo usage
    import soundfile as sf
    from pathlib import Path

    # Load a test audio file
    test_file = Path("test_audio.wav")
    if test_file.exists():
        audio, sr = librosa.load(test_file, sr=16000, mono=True)
        tracks = np.array([audio])  # Single track for demo

        results = detect_background_segments(
            tracks,
            sr,
            energy_window_ms=100,
            silence_threshold_factor=0.5,
            min_silence_duration_ms=100,
            merge_gap_ms=200,
        )

        print("Background detection results:")
        for track_id, segments in results.items():
            print(f"Track {track_id}: {len(segments)} segments")
            for seg in segments:
                print(f"  {seg['start']:.2f}s - {seg['end']:.2f}s "
                      f"({seg['duration']:.2f}s)")
