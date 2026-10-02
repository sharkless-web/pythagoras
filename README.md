# 피타고라스: 주식 차트 공간음향

시각장애인이 주식 차트의 흐름을 청각과 공간 위치로 이해할 수 있도록 돕는 접근성 프로토타입입니다.

핵심 표현은 다음 세 요소를 하나의 스테레오 신호로 결합하는 것입니다.

- 종가 → Pitch
- 거래량 → Volume/Amplitude
- 시간 → 왼쪽에서 오른쪽으로 이동하는 Stereo Panning

가격이 상승하고 거래량이 증가하면 소리가 왼쪽에서 오른쪽으로 이동하면서 음높이와 음량이 함께 올라갑니다. 정확한 OHLCV 수치는 공간음향 재생 위치와 연결된 TTS로 확인합니다.

## 사용자 흐름

1. 종목명 또는 코드를 입력하고 봉 간격과 개수를 선택합니다.
2. 최근 종가, 구간 변화, 최고·최저와 차트 요약을 확인합니다.
3. 종가·거래량·시간을 결합한 공간음향을 재생합니다.
4. 이전·다음 구간으로 이동하거나 현재 위치의 종가와 거래량을 TTS로 듣습니다.

보조 도구로 선 그래프와 주식 캔들 차트 이미지 분석을 제공합니다.

## 현재 기능

- 토스증권 1분봉·일봉 OHLCV 조회
- 실제 OHLC 캔들, 5봉·20봉 이동평균과 거래량 차트
- 인증정보 없는 환경을 위한 명시적 샘플 체험
- Continuous Phase 기반 Pitch 생성
- 거래량 `log1p` 정규화와 Amplitude smoothing
- Constant Power Stereo Panning
- 최소·최대 Pitch와 Amplitude 설정
- 재생, 일시정지, 처음부터, 이전·다음 구간, 속도와 전체 음량 조절
- 현재 위치·OHLCV·속도 TTS와 안내 후 재생 복귀
- 키보드 조작, 스크린리더 레이블, 고대비 모드
- 그래프 이미지 분석과 가격 전용 가청화

## 코드 구조

- `spatial_audio.py`: Pitch, Amplitude, Panning 통합 엔진
- `stock_service.py`: 토스증권 캔들 데이터와 샘플 데이터 어댑터
- `engine.py`: 그래프 이미지 분석과 가격 전용 오디오 호환 기능
- `server.py`: FastAPI, 주식 데이터, 공간음향, 이미지 분석 API
- `index.html`, `app.js`, `style.css`: 접근성 웹 UI
- `spatial_audio_test.py`, `stock_test.py`: 엔진과 주식 연결 테스트

현재 실행 구조는 FastAPI 백엔드와 정적 웹 프론트엔드입니다.

## 실행 방법

```bash
pip install -r requirements.txt
python -m uvicorn server:app --reload --port 8001
```

별도 터미널에서 웹 서버를 실행합니다.

```bash
python -m http.server 5500
```

- 웹 UI: `http://127.0.0.1:5500`
- API 문서: `http://127.0.0.1:8001/docs`

## 주식 API 설정

인증정보는 저장소에 저장하지 않고 환경변수로 설정합니다.

```powershell
$env:TOSSINVEST_CLIENT_ID="발급받은_client_id"
$env:TOSSINVEST_CLIENT_SECRET="발급받은_client_secret"
```

영구 사용자 환경변수로 저장하려면 새 PowerShell에서 다음 형식을 사용합니다.

```powershell
[Environment]::SetEnvironmentVariable("TOSSINVEST_CLIENT_ID", "발급받은_client_id", "User")
[Environment]::SetEnvironmentVariable("TOSSINVEST_CLIENT_SECRET", "발급받은_client_secret", "User")
```

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

## 키보드 조작

- `/`: 종목 검색으로 이동
- `L`: 실시간 종목 조회
- `Space`: 재생 또는 일시정지
- `←`, `→`: 한 봉씩 이동
- `Home`, `End`: 처음 또는 마지막 봉으로 이동
- `J`, `K`: 이전 또는 다음 구간
- `R`: 처음부터 재생
- `[`, `]`: 재생 속도 감소 또는 증가
- `P`: 현재 위치, 종가, 거래량, 속도 읽기
- `I`: 그래프 이미지 선택
- `A`: 그래프 이미지 분석
- `Esc`: 모든 소리 정지

입력 필드나 선택 상자를 조작하는 동안 전역 단축키는 실행되지 않습니다.

## 테스트

```bash
python -m unittest spatial_audio_test stock_test -v
```

## 다음 개선 우선순위

제품 목표, 범위, 성공 지표와 단계별 개발 순서는 [`PRODUCT_ROADMAP.md`](PRODUCT_ROADMAP.md)에 정리되어 있습니다.

1. 가격 변화 폭을 더 구분하기 위한 기준가·등락률 기반 Pitch 모드
2. 거래량 급증을 구별하는 선택형 보조 음색 또는 짧은 신호
3. 장중 구간을 개장·중간·마감으로 빠르게 이동하는 구조 탐색
4. 종목 비교가 아닌 한 종목의 여러 기간을 전환하는 차트 탐색
5. 실제 스크린리더 사용자 평가와 단축키 조정

## Team

Team Pythagoras

- Hwang Soo-young (Team Leader)
- Park Soo-hyun
- Kim Tae-hyun

Advisor: Professor Yoo Ju-han, Dong-A University
