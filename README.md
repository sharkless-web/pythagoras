# 피타고라스 — 듣고 탐색하는 주식 차트

시각장애인이 시계열 흐름과 특정 봉의 수치를 청각으로 탐색하는 프로토타입입니다.
종가 → Pitch, 거래량 → Amplitude, 시간 → Stereo Panning, 정확한 OHLCV → 텍스트·스크린리더·선택적 TTS로 표현합니다.

## 실행

```bash
python -m pip install -r requirements.txt
python -m uvicorn server:app --reload --host 127.0.0.1 --port 8001
```

웹 UI: http://127.0.0.1:8001 / API 문서: http://127.0.0.1:8001/docs
FastAPI가 웹 파일과 API를 함께 제공합니다. 현재 Streamlit 실행 진입점은 없습니다.

## 사용 순서

1. 종목 검색에 이름 또는 코드를 입력합니다. ↑↓로 결과를 이동하고 Enter로 선택합니다. 검색은 현재 등록 종목을 대상으로 하며, 결과가 없는 종목은 코드를 직접 입력할 수 있습니다.
2. 처음 화면의 실시간 종목 순위에서 종목을 바로 선택하거나 검색합니다. Tab으로 봉 간격(1·5·15·60분봉/일봉), 조회 기간을 선택하고 **차트 불러오기**를 실행합니다. 순위는 1분마다 갱신하고, 선택한 실데이터 차트도 재생 중이 아닐 때 1분마다 새 봉을 확인합니다. 필요하면 **현재 차트 새로고침**을 누릅니다.
3. 로딩 완료 안내 후 재생 버튼에 초점이 이동합니다. 재생 → 일시정지 → 정지 → 현재 위치 순으로 Tab 이동합니다.
4. 재생 영역에서 Space로 재생/일시정지, 좌우 방향키로 봉 탐색, Home/End로 처음/끝을 탐색합니다. P는 현재 봉, D는 상세 OHLCV 읽기입니다.
5. **요약 음성으로 읽기**는 Enter·Space·클릭 모두 지원합니다. 자동 음성 안내를 꺼도 명시적인 읽기 버튼은 한국어 음성을 실행합니다. 요약 텍스트와 live region은 별도로 유지합니다.
6. 구간 재생·반복은 상세 영역을 펼쳐 사용합니다. 시장 순위는 접지 않고 표시하며 그래프 이미지 분석은 보조 영역에 유지됩니다.
7. **사용 환경 설정으로 이동** 링크로 Sidebar에 접근합니다. Pitch·Amplitude·전체 음량·속도·파형·고대비·자동 음성·단축키 도움말을 설정하고, Sidebar의 **공간음향 재생기** 링크로 본문에 돌아옵니다.

PC에서는 왼쪽 Sidebar와 오른쪽 Main으로 표시합니다. 좁은 화면에서는 Main 뒤에 설정 패널이 배치됩니다. DOM과 Tab 순서는 항상 Main → Sidebar이며 양수 tabindex를 사용하지 않습니다.

### 음성 안내

`tts.js`의 SpeechController가 모든 읽기 기능을 관리합니다. 이전 발화를 cancel하고 한국어 음성을 선택한 뒤 사용자 입력 이벤트 안에서 speak를 호출합니다. onstart/onend/onerror로 상태를 표시하며, 실패 원인은 콘솔의 `[TTS]` 로그로 확인합니다. 음성 시작이 지연되면 재시도 안내를 표시합니다. 한국어 음성과 브라우저 소리 출력이 사용 가능한 환경이 필요합니다.

자동 음성은 스크린리더 이중 낭독을 피하기 위해 기본 꺼짐입니다. 이 설정은 탐색 자동 안내에만 적용됩니다. 읽기 버튼은 항상 음성을 요청합니다. 현재 위치 텍스트는 계속 갱신하되 재생 중 매 프레임 자동 낭독하지 않습니다. 실제 NVDA/JAWS/VoiceOver 조합의 낭독 품질은 사용자 평가가 필요합니다.

CSV 업로드·샘플·다운로드는 사용자 화면과 공개 API에서 제거했습니다. `CSVProvider`와 `samples/`는 내부 회귀 테스트 자료입니다.

## 음향 해석

Trend 모드는 **전체 불러온 차트**의 종가 최저/최고를 기본 200~800Hz에 지수 매핑합니다. 작은 실제 등락도 크게 들릴 수 있으므로 변화율은 수치 안내와 함께 확인합니다. `mapping_mode` 경계는 확장 가능하며 현재 `trend`만 지원합니다. Change 모드는 후속 과제입니다.

거래량은 log1p → 5/95 백분위 클리핑 → 정규화 → 기본 0.25~0.85 진폭으로 매핑합니다. 백분위 범위가 같은 값으로 붕괴하면 전체 범위를 사용해 고립된 급증을 보존합니다. 모두 같은 거래량은 중간 진폭입니다. 가격·거래량은 보간하고 진폭은 25ms 평활화, 양 끝은 12ms fade를 적용합니다. 위상을 누적하므로 봉 경계에서 위상이 리셋되지 않습니다.

