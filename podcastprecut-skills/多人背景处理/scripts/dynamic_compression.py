#!/usr/bin/env python3
"""
Phase 4: Laugh Sound Dynamic Compression

Apply dynamic gain compression based on the number of simultaneous speakers laughing.

Strategy:
- Single speaker laugh: Keep original volume (natural)
- 2 speakers laughing simultaneously: -3dB (reduce by ~50%)
- 3 speakers laughing simultaneously: -6dB (reduce by ~75%)
- 4 speakers laughing simultaneously: -9dB (reduce by ~87%)

Implementation:
1. For each laugh segment, determine participating speakers
2. Calculate gain reduction based on speaker count
3. Apply smooth fade-in/fade-out (200ms) to avoid abrupt changes
4. Process all tracks with the time-varying gain
"""

from typing import Dict, List
import numpy as np


def db_to_linear(db: float) -> float:
    """Convert dB to linear gain."""
    return 10 ** (db / 20.0)


def get_compression_gain_db(num_speakers: int) -> float:
    """
    Get compression gain in dB based on number of laughing speakers.

    Args:
        num_speakers: Number of speakers laughing simultaneously

    Returns:
        Gain reduction in dB (negative values = attenuation)
    """
    if num_speakers <= 1:
        return 0.0  # Single speaker or solo laugh - no compression
    elif num_speakers == 2:
        return -3.0  # -3dB for 2 speakers
    elif num_speakers == 3:
        return -6.0  # -6dB for 3 speakers
    else:  # 4 or more
        return -9.0  # -9dB for 4+ speakers


def apply_smooth_envelope(
    gain_values: np.ndarray,
    sr: int,
    fade_duration_ms: float = 200,
) -> np.ndarray:
    """
    Apply smooth fade-in/fade-out to gain changes.

    Args:
        gain_values: Gain values for each sample (linear scale, 0-1)
        sr: Sample rate
        fade_duration_ms: Duration of fade in/out

    Returns:
        Smoothed gain values
    """
    fade_samples = int(fade_duration_ms / 1000 * sr)

    if fade_samples <= 0:
        return gain_values

    smoothed = np.copy(gain_values)

    # Find transitions in gain
    transitions = np.diff(gain_values.astype(float) > 0.5).astype(int)
    change_points = np.where(transitions != 0)[0]

    for point in change_points:
        # Fade-out before transition
        fade_start = max(0, point - fade_samples)
        fade_end = min(point, len(smoothed))
        if fade_start < fade_end:
            fade_len = fade_end - fade_start
            fade_curve = np.linspace(1.0, 0.0, fade_len)
            smoothed[fade_start:fade_end] = np.minimum(
                smoothed[fade_start:fade_end],
                fade_curve
            )

        # Fade-in after transition
        fade_start = point
        fade_end = min(point + fade_samples, len(smoothed))
        if fade_start < fade_end:
            fade_len = fade_end - fade_start
            fade_curve = np.linspace(0.0, 1.0, fade_len)
            smoothed[fade_start:fade_end] = np.maximum(
                smoothed[fade_start:fade_end],
                fade_curve
            )

    return smoothed


def create_gain_envelope(
    duration_samples: int,
    sr: int,
    laugh_segments: List[Dict],
    fade_duration_ms: float = 200,
) -> np.ndarray:
    """
    Create time-varying gain envelope based on laugh segments.

    Args:
        duration_samples: Total audio duration in samples
        sr: Sample rate
        laugh_segments: List of laugh segments with speaker info
        fade_duration_ms: Fade duration in milliseconds

    Returns:
        Gain array (linear, 0-1) for each sample
    """
    # Start with unity gain (1.0 = no reduction)
    gain = np.ones(duration_samples, dtype=np.float32)

    # Apply compression for each laugh segment
    for segment in laugh_segments:
        start_sample = int(segment["start"] * sr)
        end_sample = int(segment["end"] * sr)

        # Get speaker count
        num_speakers = segment.get("num_speakers", len(segment.get("speaker_tracks", [])))

        # Calculate gain reduction
        gain_db = get_compression_gain_db(num_speakers)

        # Only apply if reduction is needed
        if gain_db < 0:
            gain_linear = db_to_linear(gain_db)

            # Clamp indices
            start_sample = max(0, min(start_sample, duration_samples))
            end_sample = max(0, min(end_sample, duration_samples))

            if start_sample < end_sample:
                gain[start_sample:end_sample] = gain_linear

    # Apply smooth envelope to transitions
    gain = apply_smooth_envelope(gain, sr, fade_duration_ms)

    return gain


