# engine.py
import numpy as np
import cv2
import io
from scipy.io.wavfile import write
import config

def generate_stereo_sound(data_values, user_max_f):
    total_steps = len(data_values)
    if total_steps == 0: return None, None
    
    duration = config.TOTAL_PLAY_TIME / total_steps 
    min_freq = config.DEFAULT_MIN_FREQ
    max_freq = float(user_max_f)

    left_channel, right_channel = [], []
    current_phase = 0.0 
    N = int(config.SAMPLE_RATE * duration)
    total_samples = total_steps * N
    min_val, max_val = np.min(data_values), np.max(data_values)

    for i, value in enumerate(data_values):
        freq = min_freq if max_val == min_val else min_freq + (max_freq - min_freq) * ((value - min_val) / (max_val - min_val + 1e-9))
        t = np.linspace(0, duration, N, False)
        wave = np.sin(current_phase + freq * t * 2 * np.pi) 
        current_phase = (current_phase + freq * duration * 2 * np.pi) % (2 * np.pi)
        
        pan_array = np.linspace(i*N / total_samples, (i+1)*N / total_samples, N, False)
        pan_array = np.clip(pan_array, 0.0, 1.0)
        
        left_channel.extend(wave * np.cos(pan_array * np.pi / 2))
        right_channel.extend(wave * np.sin(pan_array * np.pi / 2))

    audio_stereo = np.vstack((left_channel, right_channel)).T
    audio_stereo = np.int16(audio_stereo / (np.max(np.abs(audio_stereo)) + 1e-9) * 32767)
    
    vf = io.BytesIO()
    write(vf, config.SAMPLE_RATE, audio_stereo)
    return vf

def extract_color_line(opencv_img):
    hsv = cv2.cvtColor(opencv_img, cv2.COLOR_RGB2HSV)
    mask = cv2.inRange(hsv, np.array(config.LOWER_COLOR), np.array(config.UPPER_COLOR))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3,3), np.uint8), iterations=1)
    
    h, w = mask.shape
    raw_x, raw_y = [], []
    for x in range(w):
        y_ids = np.where(mask[:, x] == 255)[0]
        if len(y_ids) > 0:
            raw_x.append(x); raw_y.append(h - np.mean(y_ids))
            
    if not raw_x: return np.zeros(w), opencv_img
        
    curve = np.array([[[x, y]] for x, y in zip(raw_x, raw_y)], dtype=np.float32)
    approx = cv2.approxPolyDP(curve, 0.005 * cv2.arcLength(curve, False), False)
    key_x, key_y = [pt[0][0] for pt in approx], [pt[0][1] for pt in approx]
    data = np.interp(np.arange(w), key_x, key_y)
    
    dbg_img = cv2.cvtColor(mask, cv2.COLOR_GRAY2RGB)
    for i in range(len(key_x) - 1):
        cv2.line(dbg_img, (int(key_x[i]), int(h-key_y[i])), (int(key_x[i+1]), int(h-key_y[i+1])), (0, 255, 0), 2)
    return data, dbg_img