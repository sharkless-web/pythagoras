import streamlit as st

import pandas as pd

import numpy as np

import io, cv2

from PIL import Image

from scipy.io.wavfile import write



# ==========================================

# 1. 페이지 설정

# ==========================================

st.set_page_config(page_title="Project Pythagoras", page_icon="📐", layout="wide")



# ==========================================

# 2. 사이드바 및 상태 관리

# ==========================================

with st.sidebar:

    st.title("피타고라스")

    st.markdown("---")

    st.subheader("👁️ 접근성 설정")

    

    high_contrast = st.toggle("고대비 모드", value=False)

    

    st.subheader("🔊 시스템 설정")

    volume = st.slider("출력 볼륨", 0, 100, 80)

    st.divider()

    st.info("💡 시스템이 다크모드이거나 토글을 켜면 동일한 고대비 테마가 적용됩니다.")

    st.caption("© 2026 팀 피타고라스")



# ==========================================

# 3. 통합 테마 CSS (드롭존 배경색 정밀 수정)

# ==========================================



# 고대비 스타일 내부 정의

hc_core = """

    .block-container { padding-top: 4rem !important; padding-bottom: 0rem !important; }

    .stApp header { visibility: hidden; } 

    .stApp { background-color: #000000 !important; color: #ffffff !important; }

    [data-testid="stSidebar"] { background-color: #000000 !important; border-right: 1px solid #ffffff !important; }

    h1, h2, h3, h4, p, span, label, .stMarkdown, [data-testid="stSidebar"] * { color: #ffffff !important; }

    

    .stTabs [data-baseweb="tab-list"] { background-color: #000000 !important; border-bottom: 1px solid #ffffff !important; }

    .stTabs [data-baseweb="tab"] { 

        background-color: #000000 !important; 

        color: #ffffff !important; 

        border: 1px solid #ffffff !important; 

        border-bottom: none !important; 

        border-radius: 12px 12px 0 0 !important; 

        padding: 10px 25px !important;

    }

    .stTabs [aria-selected="true"] { background-color: #ffffff !important; color: #000000 !important; }

    .stTabs [aria-selected="true"] div, .stTabs [aria-selected="true"] p { color: #000000 !important; font-weight: 600 !important; }

    

    .stButton>button { 

        background-color: #ffffff !important; 

        color: #000000 !important; 

        border: 1px solid #ffffff !important; 

        border-radius: 12px !important;

        width: 100%; height: 3em; font-weight: bold;

    }



    /* ✅ [핵심 수정] 드롭존(파일 여는 영역)만 밝은 회색으로 유지 */

    [data-testid="stFileUploader"] { 

        border: none !important; 

        background-color: transparent !important; 

    }

    [data-testid="stFileUploaderDropzone"] { 

        background-color: #f0f2f6 !important; /* 밝은 회색 유지 */

        border: 2px dashed #ffffff !important; 

        border-radius: 15px !important;

    }

    [data-testid="stFileUploaderDropzone"] * { color: #000000 !important; } /* 내부 글자 검정색 */

    .stFileUploader button { background-color: #000000 !important; color: #ffffff !important; }

"""



# 전체 스타일 적용

style_content = f"""

    <style>

    .block-container {{ padding-top: 4rem !important; }}

    .stButton>button {{ width: 100%; height: 3em; border-radius: 12px; font-weight: bold; border: none; }}

    .stTabs [data-baseweb="tab"] {{ border-radius: 12px 12px 0 0; padding: 10px 25px; font-weight: 600; }}

    .stFileUploader {{ border-radius: 15px; padding: 20px; }}



    @media (prefers-color-scheme: light) {{

        .main {{ background-color: #fcfcfc; }}

        h1, h2, h3 {{ color: #003366 !important; font-family: 'Nanum Gothic', sans-serif; font-weight: 800; }}

        [data-testid="stSidebar"] {{ background-color: #001f3f; }}

        [data-testid="stSidebar"] * {{ color: #ffffff !important; }}

        .stButton>button {{ background-color: #004a99; color: white; }}

        .stTabs [data-baseweb="tab"] {{ background-color: #f0f2f6; color: #333; }}

        .stTabs [aria-selected="true"] {{ background-color: #004a99 !important; color: white !important; }}

        .stFileUploader {{ border: 2px dashed #004a99; }}

    }}



    @media (prefers-color-scheme: dark) {{

        {hc_core}

    }}



    {hc_core if high_contrast else ''}

    </style>

"""



