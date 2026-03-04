#!/usr/bin/env python3
"""
Unit tests and validation for multi-person podcast background processing.

Run with:
    python3 test_modules.py
"""

import json
import tempfile
from pathlib import Path
import unittest

import numpy as np
import librosa
import soundfile as sf

# Import modules to test
from background_detection import (
    detect_background_in_track,
    detect_background_segments,
    calculate_energy_time_series,
)
from laugh_detection import (
    detect_laugh_frames,
    detect_laugh_segments,
    analyze_speaker_participation,
)
from dynamic_compression import (
    get_compression_gain_db,
    create_gain_envelope,
    apply_laugh_compression,
    db_to_linear,
)


class TestAudioGeneration:
    """Utilities for generating test audio."""

    @staticmethod
    def generate_white_noise(duration_s: float, sr: int = 16000) -> np.ndarray:
        """Generate white noise."""
        num_samples = int(duration_s * sr)
        return np.random.randn(num_samples) * 0.1

    @staticmethod
    def generate_sine_wave(duration_s: float, frequency: float, sr: int = 16000) -> np.ndarray:
        """Generate sine wave."""
        num_samples = int(duration_s * sr)
        t = np.arange(num_samples) / sr
        return np.sin(2 * np.pi * frequency * t) * 0.3

    @staticmethod
    def generate_speech_like(duration_s: float, sr: int = 16000) -> np.ndarray:
        """Generate speech-like audio (mix of frequencies)."""
        num_samples = int(duration_s * sr)
        t = np.arange(num_samples) / sr

        # Fundamental + harmonics
        speech = (
            0.2 * np.sin(2 * np.pi * 150 * t) +  # F0
            0.1 * np.sin(2 * np.pi * 300 * t) +  # 2nd harmonic
            0.05 * np.sin(2 * np.pi * 450 * t)   # 3rd harmonic
        )

        # Add envelope (natural speech has amplitude variations)
        envelope = 0.5 + 0.5 * np.abs(np.sin(2 * np.pi * 2 * t))
        return speech * envelope * 0.1

    @staticmethod
    def generate_laugh_like(duration_s: float, sr: int = 16000) -> np.ndarray:
        """Generate laugh-like audio (high frequency bursts)."""
        num_samples = int(duration_s * sr)
        t = np.arange(num_samples) / sr

        # High frequency burst pattern
        burst_freq = 0.5  # Bursts every 2 seconds
        burst_pattern = 0.3 * (np.sin(2 * np.pi * burst_freq * t) > 0).astype(float)

        # High frequency content
        laugh = (
            0.2 * burst_pattern * np.sin(2 * np.pi * 1500 * t) +
            0.15 * burst_pattern * np.sin(2 * np.pi * 2000 * t)
        )

        # Fast amplitude modulation (characteristic of laugh)
        modulation = np.abs(np.sin(2 * np.pi * 15 * t))
        return laugh * modulation * 0.15


class TestBackgroundDetection(unittest.TestCase):
    """Tests for background noise detection."""

    def test_energy_calculation(self):
        """Test RMS energy calculation."""
        audio = TestAudioGeneration.generate_white_noise(1.0)
        sr = 16000

        rms, times, hop_length = calculate_energy_time_series(audio, sr, window_ms=100)

        # Check output shapes
        self.assertEqual(len(rms), len(times))
        self.assertGreater(len(rms), 0)

        # Check energy values are positive
        self.assertTrue(np.all(rms >= 0))

    def test_background_detection_silence(self):
        """Test that silence is detected as background."""
        # Create audio with clear silence
        silent = np.zeros(16000)  # 1 second of silence

        segments = detect_background_in_track(
            silent,
            sr=16000,
            min_silence_duration_ms=100,
        )

        # Most of silence should be detected
        self.assertGreater(len(segments), 0)
        total_duration = sum(s["duration"] for s in segments)
        self.assertGreater(total_duration, 0.5)  # At least 500ms detected

    def test_background_detection_speech(self):
        """Test that speech is not detected as background."""
        audio = TestAudioGeneration.generate_speech_like(2.0)

        segments = detect_background_in_track(
            audio,
            sr=16000,
            min_silence_duration_ms=100,
        )

        # Speech should have minimal background detection
        total_duration = sum(s["duration"] for s in segments)
        self.assertLess(total_duration, 0.5)  # Less than 500ms

    def test_multi_track_detection(self):
        """Test detection on multiple tracks."""
        sr = 16000
        tracks = np.array([
            TestAudioGeneration.generate_speech_like(2.0, sr),
            TestAudioGeneration.generate_white_noise(2.0, sr) * 0.01,  # Background
            np.zeros(32000),  # Silence
        ])

        results = detect_background_segments(tracks, sr)

        # Should have one result per track
        self.assertEqual(len(results), 3)

        # Track 0 (speech) should have minimal background
        self.assertLess(len(results[0]), 5)

        # Track 2 (silence) should have maximal background
        self.assertGreater(len(results[2]), 5)


