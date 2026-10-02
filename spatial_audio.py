"""Spatial sonification for aligned time-series data.

The primary series controls pitch, an optional supporting series controls
amplitude, and progress through time controls stereo position.
"""

from __future__ import annotations

import io
from typing import Optional, Sequence, Tuple

import numpy as np
from scipy import signal
from scipy.io.wavfile import write

import config


def _as_finite_array(values: Sequence[float], name: str) -> np.ndarray:
    array = np.asarray(values, dtype=float)
    if array.ndim != 1 or array.size < 2:
        raise ValueError(f"{name} must contain at least two values")
    if not np.all(np.isfinite(array)):
        raise ValueError(f"{name} must contain only finite numbers")
    return array


def normalize_price(prices: Sequence[float]) -> np.ndarray:
    """Normalize a primary graph series to 0..1 without changing its shape."""
    values = _as_finite_array(prices, "prices")
    minimum = float(np.min(values))
    maximum = float(np.max(values))
    if np.isclose(minimum, maximum):
        return np.full(values.shape, 0.5, dtype=float)
    return (values - minimum) / (maximum - minimum)


def normalize_volume(
    volumes: Sequence[float],
    lower_percentile: float = 5.0,
    upper_percentile: float = 95.0,
) -> np.ndarray:
    """Log-scale and robustly normalize supporting graph values to 0..1."""
    values = _as_finite_array(volumes, "volumes")
    if np.any(values < 0):
        raise ValueError("volumes must not contain negative values")
    if not 0 <= lower_percentile < upper_percentile <= 100:
        raise ValueError("volume percentiles must satisfy 0 <= lower < upper <= 100")

    logged = np.log1p(values)
    low, high = np.percentile(logged, [lower_percentile, upper_percentile])
    if np.isclose(low, high):
        return np.full(values.shape, 0.5, dtype=float)
    clipped = np.clip(logged, low, high)
    return (clipped - low) / (high - low)


def map_price_to_frequency(
    prices: Sequence[float],
    min_frequency: float = config.DEFAULT_MIN_FREQ,
    max_frequency: float = config.DEFAULT_MAX_FREQ,
) -> np.ndarray:
    """Map graph height to an exponential frequency scale."""
    min_frequency = float(min_frequency)
    max_frequency = float(max_frequency)
    if min_frequency <= 0 or max_frequency <= min_frequency:
        raise ValueError("max_frequency must be greater than a positive min_frequency")
    normalized = normalize_price(prices)
    return min_frequency * np.power(max_frequency / min_frequency, normalized)


def map_volume_to_amplitude(
    volumes: Optional[Sequence[float]],
    point_count: int,
    min_amplitude: float = config.DEFAULT_MIN_AMPLITUDE,
    max_amplitude: float = config.DEFAULT_MAX_AMPLITUDE,
) -> np.ndarray:
    """Map an optional supporting graph to a safe amplitude envelope."""
    min_amplitude = float(min_amplitude)
    max_amplitude = float(max_amplitude)
    if not 0 <= min_amplitude < max_amplitude <= 1:
        raise ValueError("amplitude range must satisfy 0 <= min < max <= 1")
    if point_count < 2:
        raise ValueError("point_count must be at least two")
    if volumes is None:
        return np.full(point_count, (min_amplitude + max_amplitude) / 2, dtype=float)
    normalized = normalize_volume(volumes)
    if len(normalized) != point_count:
        raise ValueError("prices and volumes must have the same length")
    return min_amplitude + normalized * (max_amplitude - min_amplitude)


def calculate_stereo_pan(
    sample_count: int,
    start_progress: float = 0.0,
    end_progress: float = 1.0,
) -> Tuple[np.ndarray, np.ndarray]:
    """Return constant-power left/right gains for a global time range."""
    if sample_count < 2:
        raise ValueError("sample_count must be at least two")
    if not 0 <= start_progress <= end_progress <= 1:
        raise ValueError("pan progress must satisfy 0 <= start <= end <= 1")
    progress = np.linspace(start_progress, end_progress, sample_count)
    return np.cos(progress * np.pi / 2), np.sin(progress * np.pi / 2)