st.markdown(style_content, unsafe_allow_html=True)



# ==========================================

# 4. 가청화 및 추출 로직 (변동 없음)

# ==========================================

def generate_stereo_sound(data_values, col_name):

    total_steps = len(data_values)

    if total_steps == 0: return None, None

    sample_rate, total_play_time = 44100, 5.0

    duration = total_play_time / total_steps

    min_freq, max_freq = 200.0, 1800.0

    left_channel, right_channel, current_phase = [], [], 0.0

    N = int(sample_rate * duration)

    total_samples = total_steps * N

    min_val, max_val = np.min(data_values), np.max(data_values)

    denom = (max_val - min_val) if max_val != min_val else 1e-9



    for i, value in enumerate(data_values):

        freq = min_freq + (max_freq - min_freq) * ((value - min_val) / denom)

        t = np.linspace(0, duration, N, False)

        wave = np.sin(current_phase + freq * t * 2 * np.pi)

        current_phase = (current_phase + freq * duration * 2 * np.pi) % (2 * np.pi)

        pan = np.clip(np.linspace(i*N/total_samples, (i+1)*N/total_samples, N, False), 0.0, 1.0)

        left_channel.extend(wave * np.cos(pan * np.pi / 2))

        right_channel.extend(wave * np.sin(pan * np.pi / 2))



    audio_stereo = np.vstack((left_channel, right_channel)).T

    audio_stereo = np.int16(audio_stereo / (np.max(np.abs(audio_stereo)) + 1e-9) * (32767 * volume / 100))

    vf = io.BytesIO(); write(vf, sample_rate, audio_stereo); return vf, sample_rate



def extract_line(img):

    hsv = cv2.cvtColor(img, cv2.COLOR_RGB2HSV)

    mask = cv2.inRange(hsv, np.array([0, 50, 50]), np.array([179, 255, 255]))

    h, w = mask.shape

    x_l, y_l = [], []

    for x in range(w):

        ids = np.where(mask[:, x] == 255)[0]

        if len(ids) > 0: x_l.append(x); y_l.append(h - np.mean(ids))

    if not x_l: return np.zeros(w), img

    y_s = np.interp(np.arange(w), x_l, y_l)

    return y_s, cv2.cvtColor(mask, cv2.COLOR_GRAY2RGB)



# ==========================================

# 5. 메인 UI

# ==========================================



col1, col2 = st.columns([1, 15])

with col1:

    st.title("🎧")

with col2:

    st.title("멀티모달 가청화 시스템")

    st.markdown("##### 시각적 데이터를 청각적 신호로 변환하여 분석을 지원합니다.")



st.divider()



t1, t2 = st.tabs(["📊 CSV 데이터 변환", "🖼️ 그래프 이미지 분석"])



with t1:

    st.subheader("📄 CSV 파일 업로드")

    up_csv = st.file_uploader("CSV 파일을 업로드하세요.", type=['csv'], key="c_up")

    if up_csv:

        df = pd.read_csv(up_csv); st.line_chart(df)

        nums = df.select_dtypes(include=[np.number])

        for c in nums.columns:

            vf, _ = generate_stereo_sound(nums[c].values, c)

            if vf: st.write(f"**열: {c} 가청화 데이터**"); st.audio(vf)



with t2:

    st.subheader("🖼️ 그래프 이미지 분석")

    up_img = st.file_uploader("이미지 파일을 업로드하세요.", type=['png', 'jpg', 'jpeg'], key="i_up")

    if up_img:

        img_raw = Image.open(up_img).convert('RGB'); img_arr = np.array(img_raw)

        y, dbg = extract_line(img_arr); c1, c2 = st.columns(2)

        c1.image(img_raw, use_container_width=True, caption="원본 그래프")

        c2.image(dbg, use_container_width=True, caption="추출 결과")

        vf_i, _ = generate_stereo_sound(y, "Img")

        if vf_i: st.write("**추출 데이터 가청화**"); st.audio(vf_i) 
