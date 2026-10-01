# 피타고라스: 시계열 그래프 공간음향

시각장애인이 시계열 그래프, 특히 주식 차트의 흐름을 청각과 공간 위치로 이해할 수 있도록 돕는 접근성 프로토타입입니다.

핵심 표현은 다음 세 가지를 한 스테레오 신호로 결합하는 것입니다.

- 주 그래프의 Y값(주가) → Pitch
- 보조 그래프의 값(거래량) → Volume/Amplitude
- 시간의 흐름 → 왼쪽에서 오른쪽으로 이동하는 Stereo Panning

가격이 상승하고 거래량이 증가하는 데이터는 왼쪽에서 오른쪽으로 이동하면서 음높이와 음량이 함께 올라갑니다. 주식은 대표 적용 사례이며 같은 엔진을 온도, 센서, 매출 등 다른 시계열 데이터에도 사용할 수 있습니다.

## 현재 기능

- 지수 주파수 매핑과 Continuous Phase 기반 Pitch 생성
- 거래량 `log1p` 정규화, 극단값 완화, Amplitude smoothing
- Constant Power Stereo Panning
- 최소·최대 Pitch와 Amplitude 설정
- CSV의 시간·주 데이터·보조 데이터 열 자동 감지 및 직접 선택
- 주식 캔들의 종가와 거래량을 결합한 공간음향
- 재생, 일시정지, 처음부터, 이전·다음 구간, 재생 속도, 전체 음량 조절
- 현재 위치·가격·거래량·속도 TTS 안내
- 키보드 조작, 스크린리더 레이블, 고대비 모드
- 기존 그래프 이미지 분석과 가격 전용 가청화

## 코드 구조

- `spatial_audio.py`: Pitch, Amplitude, Panning 통합 엔진
- `engine.py`: 기존 이미지 분석과 이전 오디오 API 호환 래퍼
- `server.py`: FastAPI 및 `/sonify-spatial` API
- `index.html`, `app.js`, `style.css`: 접근성 웹 UI
- `stock_service.py`: 주식 캔들 데이터 어댑터와 샘플 데이터
- `spatial_audio_test.py`, `stock_test.py`: 오디오·주식 연결 테스트

현재 실행 구조는 Streamlit이 아니라 FastAPI 백엔드와 정적 웹 프론트엔드입니다.

## CSV 형식

권장 형식은 다음과 같습니다.

```csv
timestamp,price,volume
2026-10-01 09:00,72000,100000
2026-10-01 09:01,72100,115000
2026-10-01 09:02,71900,98000
```

`stock_spatial_sample.csv`를 바로 사용할 수 있습니다. 열 이름이 다르면 업로드 후 시간, 주 데이터(Pitch), 보조 데이터(Volume) 열을 직접 선택합니다. 보조 열을 선택하지 않으면 일정한 중간 음량으로 재생합니다.

## 실행 방법

```bash
pip install -r requirements.txt
python -m uvicorn server:app --reload --port 8001
```

별도 터미널에서 웹 서버를 실행합니다.

```bash
python -m http.server 5500
```

브라우저에서 `http://127.0.0.1:5500`을 엽니다. API 문서는 `http://127.0.0.1:8001/docs`에서 확인할 수 있습니다.

## 공간음향 API

`POST /sonify-spatial`

```json
{
  "timestamps": ["09:00", "09:01", "09:02"],
  "prices": [72000, 72100, 71900],
  "volumes": [100000, 115000, 98000],
  "min_frequency": 200,
  "max_frequency": 800,
  "min_amplitude": 0.15,
  "max_amplitude": 0.85,
  "duration_seconds": 8,
  "waveform": "sine"
}
```

기존 `POST /sonify-data`와 `generate_stereo_sound()`는 거래량이 없는 이미지 및 이전 호출과의 호환을 위해 유지합니다.

## 키보드 조작

- `Space`: 재생 또는 일시정지
- `Home`: 처음부터 재생
- `J`, `K`: 이전 또는 다음 구간
- `[`, `]`: 재생 속도 감소 또는 증가
- `P`: 현재 위치, 주 데이터, 보조 데이터, 속도 읽기
- `/`: 종목 검색으로 이동
- `L`: 실시간 종목 조회
- `I`: 그래프 이미지 선택
- `A`: 그래프 이미지 분석
- `Esc`: 모든 소리 정지

입력 필드나 선택 상자를 조작하는 동안 전역 단축키는 실행되지 않습니다.

## 테스트

```bash
python -m unittest spatial_audio_test stock_test -v
```

테스트는 가격과 주파수의 방향, 로그 기반 거래량 정규화, Constant Power Panning, 채널별 에너지, 거래량에 따른 음량 차이, 정렬되지 않은 입력 거부, 기존 주식 데이터 연결을 확인합니다.

## 주식 API 설정

실제 API는 선택 사항입니다. 인증정보는 저장소에 저장하지 않고 환경변수로만 설정합니다.

```powershell
$env:TOSSINVEST_CLIENT_ID="발급받은_client_id"
$env:TOSSINVEST_CLIENT_SECRET="발급받은_client_secret"
```

인증정보 없이도 UI의 `샘플로 체험`과 `stock_spatial_sample.csv`로 전체 공간음향 흐름을 시험할 수 있습니다.

## 다음 단계

1. 스크린리더 사용자 테스트를 통한 단축키와 TTS 문장 개선
2. 종목 검색 범위와 봉 간격 확대
3. 실시간 데이터 갱신 시 기존 재생 위치를 유지하는 스트리밍
4. 여러 보조 차트의 음색 분리와 선택 재생
5. 그래프 이미지에서 가격 영역과 거래량 영역을 함께 추출

## Team

Team Pythagoras

- Hwang Soo-young (Team Leader)
- Park Soo-hyun
- Kim Tae-hyun

Advisor: Professor Yoo Ju-han, Dong-A University
