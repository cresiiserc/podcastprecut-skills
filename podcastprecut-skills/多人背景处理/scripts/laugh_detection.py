#!/usr/bin/env python3
"""
Phase 3: Laugh Sound Feature Detection

Identify laugh segments in podcast audio by analyzing:
1. MFCC (Mel Frequency Cepstral Coefficients) - spectral characteristics
2. ZCR (Zero Crossing Rate) - high-frequency content
3. Energy bursts - rapid amplitude changes
4. Spectral centroid - frequency distribution

Algorithm:
1. Extract MFCC, ZCR, and spectral centroid features
2. Calculate frame-by-frame energy bursts (entropy of energy changes)
3. Identify frames with laugh characteristics:
   - High energy variance (burst pattern)
   - High ZCR (high frequencies)
   - Distinct spectral characteristics (MFCC distance from speech)
4. Cluster consecutive laugh frames into segments
5. Validate segments by confidence score
"""

from typing import Dict, List
import numpy as np
import librosa


def extract_features(
    audio: np.ndarray,
    sr: int,
    window_ms: int = 50,
) -> tuple:
    """
    Extract audio features for laugh detection.

    Args:
        audio: Audio signal
        sr: Sample rate
        window_ms: Window size in milliseconds

    Returns:
        Tuple of (mfcc, zcr, energy, times, hop_length)
    """
    hop_length = int(window_ms / 1000 * sr)

    # MFCC - 13 coefficients
    mfcc = librosa.feature.mfcc(y=audio, sr=sr, n_mfcc=13, hop_length=hop_length)

    # Zero Crossing Rate
    zcr = librosa.feature.zero_crossing_rate(audio, hop_length=hop_length)[0]

    # RMS Energy
    rms = librosa.feature.rms(y=audio, hop_length=hop_length)[0]

    # Frame times
    times = librosa.frames_to_time(np.arange(len(zcr)), sr=sr, hop_length=hop_length)

    return mfcc, zcr, rms, times, hop_length


def calculate_energy_bursts(
    energy: np.ndarray,
    window_size: int = 3,
) -> np.ndarray:
    """
    Detect energy bursts (rapid changes in energy).

    Laugh typically has rapid ups and downs in energy.

    Args:
        energy: RMS energy array
        window_size: Window for local variance calculation

    Returns:
        Energy burst score for each frame
    """
    # Normalize energy
    energy_norm = (energy - np.min(energy)) / (np.max(energy) - np.min(energy) + 1e-10)

    # Calculate local variance (burst indicator)
    burst_score = np.zeros_like(energy)

    for i in range(len(energy)):
        start = max(0, i - window_size)
        end = min(len(energy), i + window_size + 1)
        local = energy_norm[start:end]
        burst_score[i] = np.std(local)

    return burst_score


def calculate_spectral_centroid(
    audio: np.ndarray,
    sr: int,
    hop_length: int,
) -> np.ndarray:
    """
    Calculate spectral centroid (center of mass of spectrum).

    Laughs have distinctive frequency distribution.

    Args:
        audio: Audio signal
        sr: Sample rate
        hop_length: Hop length for STFT

    Returns:
        Spectral centroid for each frame
    """
    centroid = librosa.feature.spectral_centroid(y=audio, sr=sr, hop_length=hop_length)[0]
    return centroid


def detect_laugh_frames(
    mfcc: np.ndarray,
    zcr: np.ndarray,
    energy: np.ndarray,
    burst_score: np.ndarray,
    centroid: np.ndarray,
    sr: int,
) -> np.ndarray:
    """
    Identify frames likely to be laughs based on acoustic features.

    Args:
        mfcc: MFCC features (n_mfcc, num_frames)
        zcr: Zero crossing rate (num_frames,)
        energy: RMS energy (num_frames,)
        burst_score: Energy burst score (num_frames,)
        centroid: Spectral centroid (num_frames,)
        sr: Sample rate

    Returns:
        Boolean array indicating laugh frames
    """
    num_frames = len(zcr)

    # Normalize features to 0-1 range for comparison
    zcr_norm = (zcr - np.min(zcr)) / (np.max(zcr) - np.min(zcr) + 1e-10)
    energy_norm = (energy - np.min(energy)) / (np.max(energy) - np.min(energy) + 1e-10)
    burst_norm = (burst_score - np.min(burst_score)) / (np.max(burst_score) - np.min(burst_score) + 1e-10)
    centroid_norm = (centroid - np.min(centroid)) / (np.max(centroid) - np.min(centroid) + 1e-10)

    # Laugh indicators:
    # 1. High energy variance (burst score) - rapid energy changes
    high_burst = burst_norm > np.percentile(burst_norm, 60)

    # 2. Elevated ZCR (higher frequency content than speech)
    high_zcr = zcr_norm > np.percentile(zcr_norm, 50)

    # 3. Energy not too low (needs to be present)
    sufficient_energy = energy_norm > np.percentile(energy_norm, 30)

    # 4. Spectral centroid in "laugh range" (typically 800-3000 Hz for laughter)
    # Map normalized centroid back to Hz range
    freq_in_range = centroid > 800  # Minimum frequency threshold

    # Laugh = high burst + (high zcr or energy changes)
    laugh_mask = (high_burst | high_zcr) & sufficient_energy & freq_in_range

    return laugh_mask