def smooth_amplitude(
    amplitudes: Sequence[float],
    sample_rate: int = config.SAMPLE_RATE,
    transition_ms: float = config.AMPLITUDE_SMOOTHING_MS,
) -> np.ndarray:
    """Apply a short symmetric smoothing window to prevent gain clicks."""
    values = np.asarray(amplitudes, dtype=float)
    if values.ndim != 1 or values.size < 2:
        raise ValueError("amplitudes must contain at least two values")
    window = max(1, int(sample_rate * transition_ms / 1000.0))
    if window <= 1:
        return values.copy()
    window = min(window, len(values))
    padding = (window // 2, window - 1 - window // 2)
    padded = np.pad(values, padding, mode="edge")
    cumulative = np.cumsum(np.insert(padded, 0, 0.0))
    return (cumulative[window:] - cumulative[:-window]) / window


def _wave_from_phase(phases: np.ndarray, waveform_type: str) -> np.ndarray:
    waveform = str(waveform_type).lower()
    if waveform == "square":
        return signal.square(phases)
    if waveform == "sawtooth":
        return signal.sawtooth(phases)
    if waveform == "triangle":
        return signal.sawtooth(phases, width=0.5)
    if waveform == "pulse":
        return signal.square(phases, duty=0.2)
    if waveform != "sine":
        raise ValueError(f"unsupported waveform: {waveform_type}")
    return np.sin(phases)


def _interpolate(values: np.ndarray, target_length: int) -> np.ndarray:
    source_axis = np.linspace(0.0, 1.0, len(values))
    target_axis = np.linspace(0.0, 1.0, target_length)
    return np.interp(target_axis, source_axis, values)


def generate_spatial_audio(
    prices: Sequence[float],
    volumes: Optional[Sequence[float]] = None,
    *,
    min_frequency: float = config.DEFAULT_MIN_FREQ,
    max_frequency: float = config.DEFAULT_MAX_FREQ,
    min_amplitude: float = config.DEFAULT_MIN_AMPLITUDE,
    max_amplitude: float = config.DEFAULT_MAX_AMPLITUDE,
    duration_seconds: float = config.TOTAL_PLAY_TIME,
    waveform_type: str = "sine",
    start_progress: float = 0.0,
    end_progress: float = 1.0,
    sample_rate: int = config.SAMPLE_RATE,
) -> io.BytesIO:
    """Generate one stereo WAV combining pitch, amplitude, and time position."""
    price_values = _as_finite_array(prices, "prices")
    duration_seconds = float(duration_seconds)
    if not config.MIN_PLAY_TIME <= duration_seconds <= config.MAX_PLAY_TIME:
        raise ValueError(
            f"duration_seconds must be between {config.MIN_PLAY_TIME} and {config.MAX_PLAY_TIME}"
        )
    target_length = int(duration_seconds * sample_rate)

    point_frequencies = map_price_to_frequency(price_values, min_frequency, max_frequency)
    point_amplitudes = map_volume_to_amplitude(
        volumes, len(price_values), min_amplitude, max_amplitude
    )
    frequencies = _interpolate(point_frequencies, target_length)
    amplitudes = smooth_amplitude(_interpolate(point_amplitudes, target_length), sample_rate)

    # Accumulating instantaneous frequency preserves phase across data points.
    phases = np.cumsum(frequencies) * (2 * np.pi / sample_rate)
    mono = _wave_from_phase(phases, waveform_type) * amplitudes

    fade_samples = min(int(sample_rate * config.EDGE_FADE_MS / 1000.0), target_length // 2)
    if fade_samples > 1:
        fade = np.linspace(0.0, 1.0, fade_samples)
        mono[:fade_samples] *= fade
        mono[-fade_samples:] *= fade[::-1]

    left_gain, right_gain = calculate_stereo_pan(target_length, start_progress, end_progress)
    stereo = np.column_stack((mono * left_gain, mono * right_gain))

    # Preserve the volume envelope. Only scale if a waveform exceeds safe headroom.
    peak = float(np.max(np.abs(stereo)))
    if peak > config.OUTPUT_HEADROOM:
        stereo *= config.OUTPUT_HEADROOM / peak
    pcm = np.int16(np.clip(stereo, -1.0, 1.0) * 32767)

    output = io.BytesIO()
    write(output, sample_rate, pcm)
    output.seek(0)
    return output
