import streamlit as st
import pandas as pd
import numpy as np
import io
import cv2
from PIL import Image
from scipy.io.wavfile import write

st.set_page_config(page_title="Data Sonifier Pro", layout="wide")
st.title("🎧 멀티모달 데이터 가청화 시스템 (시작 부분 트리밍)")

# ==========================================
# 1. [大수정] 사운드 변환 엔진 (시작 부분 자르기 기능 추가)
# ==========================================
# trim_start_seconds 파라미터를 추가했습니다.
def generate_stereo_sound(data_values, col_name, trim_start_seconds=0.0):
    total_steps = len(data_values)
    if total_steps == 0:
        return None, None
        
    sample_rate = 44100
    total_play_time = 5.0 # 전체 그래프 재생 시간 (자르기 전 기준)
    duration = total_play_time / total_steps 
    min_freq, max_freq = 200.0, 800.0 

    left_channel = []
    right_channel = []
    current_phase = 0.0 
    
    # 노이즈 없는 하드 패닝을 위한 전체 샘플 수 계산
    N = int(sample_rate * duration)
    total_samples = total_steps * N
    
    # 데이터 매핑 (기존과 동일)
    min_val, max_val = np.min(data_values), np.max(data_values)

    for i, value in enumerate(data_values):
        # 1. 주파수 계산
        if max_val == min_val:
            freq = min_freq
        else:
            freq = min_freq + (max_freq - min_freq) * ((value - min_val) / (max_val - min_val))
            
        # 2. 파형 생성 (이전 파동과 완벽하게 이어붙이기)
        t = np.linspace(0, duration, N, False)
        wave = np.sin(current_phase + freq * t * 2 * np.pi)
        
        # 다음 루프를 위해 위상 저장
        current_phase = (current_phase + freq * duration * 2 * np.pi) % (2 * np.pi)
        
        # 3. 완벽한 하D 패닝
        global_start = i * N
        global_end = (i + 1) * N
        pan_array = np.linspace(global_start / total_samples, global_end / total_samples, N, False)
        pan_array = np.clip(pan_array, 0.0, 1.0)
        
        # 등전력 패닝 적용
        left_wave = wave * np.cos(pan_array * np.pi / 2)
        right_wave = wave * np.sin(pan_array * np.pi / 2)
        
        left_channel.extend(left_wave)
        right_channel.extend(right_wave)

    # ======== [★핵심 1: 시작 부분 자르기 로직] ========
    num_samples_to_trim = int(sample_rate * trim_start_seconds)
    if num_samples_to_trim > 0 and num_samples_to_trim < len(left_channel):
        # 파이썬 배열 슬라이싱을 사용하여 앞부분을 과감히 잘라냅니다.
        left_channel = left_channel[num_samples_to_trim:]
        right_channel = right_channel[num_samples_to_trim:]
        # 자른 시간만큼 전체 재생 시간도 줄어듭니다.
        actual_play_time = total_play_time - trim_start_seconds
    else:
        actual_play_time = total_play_time
    # =================================================

    # 오디오 변환 및 저장
    audio_stereo = np.vstack((left_channel, right_channel)).T
    audio_stereo = np.int16(audio_stereo / (np.max(np.abs(audio_stereo)) + 1e-9) * 32767)
    
    virtual_file = io.BytesIO()
    write(virtual_file, sample_rate, audio_stereo)
    return virtual_file, actual_play_time

# ==========================================
# 2. 범용 격자 제거 및 꼭짓점 추출 엔진 (유지)
# ==========================================
def extract_color_line(opencv_image_rgb):
    hsv = cv2.cvtColor(opencv_image_rgb, cv2.COLOR_RGB2HSV)
    lower_color = np.array([0, 50, 50])
    upper_color = np.array([179, 255, 255])
    mask_color = cv2.inRange(hsv, lower_color, upper_color)
    kernel = np.ones((3,3), np.uint8)
    mask = cv2.morphologyEx(mask_color, cv2.MORPH_OPEN, kernel, iterations=1)
    height, width = mask.shape
    raw_x = []
    raw_y = []
    for x in range(width):
        y_indices = np.where(mask[:, x] == 255)[0]
        if len(y_indices) > 0:
            avg_y = np.mean(y_indices)
            real_y = height - avg_y 
            raw_x.append(x)
            raw_y.append(real_y)
    if not raw_x:
        return np.zeros(width), opencv_image_rgb
    curve = np.array([[[x, y]] for x, y in zip(raw_x, raw_y)], dtype=np.float32)
    epsilon = 0.005 * cv2.arcLength(curve, False)
    approx = cv2.approxPolyDP(curve, epsilon, False)
    key_x = [pt[0][0] for pt in approx]
    key_y = [pt[0][1] for pt in approx]
    full_x = np.arange(width)
    smoothed_y_data = np.interp(full_x, key_x, key_y)
    mask_bg = cv2.cvtColor(mask, cv2.COLOR_GRAY2RGB)
    for i in range(len(key_x) - 1):
        pt1 = (int(key_x[i]), int(height - key_y[i]))
        pt2 = (int(key_x[i+1]), int(height - key_y[i+1]))
        cv2.line(mask_bg, pt1, pt2, (0, 255, 0), 2)
    for x, y in zip(key_x, key_y):
        cv2.circle(mask_bg, (int(x), int(height - y)), 6, (255, 0, 0), -1)
    return smoothed_y_data, mask_bg

