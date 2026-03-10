import streamlit as st
import pandas as pd
import numpy as np
import io
from scipy.io.wavfile import write

st.title("데이터 사운드 변환기 (스테레오 버전)")
uploaded_file = st.file_uploader("CSV 파일을 올려주세요", type=['csv'])

if uploaded_file is not None:
    df = pd.read_csv(uploaded_file)
    st.line_chart(df) # 그래프 시각화 추가
    
    data_values = df.iloc[:, 0].values
    sample_rate = 44100
    duration = 0.2
    
    min_freq, max_freq = 200.0, 800.0
    min_val, max_val = np.min(data_values), np.max(data_values)

    # 전체 데이터 개수 (이게 소리의 전체 길이가 됩니다)
    total_steps = len(data_values)
    
    # 왼쪽/오른쪽 소리를 담을 두 개의 리스트 생성
    left_channel = []
    right_channel = []
    
    for i, value in enumerate(data_values):
        # 1. 높낮이(Pitch) 계산 (기존과 동일)
        freq = min_freq + (max_freq - min_freq) * ((value - min_val) / (max_val - min_val))
        t = np.linspace(0, duration, int(sample_rate * duration), False)
        wave = np.sin(freq * t * 2 * np.pi)
        
        # 2. 스테레오(Panning) 계산 ★핵심 포인트★
        # i가 0이면(시작) pan=0, i가 마지막이면 pan=1이 됩니다.
        pan = i / (total_steps - 1) 
        
        # 왼쪽 소리는 갈수록 작아지게 (1 -> 0)
        # 오른쪽 소리는 갈수록 커지게 (0 -> 1)
        left_wave = wave * (1 - pan)
        right_wave = wave * pan
        
        left_channel.extend(left_wave)
        right_channel.extend(right_wave)

    # 3. 두 채널을 합쳐서 2차원(스테레오) 배열로 만들기
    audio_stereo = np.vstack((left_channel, right_channel)).T # 세로로 쌓고 회전
    
    # 16비트 오디오 변환
    audio_stereo = np.int16(audio_stereo / np.max(np.abs(audio_stereo)) * 32767)
    
    virtual_file = io.BytesIO()
    write(virtual_file, sample_rate, audio_stereo)
    
    st.success("스테레오 변환 완료! 이어폰으로 들어보세요.")
    st.audio(virtual_file)