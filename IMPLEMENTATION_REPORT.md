# OHLCV 접근성 구현 기록

> 이전 작업 기록입니다. 최신 UI는 CSV 사용자 화면을 제거한 종목 중심 흐름이며, UX_ACCESSIBILITY_REPORT.md를 참조하세요.

기준: 로컬 main c74b472에서 feature/ohlcv-accessibility로 분기. 기존 main은 변경하지 않음.

## 구조와 데이터 흐름

CSVProvider 또는 ExistingStockProvider → ChartData → FastAPI → 차트·Navigator → /sonify-stock → spatial_audio → WAV. 이미지 업로드 → engine.py의 선/캔들 추출·분석 → 기존 /sonify-data → 같은 음향 엔진의 가격 전용 호환 래퍼.

기존에 구현됨: 가격/거래량 정규화, 누적 위상, 스테레오 패닝, WAV, Toss 조회, 차트, 이미지 분석, 고대비. 부분 구현: 탐색, TTS, 키보드, 재생. 새로 추가: 검증 모델, CSV, 구간 생성·반복, 독립적 live region, 수동 ROI.

## 1. 저장소 분석

- **Completed:** 기존 FastAPI+정적 UI와 이미지/음향 경로, CSV 부재, 키 충돌, 정적 파일 노출을 확인
- **Modified Files:** 문서 (분석 시 소스 변경 없음)
- **Reason:** 기존 기능을 유지하며 수정 경계를 결정
- **Test:** 기존 14개 테스트 기준 확인
- **Remaining:** Streamlit·다중 차트 혼합은 현 저장소에 없어 새로 만들지 않음

## 2. 공통 모델

- **Completed:** Candle·ChartData와 Provider 경계, 기존 stock adapter
- **Modified Files:** chart_data.py
- **Reason:** OHLCV·시간 정렬·유한 수치 검증을 중앙화
- **Test:** 잘못된 범위·NaN·중복·단일 봉·기존 stock 변환
- **Remaining:** 거래량 없는 기존 응답은 가격 전용 경로 유지

## 3. CSV

- **Completed:** 별칭 자동 감지·수동 연결·정렬·행 오류
- **Modified Files:** chart_data.py, workspace.js, samples/
- **Reason:** 같은 시점의 OHLCV를 함께 전달
- **Test:** 별칭·수동 연결·빈 데이터·음수 거래량·실제 파일 업로드
- **Remaining:** 현재 UTF-8 쉼표 CSV만 지원

## 4. Pitch

- **Completed:** Trend 모드·단일 봉·유한 주파수 검증
- **Modified Files:** spatial_audio.py
- **Reason:** 기존 연속 위상을 유지하고 구간의 음높이 의미를 고정
- **Test:** 상승 주파수·상수값 400Hz·구간 FFT
- **Remaining:** Change 모드는 확장 경계만 제공

## 5. Amplitude

- **Completed:** 기본 최소 0.25, percentile 붕괴 시 단발 급증 보존
- **Modified Files:** config.py, spatial_audio.py
- **Reason:** 작은 거래량도 들리고 고립된 급증도 보존
- **Test:** 상한/하한·로그·상수·극단값·희소 급증
- **Remaining:** 실제 사용자별 최적 음량 범위 평가 필요

## 6. Panning

- **Completed:** 기존 constant-power 유지, 구간의 전역 위치 사용
- **Modified Files:** spatial_audio.py
- **Reason:** 같은 봉이 구간마다 다른 좌우 위치로 들리지 않도록 함
- **Test:** 좌우 전력 합·중앙 단일 봉·오른쪽 끝
- **Remaining:** 실제 헤드폰 청취 이해도 평가 필요

## 7. 통합 엔진

- **Completed:** 전체 기준 정규화 후 구간 슬라이싱
- **Modified Files:** spatial_audio.py
- **Reason:** Pitch/Amplitude/Panning의 기준 통일
- **Test:** WAV 스테레오·진폭·속도별 FFT
- **Remaining:** 새 합성기나 다중 시리즈 혼합은 추가하지 않음

## 8. API

- **Completed:** /chart-csv, /sonify-stock 추가, 기존 라우트 유지
- **Modified Files:** server.py
- **Reason:** 검증된 데이터 모델과 범위 전달; 공개 파일 허용 목록
- **Test:** ASGI 통합 테스트·비공개 파일 404·호환 경로
- **Remaining:** 실제 Toss 인증 테스트는 이번 범위에서 제외