def cluster_laugh_segments(
    laugh_mask: np.ndarray,
    times: np.ndarray,
    min_duration_ms: float = 200,
    merge_gap_ms: float = 150,
) -> List[Dict]:
    """
    Convert laugh frame mask to continuous segments.

    Args:
        laugh_mask: Boolean array of laugh frames
        times: Frame times
        min_duration_ms: Minimum segment duration
        merge_gap_ms: Gap to merge nearby segments

    Returns:
        List of laugh segments
    """
    # Find transitions
    transitions = np.diff(laugh_mask.astype(int))
    starts = np.where(transitions == 1)[0] + 1
    ends = np.where(transitions == -1)[0] + 1

    # Handle edges
    if laugh_mask[0]:
        starts = np.concatenate([[0], starts])
    if laugh_mask[-1]:
        ends = np.concatenate([ends, [len(laugh_mask)]])

    segments = []

    for start_idx, end_idx in zip(starts, ends):
        start_time = times[min(start_idx, len(times) - 1)]
        end_time = times[min(end_idx - 1, len(times) - 1)]

        duration = (end_time - start_time) * 1000

        # Filter by minimum duration
        if duration < min_duration_ms:
            continue

        segments.append({
            "start": float(start_time),
            "end": float(end_time),
            "duration": float(end_time - start_time),
            "num_frames": int(end_idx - start_idx),
        })

    # Merge nearby segments
    if not segments:
        return []

    merge_gap_sec = merge_gap_ms / 1000.0
    merged = [segments[0]]

    for seg in segments[1:]:
        if seg["start"] - merged[-1]["end"] < merge_gap_sec:
            merged[-1]["end"] = seg["end"]
            merged[-1]["duration"] = merged[-1]["end"] - merged[-1]["start"]
            merged[-1]["num_frames"] += seg["num_frames"]
        else:
            merged.append(seg)

    return merged


def calculate_segment_confidence(
    laugh_frames: np.ndarray,
    segment_start_idx: int,
    segment_end_idx: int,
    laugh_mask: np.ndarray,
) -> float:
    """
    Calculate confidence score for a laugh segment.

    Args:
        laugh_frames: Laugh probability for each frame (0-1)
        segment_start_idx: Start frame index
        segment_end_idx: End frame index
        laugh_mask: Boolean laugh mask

    Returns:
        Confidence score (0-1)
    """
    segment = laugh_frames[segment_start_idx:segment_end_idx]
    if len(segment) == 0:
        return 0.0

    # Confidence = mean of laugh probability + proportion of laugh frames
    mean_prob = np.mean(segment)
    laugh_proportion = np.sum(laugh_mask[segment_start_idx:segment_end_idx]) / len(segment)

    confidence = (mean_prob + laugh_proportion) / 2.0
    return float(np.clip(confidence, 0, 1))


def detect_laugh_segments(
    audio: np.ndarray,
    sr: int,
    window_ms: int = 50,
    min_duration_ms: float = 200,
    merge_gap_ms: float = 150,
) -> List[Dict]:
    """
    Detect laugh segments in audio.

    Args:
        audio: Audio signal
        sr: Sample rate
        window_ms: Window size for feature extraction
        min_duration_ms: Minimum segment duration
        merge_gap_ms: Gap to merge segments

    Returns:
        List of laugh segments with confidence scores
    """
    # Extract features
    mfcc, zcr, energy, times, hop_length = extract_features(audio, sr, window_ms)

    # Calculate additional features
    burst_score = calculate_energy_bursts(energy)
    centroid = calculate_spectral_centroid(audio, sr, hop_length)

    # Detect laugh frames
    laugh_mask = detect_laugh_frames(mfcc, zcr, energy, burst_score, centroid, sr)

    # Cluster into segments
    segments = cluster_laugh_segments(laugh_mask, times, min_duration_ms, merge_gap_ms)

    # Add confidence scores
    # Create continuous confidence score
    laugh_confidence = laugh_mask.astype(float)

    for segment in segments:
        start_time = segment["start"]
        end_time = segment["end"]
        start_idx = int(start_time * sr / hop_length)
        end_idx = int(end_time * sr / hop_length)

        confidence = calculate_segment_confidence(
            laugh_confidence,
            start_idx,
            end_idx,
            laugh_mask,
        )
        segment["confidence"] = confidence

    return segments


def analyze_speaker_participation(
    tracks: np.ndarray,
    sr: int,
    laugh_start: float,
    laugh_end: float,
    energy_threshold_percentile: float = 60,
) -> List[int]:
    """
    Determine which speakers are actively laughing during a laugh segment.

    Args:
        tracks: Multi-track audio (num_tracks, num_samples)
        sr: Sample rate
        laugh_start: Laugh segment start time (seconds)
        laugh_end: Laugh segment end time (seconds)
        energy_threshold_percentile: Percentile threshold for participation

    Returns:
        List of track IDs that are laughing
    """
    start_sample = int(laugh_start * sr)
    end_sample = int(laugh_end * sr)

    participating = []

    for track_id, audio in enumerate(tracks):
        segment = audio[start_sample:end_sample]
        if len(segment) == 0:
            continue

        # Calculate energy in this segment
        segment_energy = np.sqrt(np.mean(segment ** 2))

        # Calculate baseline energy for this track
        baseline_energy = np.sqrt(np.mean(audio ** 2))

        # If segment energy is significantly above baseline, speaker is participating
        energy_ratio = segment_energy / (baseline_energy + 1e-10)

        # Threshold: if energy is at least 50% of baseline, consider as participating
        if energy_ratio > 0.5:
            participating.append(track_id)

    return participating


if __name__ == "__main__":
    # Demo usage
    import soundfile as sf
    from pathlib import Path

    # Load a test audio file
    test_file = Path("test_audio.wav")
    if test_file.exists():
        audio, sr = librosa.load(test_file, sr=16000, mono=True)

        segments = detect_laugh_segments(audio, sr)

        print(f"Detected {len(segments)} laugh segments:")
        for seg in segments:
            print(f"  {seg['start']:.2f}s - {seg['end']:.2f}s "
                  f"(confidence: {seg['confidence']:.2f})")
