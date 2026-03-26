import streamlit as st
import pandas as pd
import numpy as np
from PIL import Image
import requests  # 👈 백엔드 통신을 위해 추가
import engine    # 👈 이미지 추출 로직은 여전히 사용

SERVER_URL = "http://127.0.0.1:8000"  # FastAPI 주소


def load_css(file_name):
    with open(file_name, encoding="utf-8") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

st.set_page_config(page_title="Project Pythagoras", page_icon="📐", layout="wide")

# 사이드바 설정
with st.sidebar:
    st.title("Project Pythagoras")
    st.markdown("---")
    st.subheader("👁️ 접근성 설정")
    high_contrast = st.toggle("고대비 모드 (흑백)", value=False)
    if high_contrast:
        load_css("style.css")
    
    st.subheader("⚙️ 사운드 설정")
    max_freq = st.slider("최대 주파수 설정 (Hz)", 1000, 5000, 1800, step=100)
    st.divider()
    st.info("💡 본 시스템은 저시력자 및 시각장애인 사용자의 데이터 접근성을 위해 설계되었습니다.")
    st.caption("© 2026 팀 피타고라스")

# 메인 UI
st.title("🎧 멀티모달 가청화 시스템")
st.divider()

t1, t2 = st.tabs(["📊 CSV 데이터 변환", "🖼️ 이미지 분석"])

with t1:
    up_csv = st.file_uploader("CSV 파일을 업로드하세요", type=['csv'], key="csv_up")
    if up_csv:
        df = pd.read_csv(up_csv)
        st.line_chart(df)
        nums = df.select_dtypes(include=[np.number])
        for col in nums.columns:
            st.write(f"**열: {col} 재생**")
            
            # 💡 [백엔드 통신 추가] 로컬 연산 대신 서버로 데이터를 보냅니다.
            payload = {"data": nums[col].values.tolist(), "max_freq": max_freq}
            res = requests.post(f"{SERVER_URL}/sonify-data", json=payload)
            
            if res.status_code == 200:
                st.audio(res.content, format='audio/wav')
            else:
                st.error("서버 연결에 실패했습니다.")

with t2:
    up_img = st.file_uploader("이미지를 업로드하세요", type=['png', 'jpg', 'jpeg'], key="img_up")
    if up_img:
        img_raw = Image.open(up_img).convert('RGB')
        
        # 이미지 추출(OpenCV)은 메인에서 처리하고 결과값(y)만 뺍니다.
        y, dbg = engine.extract_color_line(np.array(img_raw))
        
        c1, c2 = st.columns(2)
        c1.image(img_raw, use_container_width=True, caption="원본")
        c2.image(dbg, use_container_width=True, caption="추출 결과")
        
        st.write("**추출 데이터 재생**")
        
        # 💡 [백엔드 통신 추가] 추출된 y 데이터를 서버로 보내 소리로 만듭니다.
        payload_img = {"data": y.tolist(), "max_freq": max_freq}
        res_img = requests.post(f"{SERVER_URL}/sonify-data", json=payload_img)
        
        if res_img.status_code == 200:
            st.audio(res_img.content, format='audio/wav')
        else:
            st.error("서버 연결에 실패했습니다.")
