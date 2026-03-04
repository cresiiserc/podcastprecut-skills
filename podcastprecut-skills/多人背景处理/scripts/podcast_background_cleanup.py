#!/usr/bin/env python3
"""
Multi-Person Podcast Background Audio Processing Script

Complete pipeline for processing 4-person podcast audio:
1. Load aligned audio tracks
2. Detect and suppress background noise during silence
3. Detect laugh segments
4. Apply dynamic compression to multi-person laughs
5. Generate final mixed audio

Usage:
    python3 podcast_background_cleanup.py \
        --input aligned_audio/ \
        --output processed_podcast.wav \
        --report processing_report.json
"""

import argparse
import json
from pathlib import Path
from typing import List, Tuple, Dict, Any

import librosa
import numpy as np
import soundfile as sf

# Import analysis modules
from background_detection import detect_background_segments
from laugh_detection import detect_laugh_segments, analyze_speaker_participation
from dynamic_compression import apply_laugh_compression


class MultiTrackAudioProcessor:
    """Main processor for multi-track podcast audio."""

    def __init__(self, metadata_path: str):
        """
        Initialize processor with alignment metadata.

        Args:
            metadata_path: Path to alignment_metadata.json
        """
        with open(metadata_path, "r", encoding="utf-8") as f:
            self.metadata = json.load(f)

        self.sr = self.metadata["target_sample_rate"]
        self.num_tracks = self.metadata["num_tracks"]
        self.total_length = self.metadata["total_length_samples"]
        self.duration = self.metadata["total_length_seconds"]

        # Will be populated during processing
        self.tracks = None
        self.mixed = None
        self.background_segments = None
        self.laugh_segments = None
        self.report = {}

    def load_tracks(self, audio_dir: str) -> np.ndarray:
        """
        Load aligned audio tracks from directory.

        Args:
            audio_dir: Directory containing track_XX_aligned.wav files

        Returns:
            Array of shape (num_tracks, num_samples)
        """
        tracks = []
        audio_path = Path(audio_dir)

        for i in range(self.num_tracks):
            track_file = audio_path / f"track_{i:02d}_aligned.wav"
            if not track_file.exists():
                raise FileNotFoundError(f"Track file not found: {track_file}")

            audio, sr = librosa.load(track_file, sr=self.sr, mono=True)
            if len(audio) != self.total_length:
                raise ValueError(
                    f"Track {i} length mismatch: "
                    f"expected {self.total_length}, got {len(audio)}"
                )

            tracks.append(audio)
            print(f"Loaded track {i}: {track_file.name} ({len(audio)} samples)")

        self.tracks = np.array(tracks)
        return self.tracks

    def create_mixed_audio(self) -> np.ndarray:
        """
        Create mixed audio from individual tracks.

        Returns:
            Mixed audio array
        """
        if self.tracks is None:
            raise RuntimeError("Tracks not loaded. Call load_tracks() first.")

        # Simple averaging of all tracks
        self.mixed = np.mean(self.tracks, axis=0)
        print(f"Created mixed audio: {len(self.mixed)} samples")

        return self.mixed

    def detect_background_noise(
        self,
        energy_window_ms: int = 100,
        silence_threshold_factor: float = 0.5,
        min_silence_duration_ms: int = 100,
        merge_gap_ms: int = 200
    ) -> Dict[str, Any]:
        """
        Detect background noise segments in individual tracks.

        Args:
            energy_window_ms: Window size for energy calculation
            silence_threshold_factor: Relative threshold (< factor * median = background)
            min_silence_duration_ms: Minimum silence duration to consider
            merge_gap_ms: Gap to merge adjacent segments

        Returns:
            Detection results with segments per track
        """
        print("\nDetecting background noise...")

        self.background_segments = detect_background_segments(
            self.tracks,
            self.sr,
            energy_window_ms=energy_window_ms,
            silence_threshold_factor=silence_threshold_factor,
            min_silence_duration_ms=min_silence_duration_ms,
            merge_gap_ms=merge_gap_ms,
        )

        print(f"Detected background segments: {len(self.background_segments)} total")
        for track_id, segments in self.background_segments.items():
            print(f"  Track {track_id}: {len(segments)} segments")

        return self.background_segments

    def suppress_background_noise(self, fade_duration_ms: int = 50) -> np.ndarray:
        """
        Suppress detected background noise by applying soft fade-out.

        Args:
            fade_duration_ms: Duration of fade-out in milliseconds

        Returns:
            Processed multi-track audio
        """
        if self.background_segments is None:
            raise RuntimeError("Background detection not performed. Call detect_background_noise() first.")

        print(f"\nSuppressing background noise (fade: {fade_duration_ms}ms)...")

        processed_tracks = np.copy(self.tracks)
        fade_samples = int(fade_duration_ms / 1000 * self.sr)

        total_suppressed = 0

        for track_id, segments in self.background_segments.items():
            for segment in segments:
                start_sample = int(segment["start"] * self.sr)
                end_sample = int(segment["end"] * self.sr)

                # Apply soft fade-out at edges, then mute
                if fade_samples > 0:
                    # Fade-out at start
                    fade_start = max(0, start_sample - fade_samples)
                    fade_end = min(start_sample, start_sample + fade_samples)
                    fade_len = fade_end - fade_start
                    if fade_len > 0:
                        fade_curve = np.linspace(1.0, 0.0, fade_len)
                        processed_tracks[track_id, fade_start:fade_end] *= fade_curve

                    # Fade-in at end
                    fade_start = max(end_sample - fade_samples, end_sample)
                    fade_end = min(end_sample + fade_samples, len(processed_tracks[track_id]))
                    fade_len = fade_end - fade_start
                    if fade_len > 0:
                        fade_curve = np.linspace(0.0, 1.0, fade_len)
                        processed_tracks[track_id, fade_start:fade_end] *= fade_curve

                # Zero out the middle section
                processed_tracks[track_id, start_sample:end_sample] = 0.0
                total_suppressed += (end_sample - start_sample)

        print(f"Suppressed {total_suppressed / self.sr:.2f}s of background noise")

        self.tracks = processed_tracks
        return self.tracks

    def detect_laugh_sounds(self) -> Dict[str, Any]:
        """
        Detect laugh sound segments in the mixed audio.

        Returns:
            Detection results with laugh segments
        """
        print("\nDetecting laugh sounds...")

        self.laugh_segments = detect_laugh_segments(
            self.mixed,
            self.sr,
        )

        print(f"Detected {len(self.laugh_segments)} laugh segments")

        # Analyze which speakers are participating in each laugh
        for laugh in self.laugh_segments:
            participating = analyze_speaker_participation(
                self.tracks,
                self.sr,
                laugh["start"],
                laugh["end"],
            )
            laugh["speaker_tracks"] = participating
            laugh["num_speakers"] = len(participating)
            print(f"  {laugh['start']:.2f}s-{laugh['end']:.2f}s: "
                  f"{len(participating)} speakers, confidence: {laugh['confidence']:.2f}")

        return self.laugh_segments

    def apply_laugh_dynamic_compression(self) -> np.ndarray:
        """
        Apply dynamic compression to multi-person laugh segments.

        Returns:
            Processed multi-track audio
        """
        if self.laugh_segments is None:
            raise RuntimeError("Laugh detection not performed. Call detect_laugh_sounds() first.")

        print("\nApplying dynamic compression to laughs...")

        processed_tracks = apply_laugh_compression(
            self.tracks,
            self.sr,
            self.laugh_segments,
        )

        print("Laugh compression applied")
        self.tracks = processed_tracks
        return self.tracks

    def create_final_mixed_audio(self) -> np.ndarray:
        """
        Create final mixed audio from processed tracks.

        Returns:
            Final mixed audio
        """
        self.mixed = np.mean(self.tracks, axis=0)
        print(f"Created final mixed audio: {len(self.mixed)} samples")
        return self.mixed

    def save_output(
        self,
        output_audio_path: str,
        report_path: str = None,
    ) -> None:
        """
        Save processed audio and processing report.

        Args:
            output_audio_path: Path for output WAV file
            report_path: Path for JSON report (optional)
        """
        # Save audio
        sf.write(output_audio_path, self.mixed, self.sr)
        print(f"Saved output audio: {output_audio_path}")

        # Save report
        if report_path:
            report = {
                "metadata": self.metadata,
                "processing": {
                    "background_suppression": {
                        "segments_found": len(self.background_segments) if self.background_segments else 0,
                        "total_duration_suppressed_seconds": sum(
                            seg["end"] - seg["start"]
                            for segs in (self.background_segments or {}).values()
                            for seg in segs
                        ),
                    },
                    "laugh_detection": {
                        "segments_found": len(self.laugh_segments) if self.laugh_segments else 0,
                        "segments": [
                            {
                                "start": round(seg["start"], 3),
                                "end": round(seg["end"], 3),
                                "duration": round(seg["end"] - seg["start"], 3),
                                "speaker_tracks": seg.get("speaker_tracks", []),
                                "num_speakers": seg.get("num_speakers", 0),
                                "confidence": round(seg.get("confidence", 0), 3),
                            }
                            for seg in (self.laugh_segments or [])
                        ],
                    },
                },
                "output": {
                    "sample_rate": self.sr,
                    "duration_seconds": round(self.duration, 2),
                    "num_samples": len(self.mixed),
                },
            }

            with open(report_path, "w", encoding="utf-8") as f:
                json.dump(report, f, ensure_ascii=False, indent=2)
            print(f"Saved report: {report_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Multi-person podcast background audio cleanup"
    )
    parser.add_argument(
        "--input", "-i",
        required=True,
        help="Input directory with aligned audio tracks (from audio_alignment.py)"
    )
    parser.add_argument(
        "--output", "-o",
        required=True,
        help="Output audio file path (WAV)"
    )
    parser.add_argument(
        "--report", "-r",
        help="Output JSON report path"
    )
    parser.add_argument(
        "--skip-background",
        action="store_true",
        help="Skip background noise detection and suppression"
    )
    parser.add_argument(
        "--skip-laugh",
        action="store_true",
        help="Skip laugh detection and compression"
    )

    args = parser.parse_args()

    # Validate input
    input_path = Path(args.input)
    if not input_path.exists():
        parser.error(f"Input directory not found: {args.input}")

    metadata_file = input_path / "alignment_metadata.json"
    if not metadata_file.exists():
        parser.error(f"Metadata file not found: {metadata_file}")

    # Initialize processor
    print("Initializing processor...")
    processor = MultiTrackAudioProcessor(str(metadata_file))

    # Load and process
    processor.load_tracks(args.input)
    processor.create_mixed_audio()

    if not args.skip_background:
        processor.detect_background_noise()
        processor.suppress_background_noise()

    if not args.skip_laugh:
        # Need to create mixed audio after background suppression
        processor.create_mixed_audio()
        processor.detect_laugh_sounds()
        processor.apply_laugh_dynamic_compression()

    # Create final output
    processor.create_final_mixed_audio()
    processor.save_output(args.output, args.report)

    print("\nProcessing complete!")


if __name__ == "__main__":
    main()