class TestLaughDetection(unittest.TestCase):
    """Tests for laugh sound detection."""

    def test_laugh_detection_on_laugh(self):
        """Test that laugh-like audio is detected as laugh."""
        audio = TestAudioGeneration.generate_laugh_like(2.0)

        segments = detect_laugh_segments(audio, sr=16000)

        # Should detect some laugh segments
        self.assertGreater(len(segments), 0)

        # Segments should have reasonable confidence
        for seg in segments:
            self.assertGreater(seg["confidence"], 0.3)

    def test_laugh_detection_on_speech(self):
        """Test that speech is not detected as laugh."""
        audio = TestAudioGeneration.generate_speech_like(3.0)

        segments = detect_laugh_segments(audio, sr=16000)

        # Speech should have few or no laugh detections
        self.assertLess(len(segments), 3)

    def test_laugh_detection_confidence(self):
        """Test that laugh segments have confidence scores."""
        audio = TestAudioGeneration.generate_laugh_like(2.0)

        segments = detect_laugh_segments(audio, sr=16000)

        for seg in segments:
            self.assertIn("confidence", seg)
            self.assertGreaterEqual(seg["confidence"], 0.0)
            self.assertLessEqual(seg["confidence"], 1.0)

    def test_speaker_participation_detection(self):
        """Test detection of which speakers are laughing."""
        sr = 16000
        duration = 2.0

        tracks = np.array([
            TestAudioGeneration.generate_laugh_like(duration, sr),      # Speaker 0: laughing
            TestAudioGeneration.generate_speech_like(duration, sr),     # Speaker 1: speaking
            TestAudioGeneration.generate_laugh_like(duration, sr),      # Speaker 2: laughing
            np.zeros(int(duration * sr)),                              # Speaker 3: silent
        ])

        # Analyze middle section (where laugh is expected)
        participants = analyze_speaker_participation(
            tracks,
            sr,
            laugh_start=0.5,
            laugh_end=1.5,
        )

        # Should include speakers 0 and 2 (laughing)
        self.assertIn(0, participants)
        self.assertIn(2, participants)