## 9. Navigator

- **Completed:** currentIndex·clamp·이전/다음·Home/End·구간 계산
- **Modified Files:** navigator.js, app.js
- **Reason:** 재생 위치와 정확한 봉 탐색을 같은 상태로 관리
- **Test:** Node 2개 테스트·브라우저 방향키/Home/End
- **Remaining:** 향후 차트상의 시각 커서 동기화 고도화

## 10. TTS와 live region

- **Completed:** 요약/상세 안내, 이전 거래일과 이전 봉 구분, 선택적 보조 음성
- **Modified Files:** app.js, index.html, workspace.js
- **Reason:** speechSynthesis가 없어도 스크린리더에 정보 제공
- **Test:** 접근성 트리·봉 텍스트·라이브 영역 확인
- **Remaining:** NVDA/JAWS 실제 낭독 검증 필요

## 11. 단축키

- **Completed:** SHORTCUTS에서 키와 도움말 생성, 버튼 Space 보존
- **Modified Files:** app.js, index.html
- **Reason:** 스크린리더·폼의 기본 키와 충돌을 줄임
- **Test:** 키보드 영역 탐색·버튼 Space로 속도 변경
- **Remaining:** 스크린리더 탐색 모드에서는 버튼 또는 포커스 모드 필요

## 12. 재생

- **Completed:** 정지·처음부터·속도·구간 적용·반복·최신 음향 요청만 적용
- **Modified Files:** app.js
- **Reason:** 구간을 다시 듣고 설정 변경 중 오래된 응답을 무시
- **Test:** 구간 5~10 생성·재생·정지, 속도 변경
- **Remaining:** 설정 변경 후 자동 재개하지 않음; 선택 범위 기본 8초

## 13. UI

- **Completed:** CSV부터 요약·재생·설정으로 탐색, 명시적 레이블·포커스
- **Modified Files:** index.html, style.css, workspace.js
- **Reason:** 마우스 없이 주요 과업 수행
- **Test:** 업로드/샘플·Tab 순서·차트/재생 화면 스크린샷
- **Remaining:** 외부 CDN 차트 로딩 실패 시 텍스트/음향은 독립 동작

## 14. 이미지

- **Completed:** 자동 분석 유지, 원본 픽셀 ROI 숫자 입력
- **Modified Files:** index.html, app.js, workspace.js
- **Reason:** 마우스 드래그 없이 분석 범위를 조절
- **Test:** 합성 선 그래프 이미지 API 회귀 테스트
- **Remaining:** 이미지 알고리즘 자체와 신뢰도 추정은 기존 수준 유지

## 15. 단위·통합 테스트

- **Completed:** 기존 14개 + 신규 9개 Python, Navigator 2개
- **Modified Files:** chart_test.py, navigator.test.js, requirements-dev.txt
- **Reason:** 입력·DSP·호환성·탐색 경계 검증
- **Test:** 23개 Python + 2개 Node 통과
- **Remaining:** 음향 의미 이해도는 기계적 검사만으로 입증 불가

## 16. 키보드 검증

- **Completed:** 실제 파일 선택→분석→요약→탐색→재생→구간·정지
- **Modified Files:** 브라우저 검증, app.js 수정
- **Reason:** 정지 상태 덮어쓰기와 설정 변경 포커스 문제 보완
- **Test:** 브라우저에서 수행; JavaScript 오류 로그 없음
- **Remaining:** 실제 시각장애인/스크린리더 사용자 테스트 필요

## 17. 문서

- **Completed:** 최신 CSV 기준 사용법·API·테스트·제약 갱신
- **Modified Files:** README.md, PRODUCT_ROADMAP.md, IMPLEMENTATION_REPORT.md
- **Reason:** 과거 CSV 제외 방침과 현재 요청 간 문서 모순 해소
- **Test:** 실행 명령과 샘플 경로 확인
- **Remaining:** 사용자 평가 후 단축키·설정 기본값 재검토

## 후속 사용자 평가

상승·하락·횡보·거래량 급증을 음향만 듣고 구분하는 정확도, 목표 봉 도달 시간, 키보드 오류 횟수, 반복 재생 필요 횟수, 청취 피로도를 측정한다. NVDA/JAWS별 모드 전환·중복 낭독·포커스 회복을 함께 검증한다. 투자 판단이나 수익률은 평가 지표로 삼지 않는다.
