/**
 * Project Pythagoras: Keyboard Shortcut System
 * - U: 파일 업로드 창 열기 (한/영 무관)
 * - Space: 모든 소리 일시 정지 (유령 클릭 방지)
 * - 1~9: 해당 순서의 데이터 가청화 재생 (한/영 무관)
 */

// 스트림릿 리로드 시 중복 등록 방지
if (!window.parent.hasPythagorasShortcut) {
    const doc = window.parent.document;

    doc.addEventListener('keydown', function(e) {
        
        // 1. 시스템 단축키(Cmd+R, Cmd+C 등)는 통과
        if (e.metaKey || e.ctrlKey || e.altKey) return;

        // 2. 현재 포커스 상태 확인 (입력창에서는 단축키 비활성화)
        const active = doc.activeElement;
        const activeTag = active.tagName.toLowerCase();
        const activeType = active.type;
        const isTextInput = activeTag === 'textarea' || (activeTag === 'input' && (activeType === 'text' || activeType === 'number'));
        
        if (isTextInput) return;

        // 3. 물리적 키 코드 정의 (한글 'ㅕ' 상태에서도 작동하게 e.code 사용)
        const isUKey = e.code === 'KeyU';
        const isDigitKey = e.code.startsWith('Digit') && e.code.length === 6; // Digit1 ~ Digit9
        const isSpaceKey = e.code === 'Space';

        // 4. 단축키 입력 시 기존 버튼 포커스 해제 (스페이스바 유령 클릭 방지)
        if (isUKey || isDigitKey || isSpaceKey) {
            if (active && typeof active.blur === 'function') {
                active.blur();
            }
        }

        // ==========================================
        // 기능 1: [ U ] 키 - 파일 업로드 창 열기
        // ==========================================
        if (isUKey) {
            e.preventDefault();
            e.stopPropagation();
            
            // 스트림릿의 실제 파일 입력 노드를 찾아 클릭 이벤트를 보냅니다.
            const fileInput = doc.querySelector('input[type="file"]');
            if (fileInput) {
                fileInput.click();
            }
            return;
        }

        // ==========================================
        // 기능 2: [ Space ] 키 - 모든 소리 정지
        // ==========================================
        if (isSpaceKey) {
            e.preventDefault();
            e.stopPropagation();
            
            const audios = doc.querySelectorAll('audio');
            audios.forEach(a => {
                a.pause();
                // a.currentTime = 0; // 필요시 처음으로 되감기 추가 가능
            });
            return; 
        }

        // ==========================================
        // 기능 3: [ 1 ~ 9 ] 키 - 데이터 가청화 재생
        // ==========================================
        if (isDigitKey) {
            const numStr = e.code.replace('Digit', ''); // 'Digit1'에서 숫자만 추출
            const index = parseInt(numStr) - 1; 
            const audioElements = doc.querySelectorAll('audio');
            
            if (audioElements.length > index) {
                e.preventDefault();  
                e.stopPropagation(); 
                
                // 선택한 오디오 재생 (이미 재생 중이면 처음부터 다시)
                audioElements[index].pause();      
                audioElements[index].currentTime = 0; 
                audioElements[index].play();       
            }
        }
    });
    
    // 등록 완료 플래그 세우기
    window.parent.hasPythagorasShortcut = true; 
    console.log("🚀 [Pythagoras] 단축키 시스템 로드 완료 (한/영 대응 버전)");
}