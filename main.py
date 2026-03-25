# main.py
import streamlit as st
import pandas as pd
import numpy as np
from PIL import Image
import engine  # 우리가 만든 엔진 모듈 임포트

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
            vf = engine.generate_stereo_sound(nums[col].values, max_freq)
            if vf: st.audio(vf, format='audio/wav')

with t2:
    up_img = st.file_uploader("이미지를 업로드하세요", type=['png', 'jpg', 'jpeg'], key="img_up")
    if up_img:
        img_raw = Image.open(up_img).convert('RGB')
        y, dbg = engine.extract_color_line(np.array(img_raw))
        
        c1, c2 = st.columns(2)
        c1.image(img_raw, use_container_width=True, caption="원본")
        c2.image(dbg, use_container_width=True, caption="추출 결과")
        
        st.write("**추출 데이터 재생**")
        vf_img = engine.generate_stereo_sound(y, max_freq)
        if vf_img: st.audio(vf_img, format='audio/wav')