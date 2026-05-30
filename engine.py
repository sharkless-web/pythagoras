import base64
import io
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np
from scipy import signal
from scipy.io.wavfile import write

import config


def _generate_beeps(data_values):
    """Create short beeps at local occurrences of the global max and min."""
    n = len(data_values)
    beep_signal = np.zeros(n)
    beep_length = int(0.1 * config.SAMPLE_RATE)

    min_val, max_val = np.min(data_values), np.max(data_values)
    if max_val == min_val:
        return beep_signal

    is_max = np.isclose(data_values, max_val, atol=1e-5)
    is_min = np.isclose(data_values, min_val, atol=1e-5)

    max_edges = np.where(np.diff(is_max.astype(int)) == 1)[0]
    min_edges = np.where(np.diff(is_min.astype(int)) == 1)[0]

    if len(is_max) > 0 and is_max[0]:
        max_edges = np.insert(max_edges, 0, 0)
    if len(is_min) > 0 and is_min[0]:
        min_edges = np.insert(min_edges, 0, 0)

    t = np.linspace(0, 0.1, beep_length, endpoint=False)
    envelope = np.exp(-t * 20)
    max_beep = np.sin(2 * np.pi * 3000 * t) * envelope * 1.5
    min_beep = np.sin(2 * np.pi * 500 * t) * envelope * 1.5

    for idx in max_edges:
        end_idx = min(idx + beep_length, n)
        beep_signal[idx:end_idx] += max_beep[: end_idx - idx]

    for idx in min_edges:
        end_idx = min(idx + beep_length, n)
        beep_signal[idx:end_idx] += min_beep[: end_idx - idx]

    return beep_signal


def _wave_from_phase(phases, waveform_type):
    w = str(waveform_type)
    if "square" in w:
        return signal.square(phases) * 0.25
    if "sawtooth" in w:
        return signal.sawtooth(phases) * 0.3
    if "triangle" in w:
        return signal.sawtooth(phases, width=0.5) * 0.5
    if "pulse" in w:
        return signal.square(phases, duty=0.2) * 0.3
    return np.sin(phases) * 0.6


# 1. Single-channel sonification engine

def generate_stereo_sound(data_values, user_max_f, waveform_type="sine"):
    pad_len = int(0.1 * config.SAMPLE_RATE)
    data_values = np.asarray(data_values, dtype=float)
    data_values = np.pad(data_values, (pad_len, pad_len), mode="edge")

    n = len(data_values)
    if n == 0:
        return None

    min_freq = config.DEFAULT_MIN_FREQ
    max_freq = float(user_max_f)
    min_val, max_val = np.min(data_values), np.max(data_values)

    if max_val == min_val:
        freqs = np.full(n, min_freq)
    else:
        freqs = min_freq + (max_freq - min_freq) * ((data_values - min_val) / (max_val - min_val + 1e-9))

    phases = np.cumsum(freqs) * (2 * np.pi / config.SAMPLE_RATE)
    wave = _wave_from_phase(phases, waveform_type)
    wave += _generate_beeps(data_values)

    pan_array = np.linspace(0.0, 1.0, n)
    left_channel = wave * np.cos(pan_array * np.pi / 2)
    right_channel = wave * np.sin(pan_array * np.pi / 2)

    audio_stereo = np.vstack((left_channel, right_channel)).T
    audio_stereo = np.int16(audio_stereo / (np.max(np.abs(audio_stereo)) + 1e-9) * 32767)

    vf = io.BytesIO()
    write(vf, config.SAMPLE_RATE, audio_stereo)
    vf.seek(0)
    return vf


# 2. Multi-channel mixing engine

def generate_mixed_sound(data_list, max_freq_list, waveform_list):
    if not data_list:
        return None

    pad_len = int(0.1 * config.SAMPLE_RATE)
    padded_data_list = [np.pad(np.asarray(data, dtype=float), (pad_len, pad_len), mode="edge") for data in data_list]

    n = len(padded_data_list[0])
    mixed_left = np.zeros(n)
    mixed_right = np.zeros(n)

    for data, max_f, wave_type in zip(padded_data_list, max_freq_list, waveform_list):
        min_freq = config.DEFAULT_MIN_FREQ
        max_freq = float(max_f)
        min_val, max_val = np.min(data), np.max(data)

        if max_val == min_val:
            freqs = np.full(n, min_freq)
        else:
            freqs = min_freq + (max_freq - min_freq) * ((data - min_val) / (max_val - min_val + 1e-9))

        phases = np.cumsum(freqs) * (2 * np.pi / config.SAMPLE_RATE)
        wave = _wave_from_phase(phases, wave_type)
        wave += _generate_beeps(data)

        pan_array = np.linspace(0.0, 1.0, n)
        mixed_left += wave * np.cos(pan_array * np.pi / 2)
        mixed_right += wave * np.sin(pan_array * np.pi / 2)

    audio_stereo = np.vstack((mixed_left, mixed_right)).T
    max_amp = np.max(np.abs(audio_stereo))

    if max_amp > 0:
        audio_stereo = np.int16((audio_stereo / max_amp) * 32767)
    else:
        audio_stereo = np.int16(audio_stereo)

    vf = io.BytesIO()
    write(vf, config.SAMPLE_RATE, audio_stereo)
    vf.seek(0)
    return vf


# 3. Graph-image extraction and accessibility analysis

