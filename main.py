import streamlit as st
import pandas as pd
import numpy as np
import io
from scipy.io.wavfile import write

st.title("데이터 사운드 변환기 - 스테레오 모드")
uploaded_file = st.file_uploader("CSV 파일을 올려주세요", type=['csv'])

if uploaded_file is not None:
    df = pd.read_csv(uploaded_file)
    st.line_chart(df) # 전체 그래프 시각화
    
    # 문자가 섞여있을 수 있으니 숫자형 데이터 열만 안전하게 추출합니다.
    numeric_df = df.select_dtypes(include=[np.number])
    
    sample_rate = 44100
    duration = 0.2
    min_freq, max_freq = 200.0, 800.0

    st.success(f"총 {len(numeric_df.columns)}개의 데이터 열이 감지되었습니다. 아래에서 각각 재생해 보세요!")

    # 감지된 열(Column)의 개수만큼 반복해서 오디오를 생성하고 플레이어를 띄웁니다.
    for col_name in numeric_df.columns:
        st.subheader(f"📈 '{col_name}' 열 재생")
        
        # 현재 반복 중인 열의 데이터만 가져옵니다.
        data_values = numeric_df[col_name].values
        total_steps = len(data_values)
        
        # 빈 데이터면 건너뛰기
        if total_steps == 0:
            continue
            
        min_val, max_val = np.min(data_values), np.max(data_values)
        
        left_channel = []
        right_channel = []
        
        # 루프 진입 전, 파동의 현재 위치(위상)를 기억할 변수를 만듭니다.
        current_phase = 0.0
        
        # 패닝 계산을 위한 전체 샘플 수 계산 (★반대쪽 소리 새는 문제 해결의 핵심)
        N = int(sample_rate * duration)
        total_samples = total_steps * N
        
        for i, value in enumerate(data_values):
            # 1. 주파수(Pitch) 계산
            if max_val == min_val:
                freq = min_freq
            else:
                freq = min_freq + (max_freq - min_freq) * ((value - min_val) / (max_val - min_val))
                
            # 2. 파형 생성 (이전 파동과 완벽하게 이어붙이기)
            t = np.linspace(0, duration, N, False)
            # 매번 0에서 시작하는 게 아니라, current_phase에서부터 시작합니다.
            wave = np.sin(current_phase + freq * t * 2 * np.pi)
            
            # 다음 루프를 위해 현재 파동이 끝난 지점을 저장합니다.
            current_phase = (current_phase + freq * duration * 2 * np.pi) % (2 * np.pi)
            
            # 3. 실시간 부드러운 패닝 (★오차 없는 하드 패닝 적용)
            global_start = i * N
            global_end = (i + 1) * N
            
            # 정확히 0.0에서 시작해 1.0을 넘지 않도록 배열 생성
            pan_array = np.linspace(global_start / total_samples, global_end / total_samples, N, False)
            
            # 혹시 모를 부동소수점 오차를 막기 위해 값을 0.0 ~ 1.0 사이로 완벽히 가둠 (Clamp)
            pan_array = np.clip(pan_array, 0.0, 1.0)
            
            # 등전력 패닝(Equal Power Panning)에 배열을 적용합니다.
            left_wave = wave * np.cos(pan_array * np.pi / 2)
            right_wave = wave * np.sin(pan_array * np.pi / 2)
            
            left_channel.extend(left_wave)
            right_channel.extend(right_wave)

        # 3. 배열 합치기 및 오디오 파일로 변환
        audio_stereo = np.vstack((left_channel, right_channel)).T
        
        # 값이 너무 작아서 0으로 나누어지는 오류 방지를 위해 1e-9(아주 작은 값)를 더해줍니다.
        audio_stereo = np.int16(audio_stereo / (np.max(np.abs(audio_stereo)) + 1e-9) * 32767)
        
        virtual_file = io.BytesIO()
        write(virtual_file, sample_rate, audio_stereo)
        
        # 웹 화면에 현재 열의 오디오 플레이어를 띄웁니다.
        st.audio(virtual_file, format='audio/wav')