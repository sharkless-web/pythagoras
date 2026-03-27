import numpy as np
import cv2
import io
from scipy.io.wavfile import write
import config

def generate_stereo_sound(data_values, user_max_f):
    """
    입력된 수치 데이터를 스테레오 사운드로 변환하는 핵심 엔진.
    데이터 흐름에 따라 주파수(Pitch)와 패닝(L/R)을 동시에 제어함.
    """
    total_steps = len(data_values)
    if total_steps == 0: return None, None
    
    # 설정값 로드
    duration = config.TOTAL_PLAY_TIME / total_steps 
    min_freq = config.DEFAULT_MIN_FREQ
    max_freq = float(user_max_f)

    left_channel, right_channel = [], []
    current_phase = 0.0 # 주파수 변화 시 노이즈(Clicking) 방지를 위한 페이즈 유지
    N = int(config.SAMPLE_RATE * duration)
    total_samples = total_steps * N
    min_val, max_val = np.min(data_values), np.max(data_values)

    for i, value in enumerate(data_values):
        # 1. 주파수 매핑: 데이터 값이 클수록 고음, 작을수록 저음
        freq = min_freq if max_val == min_val else min_freq + (max_freq - min_freq) * ((value - min_val) / (max_val - min_val + 1e-9))
        
        # 2. 사인파 생성: 시간축(t)에 맞춰 파형 계산
        t = np.linspace(0, duration, N, False)
        wave = np.sin(current_phase + freq * t * 2 * np.pi) 
        current_phase = (current_phase + freq * duration * 2 * np.pi) % (2 * np.pi)
        
        # 3. 스테레오 패닝: 시간이 흐를수록 왼쪽(L)에서 오른쪽(R)으로 소리가 넘어감
        pan_array = np.linspace(i*N / total_samples, (i+1)*N / total_samples, N, False)
        pan_array = np.clip(pan_array, 0.0, 1.0)
        
        # Constant Power Panning 적용 (L/R 볼륨 합을 일정하게 유지)
        left_channel.extend(wave * np.cos(pan_array * np.pi / 2))
        right_channel.extend(wave * np.sin(pan_array * np.pi / 2))

    # 데이터 타입 변환: float32 -> int16 (WAV 표준 포맷)
    audio_stereo = np.vstack((left_channel, right_channel)).T
    audio_stereo = np.int16(audio_stereo / (np.max(np.abs(audio_stereo)) + 1e-9) * 32767)
    
    # 메모리상에 WAV 파일 생성 (디스크 저장 없이 즉시 재생용)
    vf = io.BytesIO()
    write(vf, config.SAMPLE_RATE, audio_stereo)
    return vf

def extract_color_line(opencv_img):
    """
    이미지에서 특정 색상의 선(Line)을 추적해서 수치 데이터로 변환.
    OpenCV 전처리 후 다항 근사화를 통해 노이즈를 제거함.
    """
    # 1. 색상 필터링: HSV 영역에서 설정된 컬러 범위만 추출(Masking)
    hsv = cv2.cvtColor(opencv_img, cv2.COLOR_RGB2HSV)
    mask = cv2.inRange(hsv, np.array(config.LOWER_COLOR), np.array(config.UPPER_COLOR))
    
    # 2. 노이즈 제거: 모폴로지 연산으로 자잘한 점들 지우기
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3,3), np.uint8), iterations=1)
    
    h, w = mask.shape
    raw_x, raw_y = [], []
    
    # 3. 픽셀 스캔: 각 x 좌표별로 픽셀이 켜진 y 좌표의 평균값 계산 (선 추적)
    for x in range(w):
        y_ids = np.where(mask[:, x] == 255)[0]
        if len(y_ids) > 0:
            raw_x.append(x); raw_y.append(h - np.mean(y_ids))
            
    if not raw_x: return np.zeros(w), opencv_img
        
    # 4. 데이터 최적화: 수천 개의 픽셀 데이터를 주요 포인트(Keypoints) 위주로 단순화(Douglas-Peucker)
    curve = np.array([[[x, y]] for x, y in zip(raw_x, raw_y)], dtype=np.float32)
    approx = cv2.approxPolyDP(curve, 0.005 * cv2.arcLength(curve, False), False)
    key_x, key_y = [pt[0][0] for pt in approx], [pt[0][1] for pt in approx]
    
    # 5. 보간법(Interpolation): 단순화된 데이터를 다시 전체 이미지 너비(w)에 맞춰 복원
    data = np.interp(np.arange(w), key_x, key_y)
    
    # 디버깅용 이미지 생성: 마스크 이미지 위에 추적된 선을 초록색으로 덧그림
    dbg_img = cv2.cvtColor(mask, cv2.COLOR_GRAY2RGB)
    for i in range(len(key_x) - 1):
        cv2.line(dbg_img, (int(key_x[i]), int(h-key_y[i])), (int(key_x[i+1]), int(h-key_y[i+1])), (0, 255, 0), 2)
    return data, dbg_img