def _crop_image(image: np.ndarray, crop: Optional[Dict[str, int]]) -> Tuple[np.ndarray, Dict[str, int]]:
    h, w = image.shape[:2]
    if not crop:
        return image, {"x": 0, "y": 0, "width": w, "height": h}

    x = max(0, min(int(crop.get("x", 0)), w - 1))
    y = max(0, min(int(crop.get("y", 0)), h - 1))
    width = max(1, min(int(crop.get("width", w)), w - x))
    height = max(1, min(int(crop.get("height", h)), h - y))
    return image[y : y + height, x : x + width], {"x": x, "y": y, "width": width, "height": height}


def _moving_average(values: np.ndarray, window: int = 7) -> np.ndarray:
    if len(values) < window:
        return values
    kernel = np.ones(window) / window
    return np.convolve(values, kernel, mode="same")




def _red_blue_masks(hsv: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    red_mask = (((hsv[:, :, 0] <= 10) | (hsv[:, :, 0] >= 170)) & (hsv[:, :, 1] > 70) & (hsv[:, :, 2] > 90))
    blue_mask = ((hsv[:, :, 0] >= 90) & (hsv[:, :, 0] <= 130) & (hsv[:, :, 1] > 60) & (hsv[:, :, 2] > 80))
    return red_mask.astype(np.uint8) * 255, blue_mask.astype(np.uint8) * 255


def _component_body_close(component_mask: np.ndarray, color: str) -> Optional[float]:
    row_counts = np.sum(component_mask > 0, axis=1)
    if row_counts.size == 0 or np.max(row_counts) == 0:
        return None

    dense_rows = np.where(row_counts >= max(3, np.max(row_counts) * 0.45))[0]
    if len(dense_rows) < 2:
        dense_rows = np.where(row_counts > 0)[0]
    if len(dense_rows) == 0:
        return None

    body_top = float(np.min(dense_rows))
    body_bottom = float(np.max(dense_rows))
    return body_top if color == "red" else body_bottom


def _estimate_price_panel_bounds(red_mask: np.ndarray, blue_mask: np.ndarray) -> Tuple[int, int]:
    h, w = red_mask.shape[:2]
    color_rows = np.sum((red_mask > 0) | (blue_mask > 0), axis=1)
    price_top = max(70, int(h * 0.12))
    price_bottom = int(h * 0.92)

    dense_threshold = max(80, int(w * 0.12))
    dense_rows = color_rows > dense_threshold
    search_start = int(h * 0.55)
    run_start = None
    for y in range(search_start, h):
        if dense_rows[y] and run_start is None:
            run_start = y
        elif not dense_rows[y] and run_start is not None:
            if y - run_start >= 18:
                price_bottom = max(price_top + 80, run_start - max(14, int(h * 0.03)))
                break
            run_start = None
    if run_start is not None and h - run_start >= 18:
        price_bottom = max(price_top + 80, run_start - max(14, int(h * 0.03)))

    return price_top, price_bottom



def _candles_from_color_columns(mask: np.ndarray, color: str, price_top: int, price_bottom: int, width_limit: int, color_scheme: str = "red_up_blue_down") -> List[Dict]:
    panel = mask.copy()
    panel[:price_top, :] = 0
    panel[price_bottom:, :] = 0
    col_counts = np.sum(panel > 0, axis=0)
    active_cols = col_counts >= 4

    candles = []
    x = 0
    while x < len(active_cols):
        if not active_cols[x]:
            x += 1
            continue
        start = x
        while x < len(active_cols) and active_cols[x]:
            x += 1
        end = x
        bw = end - start
        if bw < 3 or bw > width_limit:
            continue

        block = panel[:, start:end]
        row_counts = np.sum(block > 0, axis=1)
        max_row = int(np.max(row_counts)) if row_counts.size else 0
        if max_row < max(2, int(bw * 0.45)):
            continue

        dense_rows = np.where(row_counts >= max(2, int(max_row * 0.55)))[0]
        if len(dense_rows) < 3:
            continue

        body_top = int(np.min(dense_rows))
        body_bottom = int(np.max(dense_rows))
        body_height = body_bottom - body_top + 1
        if body_height < 3:
            continue

        close_y = _close_from_body(color, body_top, body_bottom, color_scheme)
        candles.append({
            "x": float((start + end - 1) / 2),
            "close_y": close_y,
            "color": color,
            "height": int(np.max(np.where(np.sum(block > 0, axis=1) > 0)[0]) - np.min(np.where(np.sum(block > 0, axis=1) > 0)[0]) + 1),
            "width": int(bw),
            "area": int(np.sum(block > 0)),
            "body_height": int(body_height),
            "body_width": int(max_row),
            "score": float(body_height * max_row),
        })
    return candles

def _extract_body_close_from_component(component_mask: np.ndarray, color: str) -> Optional[Tuple[float, int, int, int, int]]:
    row_counts = np.sum(component_mask > 0, axis=1)
    if row_counts.size == 0 or np.max(row_counts) == 0:
        return None

    max_width = int(np.max(row_counts))
    dense_threshold = max(7, int(max_width * 0.45))
    dense_rows = np.where(row_counts >= dense_threshold)[0]
    if len(dense_rows) < 4:
        return None

    body_top = int(np.min(dense_rows))
    body_bottom = int(np.max(dense_rows))
    body_height = body_bottom - body_top + 1
    if body_height < 4:
        return None

    close_y = float(body_top if color == "red" else body_bottom)
    return close_y, body_height, max_width, body_top, body_bottom



def _red_close_uses_top(color_scheme: str) -> bool:
    if color_scheme == "blue_up_red_down":
        return False
    return True


def _close_from_body(color: str, body_top: int, body_bottom: int, color_scheme: str) -> float:
    red_top = _red_close_uses_top(color_scheme)
    if color == "red":
        return float(body_top if red_top else body_bottom)
    return float(body_bottom if red_top else body_top)


def _candlestick_confidence(expected_count: int, selected_count: int, fallback_count: int, missing_count: int, outlier_count: int, volume_rejected: bool) -> Dict:
    if expected_count <= 0:
        return {"score": 0.0, "level": "low", "warnings": ["캔들 몸통을 충분히 찾지 못했습니다."]}
    selected_ratio = selected_count / expected_count
    fallback_ratio = fallback_count / expected_count
    missing_ratio = missing_count / expected_count
    outlier_ratio = outlier_count / expected_count
    score = 1.0
    score -= max(0.0, 1.0 - selected_ratio) * 0.45
    score -= fallback_ratio * 0.20
    score -= missing_ratio * 0.35
    score -= outlier_ratio * 0.25
    if volume_rejected:
        score -= 0.05
    score = float(np.clip(score, 0.0, 1.0))
    warnings = []
    if score < 0.68:
        warnings.append("분석 신뢰도가 낮습니다. 그래프의 가격 영역만 다시 선택하거나 캔들 색상 설정을 변경해 주세요.")
    if selected_count < max(6, expected_count * 0.45):
        warnings.append("캔들 몸통을 충분히 찾지 못했습니다.")
    if missing_ratio > 0.20:
        warnings.append("가격 차트 영역만 다시 드래그해 주세요.")
    if fallback_ratio > 0.25:
        warnings.append("거래량 영역이 포함되어 종가 추출이 불안정할 수 있습니다.")
    level = "high" if score >= 0.82 else "medium" if score >= 0.68 else "low"
    return {"score": score, "level": level, "warnings": warnings}

def _debug_candlestick_image(
    roi: np.ndarray,
    price_top: int,
    price_bottom: int,
    candidates: List[Dict],
    selected: List[Dict],
    fallback: List[Dict],
    missing_x: List[float],
    expected_x: np.ndarray,
    extended_x: set,
    final_x: np.ndarray,
    final_y: np.ndarray,
) -> str:
    debug = roi.copy()
    cv2.rectangle(debug, (0, price_top), (roi.shape[1] - 1, price_bottom), (80, 160, 80), 2)

    for x in expected_x:
        xi = int(round(x))
        if any(abs(x - ex) < 0.5 for ex in extended_x):
            for y in range(price_top, price_bottom, 10):
                cv2.line(debug, (xi, y), (xi, min(y + 5, price_bottom)), (190, 190, 190), 1)
        else:
            cv2.line(debug, (xi, price_top), (xi, price_bottom), (210, 210, 210), 1)

    selected_ids = {id(item) for item in selected} | {id(item) for item in fallback}
    for item in candidates:
        if id(item) in selected_ids:
            continue
        x = int(round(item["x"]))
        y = int(round(item["close_y"]))
        cv2.circle(debug, (x, y), 3, (160, 160, 160), -1)

    for item in selected:
        x = int(round(item["x"]))
        y = int(round(item["close_y"]))
        cv2.circle(debug, (x, y), 5, (0, 180, 0), -1)

    for item in fallback:
        x = int(round(item["x"]))
        y = int(round(item["close_y"]))
        cv2.circle(debug, (x, y), 5, (0, 220, 220), -1)

    for x in missing_x:
        xi = int(round(x))
        yi = int((price_top + price_bottom) / 2)
        cv2.line(debug, (xi - 5, yi - 5), (xi + 5, yi + 5), (0, 0, 255), 2)
        cv2.line(debug, (xi + 5, yi - 5), (xi - 5, yi + 5), (0, 0, 255), 2)

    if len(final_x) > 1:
        pts = np.array([[int(round(x)), int(round(y))] for x, y in zip(final_x, final_y)], dtype=np.int32)
        cv2.polylines(debug, [pts], False, (0, 0, 220), 3)

    ok, buffer = cv2.imencode(".png", debug)
    if not ok:
        return ""
    encoded = base64.b64encode(buffer).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def _candidate_body_from_component(
    labels: np.ndarray,
    stats: np.ndarray,
    idx: int,
    color: str,
    price_top: int,
    price_bottom: int,
    relaxed: bool = False,
    color_scheme: str = "red_up_blue_down",
) -> Optional[Dict]:
    x, y, bw, bh, area = [int(v) for v in stats[idx]]
    if y + bh < price_top or y > price_bottom:
        return None
    if area < 14 or bw < 2 or bh < 3:
        return None
    if bw > 64:
        return None
    if bw / max(1, bh) > 5 and bh <= 10:
        return None

    component_mask = (labels[y : y + bh, x : x + bw] == idx).astype(np.uint8)
    row_counts = np.sum(component_mask > 0, axis=1)
    if row_counts.size == 0 or np.max(row_counts) == 0:
        return None

    max_row_count = int(np.max(row_counts))
    density_ratio = 0.52 if relaxed else 0.60
    min_body_height = 3
    min_body_width = 3 if relaxed else 4
    body_rows = np.where(row_counts >= max(2, int(max_row_count * density_ratio)))[0]
    if len(body_rows) < min_body_height:
        return None

    body_top = int(np.min(body_rows))
    body_bottom = int(np.max(body_rows))
    body_height = body_bottom - body_top + 1
    if body_height < min_body_height:
        return None

    body_global_top = y + body_top
    body_global_bottom = y + body_bottom
    if body_global_bottom < price_top or body_global_top > price_bottom:
        return None

    close_y = _close_from_body(color, body_global_top, body_global_bottom, color_scheme)
    close_local_y = int(round(close_y - y))
    close_band_top = max(0, close_local_y - 1)
    close_band_bottom = min(component_mask.shape[0], close_local_y + 2)
    close_band_pixels = int(np.sum(component_mask[close_band_top:close_band_bottom, :] > 0))
    if close_band_pixels < max(2, int(max_row_count * 0.40)):
        return None

    body_area = int(np.sum(component_mask[body_top : body_bottom + 1, :] > 0))
    body_width = max_row_count
    if body_width < min_body_width:
        return None
    rectangularity = body_area / max(1, body_width * body_height)
    if rectangularity < (0.40 if relaxed else 0.45):
        return None

    long_thin_penalty = 0.0
    if bw / max(1, bh) > 2.8:
        long_thin_penalty += 40.0
    if bh / max(1, bw) > 12.0 and body_width <= 3:
        long_thin_penalty += 35.0
    score = float(body_area * 1.0 + body_width * body_height * 1.5 + rectangularity * 50.0 - long_thin_penalty)

    return {
        "x": float(x + bw / 2),
        "close_y": close_y,
        "color": color,
        "width": bw,
        "height": bh,
        "area": area,
        "body_area": body_area,
        "body_top": body_global_top,
        "body_bottom": body_global_bottom,
        "body_height": body_height,
        "body_width": body_width,
        "rectangularity": rectangularity,
        "close_band_pixels": close_band_pixels,
        "score": score,
        "relaxed": relaxed,
    }


def _select_candidates_by_expected_slots(candidates: List[Dict], left_margin: float = 0.0) -> Tuple[np.ndarray, np.ndarray, List[Optional[Dict]], List[Dict], float, set]:
    ordered = sorted(candidates, key=lambda item: item["x"])
    if len(ordered) < 6:
        return np.array([], dtype=float), np.array([], dtype=float), [], [], 1.0, set()

    scores = np.array([item["score"] for item in ordered], dtype=float)
    score_floor = float(np.percentile(scores, 45))
    strong_x = []
    for item in ordered:
        if item["score"] < score_floor or item.get("body_width", 0) < 8:
            continue
        if not strong_x or abs(item["x"] - strong_x[-1]) >= 4:
            strong_x.append(item["x"])

    if len(strong_x) < 6:
        strong_x = []
        for item in ordered:
            if not strong_x or abs(item["x"] - strong_x[-1]) >= 4:
                strong_x.append(item["x"])

    gaps = np.diff(np.array(strong_x, dtype=float))
    if len(gaps) == 0:
        return np.array([], dtype=float), np.array([], dtype=float), [], [], 1.0, set()
    gaps = gaps[(gaps >= 5) & (gaps <= np.percentile(gaps, 80) * 1.5)]
    median_gap = float(np.median(gaps)) if len(gaps) else float(np.median(np.diff(strong_x)))
    median_gap = max(4.0, median_gap)

    first_x = min(item["x"] for item in ordered)
    max_x = max(item["x"] for item in ordered)
    grid_start = first_x
    while grid_start - median_gap >= left_margin:
        grid_start -= median_gap

    anchors = [grid_start]
    anchors.extend([grid_start + offset * median_gap / 4 for offset in range(1, 4)])
    anchors.extend([item["x"] - np.floor((item["x"] - grid_start) / median_gap) * median_gap for item in ordered if item["score"] >= score_floor][:8])

    best_grid = None
    best_matches: List[Optional[Dict]] = []
    best_value = -1e18
    for start in anchors:
        while start - median_gap >= left_margin:
            start -= median_gap
        expected_x = np.arange(start, max_x + median_gap * 0.6, median_gap)
        expected_x = expected_x[expected_x >= left_margin]
        if len(expected_x) < 6:
            continue

        matches: List[Optional[Dict]] = []
        total = 0.0
        count = 0
        for slot_index, slot_x in enumerate(expected_x):
            radius = max(3.0, median_gap * (0.55 if slot_index < 5 else 0.35))
            near = [item for item in ordered if abs(item["x"] - slot_x) <= radius]
            if not near:
                matches.append(None)
                total -= 20.0
                continue
            best = max(
                near,
                key=lambda item: item["score"]
                - abs(item["x"] - slot_x) * 1.25
                + item.get("rectangularity", 0.0) * 20.0
                + min(item.get("body_width", 0), item.get("body_height", 0)) * 0.5,
            )
            matches.append(best)
            total += best["score"] - abs(best["x"] - slot_x) * 1.25
            count += 1

        early_count = sum(1 for item in matches[:5] if item is not None)
        value = total + count * 80.0 + early_count * 45.0 - abs(len(expected_x) - count) * 25.0
        if value > best_value:
            best_value = value
            best_grid = expected_x
            best_matches = matches

    if best_grid is None:
        return np.array([], dtype=float), np.array([], dtype=float), [], [], median_gap, set()

    y_values = np.array([np.nan if item is None else item["close_y"] for item in best_matches], dtype=float)
    selected = [item for item in best_matches if item is not None]
    extended_x = {float(x) for x in best_grid if x < first_x - median_gap * 0.25}
    return best_grid, y_values, best_matches, selected, median_gap, extended_x


def _fallback_candidate_near_slot(red_mask: np.ndarray, blue_mask: np.ndarray, slot_x: float, median_gap: float, price_top: int, price_bottom: int, color_scheme: str = "red_up_blue_down") -> Optional[Dict]:
    h, w = red_mask.shape[:2]
    radius = max(3, int(round(median_gap * 0.45)))
    x0 = max(0, int(round(slot_x)) - radius)
    x1 = min(w, int(round(slot_x)) + radius + 1)
    best = None

    for color, mask in (("red", red_mask), ("blue", blue_mask)):
        roi = mask[price_top:price_bottom, x0:x1]
        if roi.size == 0:
            continue
        col_counts = np.sum(roi > 0, axis=0)
        active = np.where(col_counts >= 2)[0]
        if len(active) < 2:
            continue
        start = int(np.min(active))
        end = int(np.max(active)) + 1
        if end - start < 2:
            continue
        block = roi[:, start:end]
        row_counts = np.sum(block > 0, axis=1)
        if row_counts.size == 0 or np.max(row_counts) == 0:
            continue
        max_row = int(np.max(row_counts))
        dense_rows = np.where(row_counts >= max(2, int(max_row * 0.52)))[0]
        if len(dense_rows) < 3:
            continue
        body_top = int(np.min(dense_rows))
        body_bottom = int(np.max(dense_rows))
        body_height = body_bottom - body_top + 1
        body_area = int(np.sum(block[body_top : body_bottom + 1, :] > 0))
        rectangularity = body_area / max(1, max_row * body_height)
        if rectangularity < 0.35:
            continue
        close_y = _close_from_body(color, price_top + body_top, price_top + body_bottom, color_scheme)
        body_width = max_row
        if body_width < 2:
            continue
        score = float(body_area + body_width * body_height * 1.2 + rectangularity * 40.0 - abs((x0 + start + end / 2) - slot_x) * 1.4)
        item = {
            "x": float(x0 + (start + end - 1) / 2),
            "close_y": close_y,
            "color": color,
            "width": int(end - start),
            "height": int(body_height),
            "area": int(np.sum(block > 0)),
            "body_area": body_area,
            "body_top": int(price_top + body_top),
            "body_bottom": int(price_top + body_bottom),
            "body_height": int(body_height),
            "body_width": int(body_width),
            "rectangularity": float(rectangularity),
            "close_band_pixels": int(max_row),
            "score": score,
            "fallback": True,
        }
        if best is None or item["score"] > best["score"]:
            best = item
    return best


def _fill_missing_with_extrapolation(expected_x: np.ndarray, y_values: np.ndarray, price_top: int, price_bottom: int) -> Tuple[np.ndarray, List[float]]:
    filled = y_values.astype(float).copy()
    valid = np.isfinite(filled)
    missing_x = [float(x) for x, ok in zip(expected_x, valid) if not ok]
    if np.sum(valid) == 0:
        return filled, missing_x

    valid_indices = np.where(valid)[0]
    if len(valid_indices) >= 2:
        first = valid_indices[0]
        second = valid_indices[1]
        slope = (filled[second] - filled[first]) / max(1.0, expected_x[second] - expected_x[first])
        for idx in range(first - 1, -1, -1):
            filled[idx] = np.clip(filled[idx + 1] - slope * (expected_x[idx + 1] - expected_x[idx]), price_top, price_bottom)

        last = valid_indices[-1]
        prev = valid_indices[-2]
        slope = (filled[last] - filled[prev]) / max(1.0, expected_x[last] - expected_x[prev])
        for idx in range(last + 1, len(filled)):
            filled[idx] = np.clip(filled[idx - 1] + slope * (expected_x[idx] - expected_x[idx - 1]), price_top, price_bottom)

    valid = np.isfinite(filled)
    if np.any(~valid) and np.sum(valid) >= 2:
        filled[~valid] = np.interp(expected_x[~valid], expected_x[valid], filled[valid])
    elif np.any(~valid):
        filled[~valid] = filled[valid][0]
    filled = np.clip(filled, price_top, price_bottom)
    return filled, missing_x

def _remove_local_mad_outliers(values: np.ndarray, window: int = 3) -> np.ndarray:
    cleaned = values.astype(float).copy()
    if len(cleaned) < 9:
        return cleaned

    original = cleaned.copy()
    for idx in range(1, len(cleaned) - 1):
        left = max(0, idx - window)
        right = min(len(cleaned), idx + window + 1)
        local = np.delete(original[left:right], idx - left)
        if len(local) < 3:
            continue
        median = float(np.median(local))
        mad = float(np.median(np.abs(local - median)))
        threshold = max(18.0, 3.2 * 1.4826 * mad)
        prev_is_local = abs(original[idx - 1] - median) <= threshold
        next_is_local = abs(original[idx + 1] - median) <= threshold
        if abs(original[idx] - median) > threshold and prev_is_local and next_is_local:
            cleaned[idx] = median
    return cleaned


def _stabilize_candlestick_edges(values: np.ndarray, price_top: int, price_bottom: int) -> np.ndarray:
    cleaned = values.astype(float).copy()
    if len(cleaned) < 6:
        return cleaned

    panel_height = max(1, price_bottom - price_top)
    low_band = price_top + panel_height * 0.88
    high_band = price_top + panel_height * 0.12

    def replace_edge(idx: int, neighbors: np.ndarray) -> None:
        local = neighbors[np.isfinite(neighbors)]
        if len(local) < 3:
            return
        median = float(np.median(local))
        mad = float(np.median(np.abs(local - median)))
        threshold = max(panel_height * 0.18, 3.2 * 1.4826 * mad)
        if abs(cleaned[idx] - median) <= threshold:
            return
        if idx == len(cleaned) - 1 and cleaned[idx] >= low_band and median < price_top + panel_height * 0.78:
            cleaned[idx] = median
        elif idx == 0 and cleaned[idx] <= high_band and median > price_top + panel_height * 0.22:
            cleaned[idx] = median

    replace_edge(len(cleaned) - 1, cleaned[-6:-1])
    replace_edge(0, cleaned[1:6])
    return cleaned
def _extract_candlestick_timeseries(roi: np.ndarray, crop_info: Dict[str, int], sample_count: int, color_scheme: str = "red_up_blue_down") -> Optional[Dict]:
    h, w = roi.shape[:2]
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    raw_red_mask, raw_blue_mask = _red_blue_masks(hsv)
    price_top, price_bottom = _estimate_price_panel_bounds(raw_red_mask, raw_blue_mask)

    red_mask = raw_red_mask.copy()
    blue_mask = raw_blue_mask.copy()
    red_mask[:price_top, :] = 0
    red_mask[price_bottom:, :] = 0
    blue_mask[:price_top, :] = 0
    blue_mask[price_bottom:, :] = 0

    kernel = np.ones((2, 2), np.uint8)
    red_mask = cv2.morphologyEx(red_mask, cv2.MORPH_OPEN, kernel)
    red_mask = cv2.morphologyEx(red_mask, cv2.MORPH_CLOSE, kernel)
    blue_mask = cv2.morphologyEx(blue_mask, cv2.MORPH_OPEN, kernel)
    blue_mask = cv2.morphologyEx(blue_mask, cv2.MORPH_CLOSE, kernel)

    candidates: List[Dict] = []
    for color, mask in (("red", red_mask), ("blue", blue_mask)):
        count, labels, stats, _ = cv2.connectedComponentsWithStats(mask, 8)
        for idx in range(1, count):
            candidate = _candidate_body_from_component(labels, stats, idx, color, price_top, price_bottom, color_scheme=color_scheme)
            if candidate is not None:
                candidates.append(candidate)

    if len(candidates) < 6:
        return None

    expected_x, close_y, matched_slots, selected, median_gap, extended_x = _select_candidates_by_expected_slots(candidates, left_margin=0.0)
    if len(expected_x) < 6:
        return None

    fallback_recovered: List[Dict] = []
    for idx, item in enumerate(matched_slots):
        if item is not None:
            continue
        fallback = _fallback_candidate_near_slot(red_mask, blue_mask, expected_x[idx], median_gap, price_top, price_bottom, color_scheme)
        if fallback is not None:
            matched_slots[idx] = fallback
            close_y[idx] = fallback["close_y"]
            fallback_recovered.append(fallback)

    missing_before_fill = [float(x) for x, y in zip(expected_x, close_y) if not np.isfinite(y)]
    close_y, missing_x = _fill_missing_with_extrapolation(expected_x, close_y, price_top, price_bottom)
    before_outlier = close_y.copy()
    close_y = _remove_local_mad_outliers(close_y)
    outlier_corrections = int(np.sum(np.abs(close_y - before_outlier) > 1e-6))
    sample_x = np.linspace(float(expected_x[0]), float(expected_x[-1]), sample_count)
    sample_y = np.interp(sample_x, expected_x, close_y)

    normalized = 1.0 - ((sample_y - price_top) / max(1, price_bottom - price_top))
    normalized = np.clip(normalized, 0.0, 1.0)

    points = [
        {
            "x": float((x - expected_x[0]) / max(1.0, expected_x[-1] - expected_x[0])),
            "y": float(value),
            "pixel_x": int(round(x)) + crop_info["x"],
            "pixel_y": int(round(y)) + crop_info["y"],
        }
        for x, y, value in zip(sample_x, sample_y, normalized)
    ]

    analysis = analyze_timeseries(normalized.tolist())
    analysis["descriptions"].insert(0, "\uc8fc\uc2dd \uce94\ub4e4 \ucc28\ud2b8\ub85c \uc778\uc2dd\ud558\uc5ec \uac01 \uce94\ub4e4\uc758 \uc885\uac00 \ud750\ub984\uc744 \uae30\uc900\uc73c\ub85c \ubd84\uc11d\ud588\uc2b5\ub2c8\ub2e4.")
    confidence = _candlestick_confidence(
        int(len(expected_x)),
        int(len(selected)),
        int(len(fallback_recovered)),
        int(len(missing_before_fill) - len(fallback_recovered)),
        outlier_corrections,
        bool(price_bottom < int(h * 0.88)),
    )
    for warning in confidence["warnings"]:
        if warning not in analysis["descriptions"]:
            analysis["descriptions"].append(warning)
    analysis["summary"] = " ".join(analysis["descriptions"])
    debug_image = _debug_candlestick_image(roi, price_top, price_bottom, candidates, selected, fallback_recovered, missing_before_fill, expected_x, extended_x, sample_x, sample_y)

    return {
        "data": normalized.tolist(),
        "points": points,
        "crop": crop_info,
        "analysis": analysis,
        "chart_type": "candlestick",
        "candles_detected": len(selected) + len(fallback_recovered),
        "expected_candles": int(len(expected_x)),
        "selected_candles": int(len(selected)),
        "fallback_recovered": int(len(fallback_recovered)),
        "missing_candles": int(len(missing_before_fill) - len(fallback_recovered)),
        "confidence": confidence,
        "outlier_corrections": outlier_corrections,
        "color_scheme": color_scheme,
        "candidate_count": len(candidates),
        "median_gap": median_gap,
        "price_panel": {"top": int(price_top), "bottom": int(price_bottom)},
        "debug_image": debug_image,
    }

def extract_timeseries_from_image(image_bytes: bytes, crop: Optional[Dict[str, int]] = None, sample_count: int = 96, chart_type: str = "auto", color_scheme: str = "red_up_blue_down") -> Dict:
    np_buffer = np.frombuffer(image_bytes, np.uint8)
    image = cv2.imdecode(np_buffer, cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError("\uc774\ubbf8\uc9c0\ub97c \uc77d\uc744 \uc218 \uc5c6\uc2b5\ub2c8\ub2e4.")

    roi, crop_info = _crop_image(image, crop)
    h, w = roi.shape[:2]
    if h < 10 or w < 10:
        raise ValueError("\uc120\ud0dd\ud55c \uadf8\ub798\ud504 \uc601\uc5ed\uc774 \ub108\ubb34 \uc791\uc2b5\ub2c8\ub2e4.")

    chart_type = (chart_type or "auto").lower()
    color_scheme = color_scheme or "red_up_blue_down"
    if chart_type in ("auto", "candlestick"):
        if color_scheme == "auto":
            results = [
                _extract_candlestick_timeseries(roi, crop_info, sample_count, color_scheme="red_up_blue_down"),
                _extract_candlestick_timeseries(roi, crop_info, sample_count, color_scheme="blue_up_red_down"),
            ]
            results = [result for result in results if result is not None]
            candlestick_result = max(results, key=lambda result: result.get("confidence", {}).get("score", 0.0)) if results else None
            if candlestick_result is not None:
                candlestick_result["color_scheme"] = "auto"
        else:
            candlestick_result = _extract_candlestick_timeseries(roi, crop_info, sample_count, color_scheme=color_scheme)
        if candlestick_result is not None:
            return candlestick_result
        if chart_type == "candlestick":
            raise ValueError("캔들 몸통을 충분히 찾지 못했습니다. 가격 차트 영역만 다시 드래그하거나 캔들 색상 설정을 변경해 주세요.")

    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    saturation = hsv[:, :, 1]
    value = hsv[:, :, 2]

    dark_mask = gray < 190
    color_mask = (saturation > 45) & (value < 245)
    line_mask = (dark_mask | color_mask).astype(np.uint8) * 255

    kernel = np.ones((2, 2), np.uint8)
    line_mask = cv2.morphologyEx(line_mask, cv2.MORPH_OPEN, kernel)
    line_mask = cv2.morphologyEx(line_mask, cv2.MORPH_CLOSE, kernel)

    xs: List[int] = []
    ys: List[float] = []
    previous_y: Optional[float] = None

    for x in range(w):
        y_candidates = np.where(line_mask[:, x] > 0)[0]
        if len(y_candidates) == 0 or len(y_candidates) > h * 0.55:
            continue

        if previous_y is None:
            y = float(np.median(y_candidates))
        else:
            y = float(y_candidates[np.argmin(np.abs(y_candidates - previous_y))])

        xs.append(x)
        ys.append(y)
        previous_y = y

    if len(xs) < max(8, sample_count // 8):
        raise ValueError("\uadf8\ub798\ud504 \uc120\uc744 \ucda9\ubd84\ud788 \ucd94\ucd9c\ud558\uc9c0 \ubabb\ud588\uc2b5\ub2c8\ub2e4. \uadf8\ub798\ud504 \uc601\uc5ed\uc744 \uc120 \uc911\uc2ec\uc73c\ub85c \ub2e4\uc2dc \uc120\ud0dd\ud574 \uc8fc\uc138\uc694.")

    full_x = np.arange(w)
    interpolated_y = np.interp(full_x, np.array(xs), np.array(ys))
    smoothed_y = _moving_average(interpolated_y, window=max(5, w // 80))

    sample_x = np.linspace(0, w - 1, sample_count)
    sample_y = np.interp(sample_x, full_x, smoothed_y)
    normalized = 1.0 - (sample_y / max(1, h - 1))
    normalized = np.clip(normalized, 0.0, 1.0)

    points = [
        {
            "x": float(x / max(1, w - 1)),
            "y": float(value),
            "pixel_x": int(round(x)) + crop_info["x"],
            "pixel_y": int(round(y)) + crop_info["y"],
        }
        for x, y, value in zip(sample_x, sample_y, normalized)
    ]

    analysis = analyze_timeseries(normalized.tolist())
    return {
        "data": normalized.tolist(),
        "points": points,
        "crop": crop_info,
        "analysis": analysis,
        "chart_type": "line",
        "confidence": {"score": 0.85, "level": "medium", "warnings": []},
    }

def _position_label(index: int, length: int) -> str:
    ratio = index / max(1, length - 1)
    if ratio < 0.33:
        return "\ucd08\ubc18\ubd80"
    if ratio < 0.66:
        return "\uc911\uac04\ubd80"
    return "\ud6c4\ubc18\ubd80"


def analyze_timeseries(values: List[float]) -> Dict:
    data = np.asarray(values, dtype=float)
    n = len(data)
    if n < 3:
        return {"summary": "\ubd84\uc11d\ud560 \ub370\uc774\ud130\uac00 \ucda9\ubd84\ud558\uc9c0 \uc54a\uc2b5\ub2c8\ub2e4.", "descriptions": ["\uadf8\ub798\ud504 \uc120 \ub370\uc774\ud130\uac00 \ub108\ubb34 \uc9e7\uc2b5\ub2c8\ub2e4."]}

    start_mean = float(np.mean(data[: max(2, n // 10)]))
    end_mean = float(np.mean(data[-max(2, n // 10) :]))
    total_change = end_mean - start_mean
    first_slope = float(np.mean(np.diff(data[: n // 2]))) if n >= 4 else 0.0
    second_slope = float(np.mean(np.diff(data[n // 2 :]))) if n >= 4 else 0.0
    diffs = np.diff(data)
    abs_diffs = np.abs(diffs)

    max_index = int(np.argmax(data))
    min_index = int(np.argmin(data))
    volatility = float(np.std(diffs))
    abrupt_threshold = max(0.12, float(np.mean(abs_diffs) + 2.0 * np.std(abs_diffs)))
    abrupt_indices = np.where(abs_diffs >= abrupt_threshold)[0]

    descriptions: List[str] = []
    if total_change > 0.12:
        trend = "\uc0c1\uc2b9"
        descriptions.append("\uadf8\ub798\ud504\ub294 \uc804\uccb4\uc801\uc73c\ub85c \uc0c1\uc2b9 \ucd94\uc138\ub97c \ubcf4\uc785\ub2c8\ub2e4.")
    elif total_change < -0.12:
        trend = "\ud558\ub77d"
        descriptions.append("\uadf8\ub798\ud504\ub294 \uc804\uccb4\uc801\uc73c\ub85c \ud558\ub77d \ucd94\uc138\ub97c \ubcf4\uc785\ub2c8\ub2e4.")
    else:
        trend = "\uc644\ub9cc"
        descriptions.append("\uadf8\ub798\ud504\ub294 \uc2dc\uc791\uacfc \ub05d\uc758 \ucc28\uc774\uac00 \ud06c\uc9c0 \uc54a\uc544 \uc804\uccb4\uc801\uc73c\ub85c \uc644\ub9cc\ud55c \ud750\ub984\uc744 \ubcf4\uc785\ub2c8\ub2e4.")

    if first_slope > 0.004 and second_slope < -0.004:
        descriptions.append("\ucd08\ubc18\uc5d0\ub294 \uc0c1\uc2b9\ud558\ub2e4\uac00 \ud6c4\ubc18\uc5d0\ub294 \ud558\ub77d\ud558\ub294 \uc804\ud658 \ud750\ub984\uc774 \uac10\uc9c0\ub429\ub2c8\ub2e4.")
    elif first_slope < -0.004 and second_slope > 0.004:
        descriptions.append("\ucd08\ubc18\uc5d0\ub294 \ud558\ub77d\ud558\ub2e4\uac00 \ud6c4\ubc18\uc5d0\ub294 \ub2e4\uc2dc \uc0c1\uc2b9\ud558\ub294 \ud68c\ubcf5 \ud750\ub984\uc774 \uac10\uc9c0\ub429\ub2c8\ub2e4.")

    descriptions.append(f"\ucd5c\uace0\uc810\uc740 \uadf8\ub798\ud504 {_position_label(max_index, n)}\uc5d0 \uc704\uce58\ud569\ub2c8\ub2e4.")
    descriptions.append(f"\ucd5c\uc800\uc810\uc740 \uadf8\ub798\ud504 {_position_label(min_index, n)}\uc5d0 \uc704\uce58\ud569\ub2c8\ub2e4.")

    if len(abrupt_indices) > 0:
        main_idx = int(abrupt_indices[np.argmax(abs_diffs[abrupt_indices])])
        direction = "\uc0c1\uc2b9" if diffs[main_idx] > 0 else "\ud558\ub77d"
        descriptions.append(f"{_position_label(main_idx, n)}\uc5d0\uc11c \ud070 \ud3ed\uc758 {direction} \ubcc0\ud654\uac00 \uac10\uc9c0\ub418\uc5c8\uc2b5\ub2c8\ub2e4.")

    if volatility > 0.045:
        descriptions.append("\ubcc0\ub3d9\uc131\uc774 \ud070 \ub370\uc774\ud130\uc785\ub2c8\ub2e4.")
    else:
        descriptions.append("\ubcc0\ub3d9\uc131\uc774 \ube44\uad50\uc801 \uc791\uc544 \ud750\ub984\uc774 \uc548\uc815\uc801\uc778 \ud3b8\uc785\ub2c8\ub2e4.")

    return {
        "summary": " ".join(descriptions),
        "descriptions": descriptions,
        "trend": trend,
        "max_position": _position_label(max_index, n),
        "min_position": _position_label(min_index, n),
        "volatility": volatility,
        "total_change": total_change,
    }
