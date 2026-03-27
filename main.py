import streamlit as st
import pandas as pd
import numpy as np
from PIL import Image
import requests  
import engine    
from streamlit.components.v1 import html

# 백엔드(FastAPI) 서버 주소 설정
SERVER_URL = "http://127.0.0.1:8000" 

def load_css(file_name):
    """외부 CSS 파일을 로드하여 스트림릿 UI에 적용함"""
    with open(file_name, encoding="utf-8") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

st.set_page_config(page_title="Project Pythagoras", page_icon="📐", layout="wide")

# 사이드바 패널: 접근성 및 오디오 파라미터 제어
with st.sidebar:
    st.title("Project Pythagoras")
    st.markdown("---")
    st.subheader("👁️ 접근성 설정")
    
    # 고대비 모드 활성화 시 style.css 주입
    high_contrast = st.toggle("고대비 모드 (흑백)", value=False)
    if high_contrast:
        load_css("style.css")
    
    st.subheader("⚙️ 사운드 설정")
    # 사용자의 가청 범위를 고려한 주파수 필터 슬라이더
    max_freq = st.slider("최대 주파수 설정 (Hz)", 1000, 5000, 1800, step=100)
    st.divider()
    st.info("💡 본 시스템은 저시력자 및 시각장애인 사용자의 데이터 접근성을 위해 설계되었습니다.")
    st.caption("© 2026 팀 피타고라스")

# 메인 대시보드 UI
st.title("🎧 멀티모달 가청화 시스템")
st.divider()

# 멀티모달 대응을 위한 탭 구조 (CSV/이미지)
t1, t2 = st.tabs(["📊 CSV 데이터 변환", "🖼️ 이미지 분석"])

# 탭 1: CSV 데이터 가청화 처리 로직
with t1:
    up_csv = st.file_uploader("CSV 파일을 업로드하세요", type=['csv'], key="csv_up")
    if up_csv:
        df = pd.read_csv(up_csv)
        st.line_chart(df) # 데이터 시각화 프리뷰
        
        # 수치 데이터만 선별하여 백엔드 전송 준비
        nums = df.select_dtypes(include=[np.number])
        for col in nums.columns:
            st.write(f"**열: {col} 재생**")
            
            # FastAPI 서버로 데이터 전송 및 가청화 사운드 요청
            payload = {"data": nums[col].values.tolist(), "max_freq": max_freq}
            res = requests.post(f"{SERVER_URL}/sonify-data", json=payload)
            
            if res.status_code == 200:
                st.audio(res.content, format='audio/wav')
            else:
                st.error("서버 연결에 실패했습니다.")
    
    # 키보드 접근성(단축키) 향상을 위한 외부 JS 인젝션
    try:
        with open("script.js", "r", encoding="utf-8") as f:
            js_code = f.read()
            html(f"<script>{js_code}</script>", height=0)
    except FileNotFoundError:
        st.error("script.js 파일을 찾을 수 없습니다.")

# 탭 2: 이미지 데이터 가청화 처리 로직
with t2:
    up_img = st.file_uploader("이미지를 업로드하세요", type=['png', 'jpg', 'jpeg'], key="img_up")
    if up_img:
        img_raw = Image.open(up_img).convert('RGB')
        
        # 엔진을 통한 이미지 내 그래픽 선(Line) 추출
        y, dbg = engine.extract_color_line(np.array(img_raw))
        
        c1, c2 = st.columns(2)
        c1.image(img_raw, use_container_width=True, caption="원본")
        c2.image(dbg, use_container_width=True, caption="추출 결과")
        
        st.write("**추출 데이터 재생**")
        
        # 추출된 y축 좌표 리스트를 서버로 전송하여 소리로 변환
        payload_img = {"data": y.tolist(), "max_freq": max_freq}
        res_img = requests.post(f"{SERVER_URL}/sonify-data", json=payload_img)
        
        if res_img.status_code == 200:
            st.audio(res_img.content, format='audio/wav')
        else:
            st.error("서버 연결에 실패했습니다.")