import streamlit as st
import pandas as pd
import numpy as np
from PIL import Image
import requests  
import engine    
from streamlit.components.v1 import html
from streamlit_cropper import st_cropper

# 백엔드 서버 주소 설정
SERVER_URL = "http://127.0.0.1:8000" 

def load_css(file_name):
    """외부 CSS 파일을 로드하여 스트림릿 UI에 적용"""
    with open(file_name, encoding="utf-8") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


st.set_page_config(page_title="Project Pythagoras", page_icon="📐", layout="wide")

# 사이드바 패널
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

st.title("🎧 멀티모달 가청화 시스템")
st.divider()

# 멀티모달 대응을 위한 탭 구조
t1, t2 = st.tabs(["📊 CSV 데이터 변환", "🖼️ 이미지 분석"])

# 탭 1: CSV 데이터 가청화 처리 로직
# 탭 1: CSV 데이터 가청화 처리 로직
with t1:
    up_csv = st.file_uploader("CSV 파일을 업로드하세요", type=['csv'], key="csv_up")
    if up_csv:
        df = pd.read_csv(up_csv)
        
        # [수정 1] 첫 번째 열이 시간이나 인덱스 성격의 데이터라면 X축(Index)으로 강제 지정
        first_col = df.columns[0]
        if first_col.lower() in ['time', 'date', 'index', '시간', '날짜', '기간', 'year', 'month', 'day',
                                'datetime', 'timestamp', 'epoch', 't', '일자', '연도', '년도', '분기', '주차', 
                                'id', 'no', '번호', '순번', 'idx']:
            df.set_index(first_col, inplace=True)
            
        nums = df.select_dtypes(include=[np.number])
        nums = nums.interpolate(method='linear', limit_direction='both')
        nums = nums.dropna(axis=1, how='all')
        
        if nums.empty:
            st.warning("가청화할 수 있는 유효한 수치 데이터가 없습니다.")
        else:
            # [수정 2] 스케일링 전, 사용자에게 보여줄 원본 최솟값/최댓값 보존
            original_stats = {}
            
            for col in nums.columns:
                col_min = nums[col].min()
                col_max = nums[col].max()
                original_stats[col] = (col_min, col_max) 
                
                # 데이터 정규화 (엔진 전송용)
                if col_min != col_max:
                    nums[col] = (nums[col] - col_min) / (col_max - col_min)
                else:
                    nums[col] = 0.5 

            # X축이 Time으로 설정되어 차트가 훨씬 자연스럽게 그려짐
            st.line_chart(nums) 
            st.divider()
            
            for col in nums.columns:
                orig_min, orig_max = original_stats[col]
                
                # [수정 3] 스크린리더 접근성을 위한 텍스트 마크다운 출력
                st.markdown(f"### 🎵 데이터: {col}")
                st.markdown(f"- **원본 최솟값:** `{orig_min:.2f}`")
                st.markdown(f"- **원본 최댓값:** `{orig_max:.2f}`")
                
                payload = {"data": nums[col].values.tolist(), "max_freq": max_freq}
                res = requests.post(f"{SERVER_URL}/sonify-data", json=payload)
                
                if res.status_code == 200:
                    st.audio(res.content, format='audio/wav')
                else:
                    st.error("서버 연결에 실패했습니다.")

# 탭 2: 이미지 데이터 가청화 처리 로직
with t2:
    up_img = st.file_uploader("이미지를 업로드하세요", type=['png', 'jpg', 'jpeg'], key="img_up")
    if up_img:
        img_raw = Image.open(up_img).convert('RGB')
        
        st.write("**분석할 그래프 영역을 마우스로 드래그하여 지정하세요**")
        
        # 화면 분할 레이아웃 적용 (이미지가 너무 크게 렌더링되는 현상 방지)
        left_col, right_col = st.columns([6, 4])
        
        with left_col:
            cropped_img = st_cropper(
                img_raw, 
                realtime_update=True, 
                box_color='#FF0000', 
                aspect_ratio=None, 
                stroke_width=1.0
            )
            
        with right_col:
            st.write("**ROI 추출 미리보기**")
            st.image(cropped_img, use_container_width=True, caption="선택된 관심 영역")
        
        st.divider()
        st.write("**추출 데이터 재생**")
        
        y, dbg = engine.extract_color_line(np.array(cropped_img))
        
        c1, c2 = st.columns(2)
        c1.image(cropped_img, use_container_width=True, caption="원본 (크롭됨)")
        c2.image(dbg, use_container_width=True, caption="추출 데이터 라인")
        
        payload_img = {"data": y.tolist(), "max_freq": max_freq}
        res_img = requests.post(f"{SERVER_URL}/sonify-data", json=payload_img)
        
        if res_img.status_code == 200:
            st.audio(res_img.content, format='audio/wav')
        else:
            st.error("서버 연결에 실패했습니다.")

# 글로벌 JS 단축키 스크립트 
try:
    with open("script.js", "r", encoding="utf-8") as f:
        js_code = f.read()
        html(f"<script>{js_code}</script>", height=0)
except FileNotFoundError:
    pass