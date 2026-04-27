import streamlit as st
import pandas as pd
import numpy as np
from PIL import Image
import requests  
import engine    
from streamlit.components.v1 import html
from streamlit_cropper import st_cropper
import base64

# 백엔드 서버 주소 설정
SERVER_URL = "http://127.0.0.1:8000" 

def load_css(file_name):
    # 외부 CSS 파일을 로드하여 스트림릿 UI에 적용
    with open(file_name, encoding="utf-8") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

st.set_page_config(page_title="Project Pythagoras", page_icon="📐", layout="wide")
# 이 style은 css에 따로 빼는 순간 고대비 모드에서만 작동하기 때문에 글로벌로 선언
st.markdown("""
    <style>
    /* [그래프 상호작용 잠금] 하위 캔버스 요소까지 마우스 이벤트 완벽 차단 */
    [data-testid="stArrowVegaLiteChart"],
    [data-testid="stArrowVegaLiteChart"] div,
    [data-testid="stArrowVegaLiteChart"] canvas,
    .vega-embed {
        pointer-events: none !important;
    }
    </style>
""", unsafe_allow_html=True)

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
with t1:
    up_csv = st.file_uploader("CSV 파일을 업로드하세요", type=['csv'], key="csv_up")
    if up_csv:
        df = pd.read_csv(up_csv)
        
        # 첫 번째 열이 시간이나 인덱스 성격의 데이터라면 X축으로 강제 지정
        first_col = df.columns[0]
        index_keywords = ['time', 'date', 'index', '시간', '날짜', '기간', 'year', 'month', 'day',
                          'datetime', 'timestamp', 'epoch', 't', '일자', '연도', '년도', '분기', '주차', 
                          'id', 'no', '번호', '순번', 'idx']
                          
        if first_col.lower() in index_keywords:
            df.set_index(first_col, inplace=True)
            
        nums = df.select_dtypes(include=[np.number])
        nums = nums.interpolate(method='linear', limit_direction='both')
        nums = nums.dropna(axis=1, how='all')
        
        if nums.empty:
            st.warning("가청화할 수 있는 유효한 수치 데이터가 없습니다.")
        else:
            # 스케일링 전 원본 최솟값/최댓값 보존
            original_stats = {}
            
            for col in nums.columns:
                col_min = nums[col].min()
                col_max = nums[col].max()
                original_stats[col] = (col_min, col_max) 
                
                # 데이터 정규화
                if col_min != col_max:
                    nums[col] = (nums[col] - col_min) / (col_max - col_min)
                else:
                    nums[col] = 0.5 

            st.line_chart(nums) 
            st.divider()
            
            for i, col in enumerate(nums.columns):
                orig_min, orig_max = original_stats[col]
                
                # 스크린리더 접근성을 위한 텍스트 마크다운 출력
                st.markdown(f"### 🎵 데이터: {col}")
                st.markdown(f"- **원본 최솟값:** `{orig_min:.2f}`")
                st.markdown(f"- **원본 최댓값:** `{orig_max:.2f}`")
                
                payload = {"data": nums[col].values.tolist(), "max_freq": max_freq}
                res = requests.post(f"{SERVER_URL}/sonify-data", json=payload)
                
                if res.status_code == 200:
                    b64_audio = base64.b64encode(res.content).decode("utf-8")
                    
                    # HTML과 JS를 결합하여 브라우저 내장 TTS 연동 플레이어 생성
                    html_code = f"""
                    <div style="display: flex; align-items: center; gap: 10px;">
                        <button id="tts_btn_{i}" 
                                onclick="window.parent.playTTS({i}, '{col}', {orig_min}, {orig_max})"
                                style="padding: 8px 15px; border-radius: 8px; border: 1px solid #ccc; background: white; cursor: pointer; font-weight: bold; color: black;">
                            🔊 음성 안내와 함께 듣기
                        </button>
                        <audio id="audio_{i}" src="data:audio/wav;base64,{b64_audio}" controls></audio>
                    </div>
                    """
                    st.components.v1.html(html_code, height=60)
                else:
                    st.error("서버 연결에 실패했습니다.")

# 탭 2: 이미지 데이터 가청화 처리 로직
with t2:
    up_img = st.file_uploader("이미지를 업로드하세요", type=['png', 'jpg', 'jpeg'], key="img_up")
    if up_img:
        img_raw = Image.open(up_img).convert('RGB')
        
        st.write("**분석할 그래프 영역을 마우스로 드래그하여 지정하세요**")
        
        left_col, right_col = st.columns([8, 2])
        
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