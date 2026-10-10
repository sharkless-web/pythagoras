# 종목 중심 UI/UX 수정 기록

## CSV UI
업로드·열 선택·분석·샘플 버튼·다운로드·설명을 제거했다. 공개 CSV API와 샘플 파일 라우트도 제거했다. CSVProvider, 합성 CSV 및 회귀 테스트는 내부에 유지한다.

## Sidebar
Main 밖의 aside를 왼쪽으로 배치했다. DOM은 Main 뒤에 두어 핵심 작업을 먼저 탐색한다. Pitch, 거래량 음량, 전체 음량, 속도, 파형, 고대비, 자동 음성, 설정 읽기와 단축키 도움말을 모았다. 좁은 화면에서는 Main 뒤 설정 패널로 표시한다.

## Main UI
검색 → 결과 선택 → 봉 간격 → 조회 기간 → 불러오기 → 현재 종목/차트 → 재생/일시정지/정지 → 현재 위치 → 상세·요약 순서. 반복 구간·시장 순위·이미지 분석은 상세 보조 영역으로 유지했다. 조회 기간은 실제 API가 지원하는 최근 N봉/거래일로 명시한다.

## Accessibility
combobox/listbox/option, aria-expanded/activedescendant/selected로 검색 결과를 표현한다. 포커스는 입력에 유지하고 방향키와 Enter로 선택한다. Tab 기본 순서를 유지하고 양수 tabindex를 쓰지 않는다. 로딩 후 재생 버튼, 오류 시 불러오기 버튼으로 초점을 이동한다. 요약과 상태에 live region, 현재 위치에 aria-valuetext를 제공한다. 단축키는 입력 컨트롤·버튼의 기본 동작을 보존한다. 본문/설정 사이 이동 링크와 큰 포커스 표시를 제공한다.

## TTS Bug
요약 click handler와 텍스트 생성은 존재했지만 speakText가 기본 꺼진 speechToggle을 확인하고 return했다. 이 때문에 직접 읽기 요청도 음성이 차단되었다.

## TTS Fix
명시적 읽기와 선택적 자동 안내를 분리했다. SpeechController는 cancel → ko-KR utterance → 한국어 voice 선택 → resume/speak를 사용자 이벤트 안에서 실행한다. utterance 참조를 유지하며 이전 발화의 늦은 이벤트를 무시한다. 시작/완료/오류/지연 상태를 표시하고 오류를 console.error로 기록한다. 화면 텍스트는 음성 지원과 무관하게 유지한다.

## Modified Files
index.html, style.css, app.js, workspace.js, tts.js, server.py, chart_test.py, tts.test.js, README.md, PRODUCT_ROADMAP.md, UX_ACCESSIBILITY_REPORT.md.

## Test Result
Python 23개, Node 5개 회귀 테스트. 실제 토스 데이터로 삼성전자 검색·선택, 일봉과 60거래일 선택, 불러오기 성공. 요약 버튼은 자동 안내 꺼짐에서도 Enter/Space로 한국어 음성 시작과 정상 종료 이벤트를 발생시킨다. 재생→일시정지→정지→위치 Tab 순서, 봉 탐색, 설정 링크 왕복도 검증했다. 실제 스크린리더 사용자 평가와 물리 스피커 직접 청취는 별도 검증이다.