시간은 일정 전력 패닝으로 표현합니다. 봉 인덱스 간격을 동일하게 취급하며 휴장 시간은 늘리지 않습니다. 구간을 들어도 전체 차트 기준 음높이·진폭·좌우 위치가 유지됩니다. 선택한 범위의 기본 재생 길이는 8초입니다. 속도 0.5/0.75/1/1.25/1.5/2배는 WAV 길이를 재생성하며 주파수를 바꾸지 않습니다. 설정 변경은 재생을 일시정지하고 현재 위치를 유지합니다.

## 기존 기능

- 토스증권 실시간 시장 순위·종목 검색·캔들 조회를 기본 흐름으로 사용합니다. 공식 캔들 API는 1분봉과 일봉만 제공하므로 5·15·60분봉은 페이지를 넘겨 가져온 실제 1분봉 OHLCV를 해당 구간으로 합산합니다. 시가=첫 봉, 고가=최고, 저가=최저, 종가=마지막 봉, 거래량=합계입니다. 합산 봉은 최대 30개까지 조회합니다. 차트 자동 확인은 1분 주기 폴링이며 체결 단위 스트리밍은 아닙니다. 화면에 최근 봉 시각을 표시하므로 장 마감 시 오래된 데이터를 실시간 가격으로 오인하지 않도록 합니다.
- 인증은 서버 환경변수 `TOSSINVEST_CLIENT_ID`, `TOSSINVEST_CLIENT_SECRET`만 사용합니다. 키를 코드·CSV·브라우저에 넣지 않습니다.
- 거래량이 누락된 기존 API 응답은 가격 전용 음향으로 유지하되 OHLCV 구간 생성은 제공하지 않습니다.
- 그래프 이미지 분석은 보조 도구입니다. 기존 HSV/선·캔들 추출·보간·신뢰도 설명을 유지합니다. 영역을 지정하지 않으면 자동 분석하고, 필요하면 X/Y/너비/높이를 원본 픽셀로 입력해 키보드로 영역을 적용할 수 있습니다. 영역 초기화는 자동 분석으로 복귀합니다.
- 이미지에서 추출한 값은 상대 높이입니다. 실제 통화·OHLCV로 오인해서 안내하지 않습니다.

## 코드 구조 및 API

- `chart_data.py`: Candle, ChartData 검증, CSVProvider, ExistingStockProvider, 전체 요약.
- `stock_service.py`: 토스증권 캔들·시장 순위 공급자 및 1분봉 합산 (샘플 공급자 호환 유지).
- `spatial_audio.py`: 정규화·Pitch·Amplitude·패닝·통합 WAV 엔진.
- `engine.py`: 기존 이미지 분석 및 가격 전용 오디오 호환 래퍼.
- `server.py`: FastAPI 및 공개 웹 파일 허용 목록.
- `navigator.js`: 순수 탐색 상태와 구간 계산, `app.js`: 기존 차트·음향·키보드 UI, `workspace.js`: 검색 combobox·조회 기간·이미지 ROI. `tts.js`: 공통 한국어 음성 큐.
- `index.html`, `style.css`: 순서대로 탐색하는 시맨틱 화면·고대비.

`POST /sonify-stock`: JSON symbol, timeframe, candles와 선택적 min_frequency, max_frequency, min_amplitude, max_amplitude, duration_seconds, waveform, start_index, end_index. 인덱스는 0부터 시작하며 끝 봉을 포함합니다. WAV 반환.

기존 `/sonify-data`, `/sonify-spatial`, `/stock-candles`, `/stock-rankings`, `/stock-search`, `/analyze-graph-image`는 유지합니다. `/stock-candles`에는 거래량이 있는 경우 검증된 chart/summary도 제공합니다. 웹 서버는 저장소 전체를 공개하지 않으며 HTML/JS/CSS만 제공합니다.

## 검증

```bash
python -m pip install -r requirements-dev.txt
python -m unittest spatial_audio_test stock_test chart_test -v
node --test navigator.test.js tts.test.js
node --check app.js
node --check workspace.js
```

25개 Python 테스트와 5개 Navigator·TTS 테스트(총 30개): CSV 별칭·수동 열·범위 오류·중복·빈 데이터·NaN, 단일 봉, 음높이·진폭·좌우 전력, 구간 주파수 보존, 속도 변경 시 주파수 보존, API 호환 및 비공개 파일 차단, 합성 선 이미지 분석을 검증합니다.

키보드 수동 점검: 종목 검색 → 방향키/Enter 선택 → 봉 간격 → 기간 → 차트 불러오기 → 재생 영역 → Space → 방향키 → D → Home/End → 속도 버튼 → 구간 적용 → 반복 → Escape. 브라우저 보조 음성 꺼짐/켜짐과 고대비도 확인합니다. 실제 NVDA/JAWS 낭독 품질, 스크린리더별 단축키 충돌, 청취 이해도·피로도는 실제 사용자 평가가 필요합니다.

세부 분석과 단계별 변경 사항은 `IMPLEMENTATION_REPORT.md`에 기록했습니다.

## 팀 공유

기존처럼 로컬 서버에 Cloudflare Quick Tunnel을 연결할 수 있습니다.

```bash
cloudflared tunnel --url http://127.0.0.1:8001
```

프로세스와 PC가 켜진 동안만 접속할 수 있으며 재시작 시 주소가 바뀔 수 있습니다. 토스 API는 서버 PC의 허용 IP·환경변수를 사용합니다. 이번 작업은 로컬 개발 브랜치에서 검증하며 별도 배포를 수행하지 않습니다.
