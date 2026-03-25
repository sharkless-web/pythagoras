/* script.js */
const doc = window.parent.document;

doc.addEventListener('keydown', function(e) {
    // 1. Space 키 -> 재생 버튼 클릭
    if (e.code === 'Space') {
        e.preventDefault(); // 페이지 스크롤 방지
        const playBtn = Array.from(doc.querySelectorAll('button')).find(el => 
            el.innerText.includes('재생') || el.innerText.includes('Space')
        );
        if (playBtn) playBtn.click();
    } 
    
    // 2. R 키 -> 다시 재생 버튼 클릭
    else if (e.key.toLowerCase() === 'r') {
        const replayBtn = Array.from(doc.querySelectorAll('button')).find(el => 
            el.innerText.includes('다시') || el.innerText.includes('R')
        );
        if (replayBtn) replayBtn.click();
    } 
    
    // 3. U 키 -> 파일 업로드 창 열기
    else if (e.key.toLowerCase() === 'u', 'ㅕ') {
        const uploadInput = doc.querySelector('input[type="file"]');
        if (uploadInput) uploadInput.click();
    }
});