class TestDynamicCompression(unittest.TestCase):
    """Tests for laugh dynamic compression."""

    def test_compression_gain_single_speaker(self):
        """Test no compression for single speaker."""
        gain_db = get_compression_gain_db(1)
        self.assertEqual(gain_db, 0.0)

    def test_compression_gain_two_speakers(self):
        """Test -3dB compression for two speakers."""
        gain_db = get_compression_gain_db(2)
        self.assertEqual(gain_db, -3.0)

    def test_compression_gain_three_speakers(self):
        """Test -6dB compression for three speakers."""
        gain_db = get_compression_gain_db(3)
        self.assertEqual(gain_db, -6.0)

    def test_compression_gain_four_speakers(self):
        """Test -9dB compression for four speakers."""
        gain_db = get_compression_gain_db(4)
        self.assertEqual(gain_db, -9.0)

    def test_db_to_linear_conversion(self):
        """Test dB to linear conversion."""
        # -3dB should be approximately 0.707 (1/sqrt(2))
        linear = db_to_linear(-3.0)
        self.assertAlmostEqual(linear, 1/np.sqrt(2), places=2)

        # 0dB should be 1.0
        linear = db_to_linear(0.0)
        self.assertAlmostEqual(linear, 1.0, places=5)

    def test_gain_envelope_creation(self):
        """Test creation of gain envelope."""
        sr = 16000
        duration_samples = 30000  # 1.875 seconds

        laugh_segments = [
            {
                "start": 0.5,
                "end": 1.0,
                "num_speakers": 2,
                "speaker_tracks": [0, 1],
            }
        ]

        gain = create_gain_envelope(duration_samples, sr, laugh_segments)

        # Check shape
        self.assertEqual(len(gain), duration_samples)

        # Check values in range
        self.assertTrue(np.all(gain >= 0))
        self.assertTrue(np.all(gain <= 1))

        # Check that laugh segment has reduced gain
        laugh_start_sample = int(0.5 * sr)
        laugh_end_sample = int(1.0 * sr)
        laugh_gain = np.mean(gain[laugh_start_sample:laugh_end_sample])
        self.assertLess(laugh_gain, 0.8)  # Should be < 0.707 (-3dB)

    def test_compression_application(self):
        """Test applying compression to tracks."""
        sr = 16000
        duration = 1.0

        # Create identical test tracks
        test_signal = TestAudioGeneration.generate_laugh_like(duration, sr)
        tracks = np.array([test_signal, test_signal])

        laugh_segments = [
            {
                "start": 0.3,
                "end": 0.7,
                "num_speakers": 2,
                "speaker_tracks": [0, 1],
            }
        ]

        processed = apply_laugh_compression(tracks, sr, laugh_segments)

        # Check shape preserved
        self.assertEqual(processed.shape, tracks.shape)

        # Check that laugh segment is quieter
        laugh_start = int(0.3 * sr)
        laugh_end = int(0.7 * sr)

        original_energy = np.sqrt(np.mean(tracks[:, laugh_start:laugh_end] ** 2))
        processed_energy = np.sqrt(np.mean(processed[:, laugh_start:laugh_end] ** 2))

        self.assertLess(processed_energy, original_energy)


class TestIntegration(unittest.TestCase):
    """Integration tests for the full pipeline."""

    def test_create_test_files(self):
        """Test creating temporary test audio files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sr = 16000
            tmpdir = Path(tmpdir)

            # Create 4 test audio files
            files = []
            for i in range(4):
                audio = TestAudioGeneration.generate_speech_like(1.0, sr)
                path = tmpdir / f"speaker_{i}.wav"
                sf.write(path, audio, sr)
                files.append(str(path))

            # Check files exist
            self.assertEqual(len(files), 4)
            for path in files:
                self.assertTrue(Path(path).exists())

    def test_end_to_end_mock(self):
        """Test a mock end-to-end pipeline."""
        sr = 16000

        # Create test tracks
        tracks = np.array([
            TestAudioGeneration.generate_speech_like(3.0, sr),
            TestAudioGeneration.generate_speech_like(3.0, sr) + TestAudioGeneration.generate_white_noise(3.0, sr) * 0.01,
            TestAudioGeneration.generate_speech_like(3.0, sr) + TestAudioGeneration.generate_white_noise(3.0, sr) * 0.01,
            TestAudioGeneration.generate_laugh_like(3.0, sr),
        ])

        # Detect background
        backgrounds = detect_background_segments(tracks, sr)
        self.assertEqual(len(backgrounds), 4)

        # Mix audio
        mixed = np.mean(tracks, axis=0)

        # Detect laugh
        laughs = detect_laugh_segments(mixed, sr)
        self.assertGreater(len(laughs), 0)

        # Apply compression
        processed = apply_laugh_compression(tracks, sr, laughs)
        self.assertEqual(processed.shape, tracks.shape)


def run_tests():
    """Run all tests."""
    print("=" * 70)
    print("Multi-Person Podcast Background Processing - Unit Tests")
    print("=" * 70)

    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Add test classes
    suite.addTests(loader.loadTestsFromTestCase(TestBackgroundDetection))
    suite.addTests(loader.loadTestsFromTestCase(TestLaughDetection))
    suite.addTests(loader.loadTestsFromTestCase(TestDynamicCompression))
    suite.addTests(loader.loadTestsFromTestCase(TestIntegration))

    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # Summary
    print("\n" + "=" * 70)
    print("Test Summary")
    print("=" * 70)
    print(f"Tests run: {result.testsRun}")
    print(f"Successes: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")

    if result.wasSuccessful():
        print("\n✓ All tests passed!")
        return 0
    else:
        print("\n✗ Some tests failed")
        return 1


if __name__ == "__main__":
    exit(run_tests())
