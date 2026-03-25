import streamlit as st
import pandas as pd
import numpy as np
import io
import cv2
from PIL import Image
from scipy.io.wavfile import write

# ==========================================
# 임시 백엔드 서버 
#===========================================
# import requests
# SERVER_URL = "http://127.0.0.1:8501"
# def play_system_voice(action_name):
#     # 백엔드 API 호출
#     response = requests.get(f"{SERVER_URL}/voice/{action_name}")
#     if response.status_code == 200:
#         # 가져온 mp3 데이터를 바로 재생
#         st.audio(response.content, format="audio/mp3", autoplay=True)

# ==========================================
# 외부 CSS 로더 함수
# ==========================================
def apply_custom_style(file_name):
    try:
        with open(file_name, encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    except FileNotFoundError:
        st.error(f"⚠️ '{file_name}' 파일을 찾을 수 없습니다. 디자인이 적용되지 않습니다.")

# 페이지 설정
st.set_page_config(page_title="Project Pythagoras", page_icon="📐", layout="wide")

# ==========================================
# 사이드바 및 상태 관리 (사운드 컨트롤 + 고대비)
# ==========================================
with st.sidebar:
    st.title("Project Pythagoras")
    st.markdown("---")
    
    st.subheader("👁️ 접근성 설정")
    # 고대비 모드 토글 (style.css 연동)
    high_contrast = st.toggle("고대비 모드 (흑백)", value=False)
    if high_contrast:
        apply_custom_style("style.css")
    
    st.subheader("⚙️ 사운드 설정")
    st.markdown("시각 장애인의 청각 예민도에 맞춰 설정하세요.")
    # 주파수 상한선 조절 (1000Hz ~ 5000Hz)
    max_freq_input = st.slider("최대 주파수 설정 (Hz)", 1000, 5000, 1800, step=100)
    
    st.divider()
    st.info("💡 본 시스템은 저시력자 및 시각장애인 사용자의 데이터 접근성을 위해 설계되었습니다.")
    st.caption("© 2026 팀 피타고라스")

# ==========================================
# 핵심 사운드 변환 엔진
# ==========================================
def generate_stereo_sound(data_values, col_name, user_max_f):
    total_steps = len(data_values)
    if total_steps == 0:
        return None, None
        
    sample_rate = 44100
    total_play_time = 5.0  # 5초 고정
    duration = total_play_time / total_steps 
    
    min_freq = 200.0
    max_freq = float(user_max_f)

    left_channel = []
    right_channel = []
    current_phase = 0.0 
    
    N = int(sample_rate * duration)
    total_samples = total_steps * N
    min_val, max_val = np.min(data_values), np.max(data_values)

    for i, value in enumerate(data_values):
        if max_val == min_val:
            freq = min_freq
        else:
            freq = min_freq + (max_freq - min_freq) * ((value - min_val) / (max_val - min_val + 1e-9))
            
        t = np.linspace(0, duration, N, False)
        wave = np.sin(current_phase + freq * t * 2 * np.pi) 
        
        current_phase = (current_phase + freq * duration * 2 * np.pi) % (2 * np.pi)
        
        global_start = i * N
        pan_array = np.linspace(global_start / total_samples, (global_start + N) / total_samples, N, False)
        pan_array = np.clip(pan_array, 0.0, 1.0)
        
        left_wave = wave * np.cos(pan_array * np.pi / 2)
        right_wave = wave * np.sin(pan_array * np.pi / 2)
        
        left_channel.extend(left_wave)
        right_channel.extend(right_wave)

    audio_stereo = np.vstack((left_channel, right_channel)).T
    audio_stereo = np.int16(audio_stereo / (np.max(np.abs(audio_stereo)) + 1e-9) * 32767)
    
    virtual_file = io.BytesIO()
    write(virtual_file, sample_rate, audio_stereo)
    return virtual_file, sample_rate

# ==========================================
# 비정형 데이터 추출 엔진 (OpenCV)
# ==========================================
def extract_color_line(opencv_image_rgb):
    hsv = cv2.cvtColor(opencv_image_rgb, cv2.COLOR_RGB2HSV)
    lower_color = np.array([0, 50, 50])
    upper_color = np.array([179, 255, 255])
    mask_color = cv2.inRange(hsv, lower_color, upper_color)
    
    kernel = np.ones((3,3), np.uint8)
    mask = cv2.morphologyEx(mask_color, cv2.MORPH_OPEN, kernel, iterations=1)
    
    height, width = mask.shape
    raw_x, raw_y = [], []
    
    for x in range(width):
        y_indices = np.where(mask[:, x] == 255)[0]
        if len(y_indices) > 0:
            avg_y = np.mean(y_indices)
            raw_x.append(x)
            raw_y.append(height - avg_y)
            
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
# 메인 화면 UI (Tabs)
# ==========================================
st.title("🎧 멀티모달 가청화 시스템")
st.markdown("##### 시각적 데이터를 청각적 신호로 변환하여 데이터 접근성을 지원합니다.")
st.divider()

tab1, tab2 = st.tabs(["📊 정형 데이터 (CSV)", "🖼️ 비정형 데이터 (이미지)"])


    
with tab1:
    st.header("CSV 파일 가청화")
    uploaded_csv = st.file_uploader("CSV 파일을 업로드하세요", type=['csv'], key="csv_uploader")
    
    if uploaded_csv is not None:
        df = pd.read_csv(uploaded_csv)
        st.subheader("📈 데이터 시각화")
        st.line_chart(df)
        
        numeric_df = df.select_dtypes(include=[np.number])
        for col_name in numeric_df.columns:
            st.markdown(f"---")
            virtual_file, sr = generate_stereo_sound(numeric_df[col_name].values, col_name, max_freq_input)
            if virtual_file:
                st.subheader(f"🔊 '{col_name}' 열 가청화 재생")
                st.audio(virtual_file, format='audio/wav')

with tab2:
    st.header("그래프 이미지 분석")
    st.info("💡 팁: 그래프의 선만 명확하게 캡처된 이미지를 사용하면 인식률이 높아집니다.")
    
    uploaded_image = st.file_uploader("이미지를 업로드하세요", type=['png', 'jpg', 'jpeg'], key="img_uploader")
    
    if uploaded_image is not None:
        img = Image.open(uploaded_image)
        opencv_img = np.array(img.convert('RGB'))
        
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("🖼️ 원본 이미지")
            st.image(uploaded_image, use_container_width=True)
            
        with col2:
            st.subheader("🔍 데이터 추출 과정")
            data_extracted, debug_image = extract_color_line(opencv_img)
            st.image(debug_image, caption="꼭짓점 추출 및 보간 결과", use_container_width=True)

        st.markdown(f"---")
        st.subheader("📊 자동 추출된 데이터 차트")
        extracted_df = pd.DataFrame({"Extracted Data": data_extracted})
        st.line_chart(extracted_df)
        
        st.markdown(f"---")
        st.subheader("🔊 가청화 결과 재생")
        virtual_file_img, _ = generate_stereo_sound(data_extracted, "Image_Data", max_freq_input)
        if virtual_file_img:
            st.audio(virtual_file_img, format='audio/wav')