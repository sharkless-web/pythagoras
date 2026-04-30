import numpy as np
import cv2
import io
from scipy.io.wavfile import write
from scipy import signal
import config

def _generate_beeps(data_values):
    """
    [핵심 기능] 데이터의 '실제' 최댓값 또는 최솟값에 도달하는 순간을 포착하여 
    짧고 명확한 타격음(Beep) 파형을 생성합니다.
    """
    N = len(data_values)
    beep_signal = np.zeros(N)
    beep_length = int(0.1 * config.SAMPLE_RATE) # 0.1초 타격음
    
    # [수정 1] 절대값(0.99, 0.01)이 아닌 데이터의 실제 최소/최대값을 동적으로 추출
    min_val, max_val = np.min(data_values), np.max(data_values)
    
    # 데이터가 아예 평탄하면 타격음을 내지 않음
    if max_val == min_val:
        return beep_signal
        
    # 부동소수점 오차를 무시하고 정확히 일치하는 지점 찾기
    is_max = np.isclose(data_values, max_val, atol=1e-5)
    is_min = np.isclose(data_values, min_val, atol=1e-5)
    
    max_edges = np.where(np.diff(is_max.astype(int)) == 1)[0]
    min_edges = np.where(np.diff(is_min.astype(int)) == 1)[0]
    
    if len(is_max) > 0 and is_max[0]: max_edges = np.insert(max_edges, 0, 0)
    if len(is_min) > 0 and is_min[0]: min_edges = np.insert(min_edges, 0, 0)
    
    t = np.linspace(0, 0.1, beep_length, endpoint=False)
    envelope = np.exp(-t * 40) 
    
    # 최고점은 3000Hz(맑은 핑!), 최저점은 500Hz(묵직한 퉁!)
    max_beep = np.sin(2 * np.pi * 3000 * t) * envelope * 0.8
    min_beep = np.sin(2 * np.pi * 500 * t) * envelope * 0.8
    
    for idx in max_edges:
        end_idx = min(idx + beep_length, N)
        beep_signal[idx:end_idx] += max_beep[:end_idx-idx]
        
    for idx in min_edges:
        end_idx = min(idx + beep_length, N)
        beep_signal[idx:end_idx] += min_beep[:end_idx-idx]
        
    return beep_signal

# ==========================================
# 1. 단일 채널 사운드 엔진
# ==========================================

def generate_stereo_sound(data_values, user_max_f, waveform_type="sine"):
    # [수정 3] 소리 잘림 방지: 앞뒤로 0.1초 여백(Padding) 추가 (값은 유지)
    print(f"!!! 현재 수신된 음색 파라미터: {waveform_type} !!!") 
    pad_len = int(0.1 * config.SAMPLE_RATE)
    data_values = np.pad(data_values, (pad_len, pad_len), mode='edge')
    
    N = len(data_values)
    if N == 0: return None
    
    min_freq = config.DEFAULT_MIN_FREQ
    max_freq = float(user_max_f)
    min_val, max_val = np.min(data_values), np.max(data_values)
    
    if max_val == min_val:
        freqs = np.full(N, min_freq)
    else:
        freqs = min_freq + (max_freq - min_freq) * ((data_values - min_val) / (max_val - min_val + 1e-9))
        
    phases = np.cumsum(freqs) * (2 * np.pi / config.SAMPLE_RATE)
    
    # [수정 2] 원하시던 직관적인 뚜, 삐, 브 음색 적용 (순수 파형)
    if waveform_type == "square":
        wave = signal.square(phases) * 0.8       # '삐' 소리 (8비트 게임 느낌)
    elif waveform_type == "sawtooth":
        wave = signal.sawtooth(phases) * 0.8     # '브' 소리 (거친 기계음 느낌)
    else:
        wave = np.sin(phases) * 0.8              # '뚜' 소리 (부드러운 기본음)
        
    wave += _generate_beeps(data_values)
    
    pan_array = np.linspace(0.0, 1.0, N)
    left_channel = wave * np.cos(pan_array * np.pi / 2)
    right_channel = wave * np.sin(pan_array * np.pi / 2)

    audio_stereo = np.vstack((left_channel, right_channel)).T
    audio_stereo = np.int16(audio_stereo / (np.max(np.abs(audio_stereo)) + 1e-9) * 32767)
    
    vf = io.BytesIO()
    write(vf, config.SAMPLE_RATE, audio_stereo)
    vf.seek(0) 
    return vf

# ==========================================
# 2. 다중 채널 믹싱 엔진
# ==========================================

def generate_mixed_sound(data_list, max_freq_list, waveform_list):
    if not data_list: return None
    
    # [수정 3] 다중 채널에도 0.1초 앞뒤 여백 추가
    pad_len = int(0.1 * config.SAMPLE_RATE)
    padded_data_list = [np.pad(data, (pad_len, pad_len), mode='edge') for data in data_list]
    
    N = len(padded_data_list[0]) 
    mixed_left = np.zeros(N)
    mixed_right = np.zeros(N)
    
    for data, max_f, wave_type in zip(padded_data_list, max_freq_list, waveform_list):
        min_freq = config.DEFAULT_MIN_FREQ
        max_freq = float(max_f)
        min_val, max_val = np.min(data), np.max(data)
        
        if max_val == min_val:
            freqs = np.full(N, min_freq)
        else:
            freqs = min_freq + (max_freq - min_freq) * ((data - min_val) / (max_val - min_val + 1e-9))
            
        phases = np.cumsum(freqs) * (2 * np.pi / config.SAMPLE_RATE)
        
        # [수정 2] 직관적인 음색
        if wave_type == "square" or "삐" in wave_type or "경고음" in wave_type:
            wave = signal.square(phases) * 0.8       # '삐' 소리
        elif wave_type == "sawtooth" or "브" in wave_type or "강조음" in wave_type:
            wave = signal.sawtooth(phases) * 0.8     # '브' 소리
        else:
            wave = np.sin(phases) * 0.8
            
        wave += _generate_beeps(data)
        
        pan_array = np.linspace(0.0, 1.0, N)
        left_channel = wave * np.cos(pan_array * np.pi / 2)
        right_channel = wave * np.sin(pan_array * np.pi / 2)
        
        mixed_left += left_channel
        mixed_right += right_channel

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