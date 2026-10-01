"""Unit tests for price, volume, and time spatial sonification."""

import io
import unittest

import numpy as np
from scipy.io.wavfile import read

from spatial_audio import (
    calculate_stereo_pan,
    generate_spatial_audio,
    map_price_to_frequency,
    map_volume_to_amplitude,
    normalize_volume,
)


class SpatialAudioTest(unittest.TestCase):
    def test_rising_prices_produce_rising_frequencies(self):
        frequencies = map_price_to_frequency([10, 20, 40], 200, 800)
        self.assertTrue(np.all(np.diff(frequencies) > 0))
        self.assertAlmostEqual(frequencies[0], 200)
        self.assertAlmostEqual(frequencies[-1], 800)

    def test_volume_is_log_scaled_and_bounded(self):
        normalized = normalize_volume([1, 10, 100, 1_000_000])
        amplitudes = map_volume_to_amplitude([1, 10, 100, 1_000_000], 4, 0.1, 0.8)
        self.assertTrue(np.all((normalized >= 0) & (normalized <= 1)))
        self.assertTrue(np.all((amplitudes >= 0.1) & (amplitudes <= 0.8)))
        self.assertTrue(np.all(np.diff(amplitudes) >= 0))

    def test_constant_power_pan_moves_from_left_to_right(self):
        left, right = calculate_stereo_pan(101)
        self.assertGreater(left[0], right[0])
        self.assertAlmostEqual(left[50], right[50], places=6)
        self.assertLess(left[-1], right[-1])
        np.testing.assert_allclose(left ** 2 + right ** 2, 1.0, atol=1e-7)

    def test_generated_wav_preserves_volume_and_pan(self):
        output = generate_spatial_audio(
            [100, 110, 120, 130],
            [10, 20, 100, 1000],
            duration_seconds=2,
            sample_rate=8000,
        )
        self.assertIsInstance(output, io.BytesIO)
        sample_rate, audio = read(output)
        self.assertEqual(sample_rate, 8000)
        self.assertEqual(audio.ndim, 2)
        self.assertEqual(audio.shape[1], 2)
        quarter = len(audio) // 4
        early_left = np.sqrt(np.mean(audio[:quarter, 0].astype(float) ** 2))
        early_right = np.sqrt(np.mean(audio[:quarter, 1].astype(float) ** 2))
        late_left = np.sqrt(np.mean(audio[-quarter:, 0].astype(float) ** 2))
        late_right = np.sqrt(np.mean(audio[-quarter:, 1].astype(float) ** 2))
        self.assertGreater(early_left, early_right)
        self.assertGreater(late_right, late_left)
        self.assertGreater(late_right, early_right)

    def test_rejects_misaligned_series(self):
        with self.assertRaisesRegex(ValueError, "same length"):
            generate_spatial_audio([1, 2, 3], [10, 20])


if __name__ == "__main__":
    unittest.main(verbosity=2)