def apply_gain(
    audio: np.ndarray,
    gain: np.ndarray,
) -> np.ndarray:
    """
    Apply gain to audio.

    Args:
        audio: Audio signal
        gain: Gain values (same length as audio)

    Returns:
        Gain-adjusted audio
    """
    if len(audio) != len(gain):
        raise ValueError(
            f"Audio and gain length mismatch: {len(audio)} vs {len(gain)}"
        )

    return audio * gain


def apply_laugh_compression(
    tracks: np.ndarray,
    sr: int,
    laugh_segments: List[Dict],
    fade_duration_ms: float = 200,
) -> np.ndarray:
    """
    Apply dynamic compression to multi-person laugh segments.

    Args:
        tracks: Multi-track audio (num_tracks, num_samples)
        sr: Sample rate
        laugh_segments: List of detected laugh segments
        fade_duration_ms: Fade duration in milliseconds

    Returns:
        Processed multi-track audio with compression applied
    """
    num_tracks, num_samples = tracks.shape

    # Create gain envelope
    gain_envelope = create_gain_envelope(
        num_samples,
        sr,
        laugh_segments,
        fade_duration_ms,
    )

    # Apply to all tracks
    processed_tracks = np.zeros_like(tracks)

    for track_id in range(num_tracks):
        processed_tracks[track_id] = apply_gain(tracks[track_id], gain_envelope)

    return processed_tracks


def apply_laugh_compression_with_report(
    tracks: np.ndarray,
    sr: int,
    laugh_segments: List[Dict],
    fade_duration_ms: float = 200,
) -> tuple:
    """
    Apply laugh compression and return report of compressions applied.

    Args:
        tracks: Multi-track audio
        sr: Sample rate
        laugh_segments: List of laugh segments
        fade_duration_ms: Fade duration

    Returns:
        Tuple of (processed_tracks, compression_report)
    """
    processed_tracks = apply_laugh_compression(
        tracks,
        sr,
        laugh_segments,
        fade_duration_ms,
    )

    # Create compression report
    report = {
        "total_segments": len(laugh_segments),
        "compressions_applied": [],
    }

    for seg in laugh_segments:
        num_speakers = seg.get("num_speakers", len(seg.get("speaker_tracks", [])))
        if num_speakers > 1:
            gain_db = get_compression_gain_db(num_speakers)
            report["compressions_applied"].append({
                "start": round(seg["start"], 3),
                "end": round(seg["end"], 3),
                "duration": round(seg["end"] - seg["start"], 3),
                "num_speakers": num_speakers,
                "speakers": seg.get("speaker_tracks", []),
                "gain_db": gain_db,
                "gain_linear": round(db_to_linear(gain_db), 3),
            })

    report["total_compressions"] = len(report["compressions_applied"])

    return processed_tracks, report


if __name__ == "__main__":
    # Demo usage
    import json

    # Create test data
    num_tracks = 4
    duration_seconds = 10
    sr = 16000
    num_samples = duration_seconds * sr

    # Dummy tracks
    tracks = np.random.randn(num_tracks, num_samples) * 0.1

    # Test laugh segments
    laugh_segments = [
        {
            "start": 2.0,
            "end": 2.5,
            "speaker_tracks": [0],
            "num_speakers": 1,
            "confidence": 0.8,
        },
        {
            "start": 3.0,
            "end": 3.8,
            "speaker_tracks": [0, 1],
            "num_speakers": 2,
            "confidence": 0.85,
        },
        {
            "start": 5.0,
            "end": 5.7,
            "speaker_tracks": [0, 1, 2],
            "num_speakers": 3,
            "confidence": 0.9,
        },
    ]

    # Apply compression
    processed, report = apply_laugh_compression_with_report(
        tracks,
        sr,
        laugh_segments,
    )

    print("Compression Report:")
    print(json.dumps(report, indent=2))
