import streamlit as st
import pandas as pd
import numpy as np
import io
import cv2
from PIL import Image
from scipy.io.wavfile import write

st.set_page_config(page_title="Data Sonifier Pro", layout="wide")
st.title("🎧 멀티모달 데이터 가청화 시스템")

# ==========================================
# 1. 핵심 사운드 변환 엔진 (트리밍 제거, 순정 복귀)
# ==========================================
def generate_stereo_sound(data_values, col_name):
    total_steps = len(data_values)
    if total_steps == 0:
        return None, None
        
    sample_rate = 44100
    total_play_time = 5.0 # 그래프 하나당 5초 고정
    duration = total_play_time / total_steps 
    min_freq, max_freq = 200.0, 800.0 

    left_channel = []
    right_channel = []
    current_phase = 0.0 
    
    # 노이즈 없는 하드 패닝을 위한 전체 샘플 수 계산
    N = int(sample_rate * duration)
    total_samples = total_steps * N
    
    # 데이터 매핑
    min_val, max_val = np.min(data_values), np.max(data_values)

    for i, value in enumerate(data_values):
        # 1. 주파수 계산
        if max_val == min_val:
            freq = min_freq
        else:
            freq = min_freq + (max_freq - min_freq) * ((value - min_val) / (max_val - min_val))
            
        # 2. 파형 생성 (연속 위상)
        t = np.linspace(0, duration, N, False)
        wave = np.sin(current_phase + freq * t * 2 * np.pi)
        
        # 다음 루프를 위해 위상 저장
        current_phase = (current_phase + freq * duration * 2 * np.pi) % (2 * np.pi)
        
        # 3. 완벽한 100% 분리 패닝
        global_start = i * N
        global_end = (i + 1) * N
        pan_array = np.linspace(global_start / total_samples, global_end / total_samples, N, False)
        pan_array = np.clip(pan_array, 0.0, 1.0)
        
        # 등전력 패닝 적용
        left_wave = wave * np.cos(pan_array * np.pi / 2)
        right_wave = wave * np.sin(pan_array * np.pi / 2)
        
        left_channel.extend(left_wave)
        right_channel.extend(right_wave)

    # 오디오 변환 및 저장
    audio_stereo = np.vstack((left_channel, right_channel)).T
    audio_stereo = np.int16(audio_stereo / (np.max(np.abs(audio_stereo)) + 1e-9) * 32767)
    
    virtual_file = io.BytesIO()
    write(virtual_file, sample_rate, audio_stereo)
    return virtual_file, sample_rate

# ==========================================
# 2. 범용 컬러 마스킹 및 꼭짓점 추출 엔진 (유지)
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
# 3. 메인 화면 UI (Tabs 적용, 트리밍 슬라이더 제거)
# ==========================================
tab1, tab2 = st.tabs(["📄 정형 데이터 (CSV)", "🖼️ 비정형 데이터 (이미지)"])

with tab1:
    st.header("CSV 파일 가청화")
    uploaded_csv = st.file_uploader("숫자 데이터가 포함된 CSV 파일을 올려주세요", type=['csv'], key="csv_uploader")
    
    if uploaded_csv is not None:
        df = pd.read_csv(uploaded_csv)
        st.subheader("📈 원본 CSV 그래프 시각화")
        st.line_chart(df)
        
        numeric_df = df.select_dtypes(include=[np.number])
        for col_name in numeric_df.columns:
            st.markdown(f"---")
            virtual_file, sr = generate_stereo_sound(numeric_df[col_name].values, col_name)
            if virtual_file:
                st.subheader(f"🔊 '{col_name}' 열 재생 (5초)")
                st.audio(virtual_file, format='audio/wav')

with tab2:
    st.header("그래프 선(ROI) 이미지 가청화")
    st.info("💡 팁: 축(Axis), 숫자, 글자 등을 제외하고 **순수하게 컬러 선이 있는 영역만 캡처해서 올리면** 정확도가 100%에 가까워집니다!")
    
    uploaded_image = st.file_uploader("분석할 그래프 영역 이미지를 올려주세요", type=['png', 'jpg', 'jpeg'], key="img_uploader")
    
    if uploaded_image is not None:
        img = Image.open(uploaded_image)
        opencv_img = np.array(img.convert('RGB'))
        
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("🖼️ 원본 이미지")
            st.image(uploaded_image, use_container_width=True)
            
        with col2:
            st.subheader("🔍 AI 꼭짓점 추출 과정")
            data_extracted, debug_image = extract_color_line(opencv_img)
            st.image(debug_image, caption="컴퓨터가 인식한 꺾임 구간(빨간 점) 및 보간된 데이터(초록 선)", use_container_width=True)

        st.markdown(f"---")
        st.subheader("📊 자동 추출된 데이터 차트")
        extracted_df = pd.DataFrame({"Extracted Data": data_extracted})
        st.line_chart(extracted_df)
        
        st.markdown(f"---")
        st.subheader("🔊 가청화 결과 재생")
        virtual_file_img, _ = generate_stereo_sound(data_extracted, "Image_Data")
        if virtual_file_img:
            st.audio(virtual_file_img, format='audio/wav')