# ==========================================
# 3. 메인 화면 UI (Tabs 적용 및 트리밍 UI 추가)
# ==========================================
tab1, tab2 = st.tabs(["📄 정형 데이터 (CSV)", "🖼️ 비정형 데이터 (이미지)"])

with tab1:
    st.header("CSV 파일 가청화")
    st.write("CSV 파일은 이미지 노이즈가 없으므로 트리밍 없이 전체를 재생합니다.")
    uploaded_csv = st.file_uploader("숫자 데이터가 포함된 CSV 파일을 올려주세요", type=['csv'], key="csv_uploader")
    
    if uploaded_csv is not None:
        df = pd.read_csv(uploaded_csv)
        st.subheader("📈 원본 CSV 그래프 시각화")
        st.line_chart(df)
        
        numeric_df = df.select_dtypes(include=[np.number])
        for col_name in numeric_df.columns:
            st.markdown(f"---")
            # CSV 모드는 trim_start_seconds를 0으로 고정합니다.
            virtual_file, playtime = generate_stereo_sound(numeric_df[col_name].values, col_name, trim_start_seconds=0.0)
            if virtual_file:
                st.subheader(f"🔊 '{col_name}' 열 재생 ({playtime:.1f}초)")
                st.audio(virtual_file, format='audio/wav')

with tab2:
    st.header("범용 그래프 이미지 가청화 (트리밍 기능)")
    st.write("이미지 인식의 한계(시작 부분 노이즈)를 극복하기 위해, 재생 시 시작 부분의 일정 시간을 수학적으로 제거합니다.")
    uploaded_image = st.file_uploader("컬러 선 그래프 이미지를 올려주세요", type=['png', 'jpg', 'jpeg'], key="img_uploader")
    
    if uploaded_image is not None:
        img = Image.open(uploaded_image)
        # RGBA 이미지 처리 및 RGB 변환
        opencv_img = np.array(img.convert('RGB'))
        
        # ======== [★핵심 2: 시작 부분 자르기 슬라이더 UI 추가] ========
        st.markdown(f"---")
        st.subheader("🛠️ 사운드 재생 설정 (Image 전용)")
        # 0.5초에서 1.0초 사이를 기본값 0.75초로 설정합니다.
        trim_sec = st.slider("시작 부분 노이즈 제거 (초)", 0.0, 1.0, 0.75, 0.05, key="img_trim_slider")
        st.write(f"처음 **{trim_sec:.2f}초**를 날리고 그 이후부터 재생을 시작합니다.")
        st.markdown(f"---")
        # ==========================================================

        col1, col2 = st.columns(2)
        with col1:
            st.subheader("🖼️ 원본 이미지")
            st.image(uploaded_image, use_container_width=True)
            
        with col2:
            st.subheader("🔍 격자 제거 및 꼭짓점 추출 과정")
            data_extracted, debug_image = extract_color_line(opencv_img)
            st.image(debug_image, caption="격자가 사라지고 컬러 선 위에만 꼭짓점이 찍힘", use_container_width=True)

        st.markdown(f"---")
        st.subheader("📊 자동 추출 및 보간된 최종 데이터 차트")
        st.write("이 데이터에서 앞부분을 수학적으로 잘라내어 사운드를 생성합니다.")
        extracted_df = pd.read_csv(io.StringIO("Index,ExtractedData\n")) # Empty DF for layout
        extracted_df = pd.DataFrame({"Extracted Data": data_extracted})
        st.line_chart(extracted_df)
        
        st.markdown(f"---")
        st.subheader(f"🔊 트리밍된 가청화 결과 재생 (처음 {trim_sec:.1f}초 제외)")
        
        # ======== [★핵심 3: 슬라이더 값을 엔진에 전달] ========
        # 슬라이더에서 받은 trim_sec 값을 전달하여 오디오를 생성합니다.
        virtual_file_img, playtime = generate_stereo_sound(data_extracted, "Image_Data", trim_start_seconds=trim_sec)
        
        if virtual_file_img:
            # 최종 재생 시간(예: 4.2초)을 UI에 표시해 줍니다.
            st.markdown(f"**📍 최종 재생 시간: 약 {playtime:.1f}초 (처음 노이즈 제거됨)**")
            st.audio(virtual_file_img, format='audio/wav')