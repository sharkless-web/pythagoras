/**
 * Project Pythagoras: Keyboard Shortcut & TTS System
 * - U: 파일 업로드 창 열기 
 * - Space: 모든 소리 및 TTS 일시 정지
 * - 1~9: 해당 순서의 음성 안내 + 가청화 재생 (CSV 탭 전용)
 * - [New] 탭 전환 시 모든 소리 자동 정지
 */

if (!window.parent.hasPythagorasShortcut) {
    const doc = window.parent.document;

    const getIframeElements = (selector) => {
        let elements = [];
        const iframes = doc.querySelectorAll('iframe');
        iframes.forEach(iframe => {
            try {
                const innerDoc = iframe.contentDocument || iframe.contentWindow.document;
                if (innerDoc) {
                    innerDoc.querySelectorAll(selector).forEach(el => elements.push(el));
                }
            } catch(err) {} 
        });
        return elements;
    };

    window.parent.playTTS = function(index, colName, minVal, maxVal) {
        const audios = getIframeElements(`audio#audio_${index}`);
        if (audios.length > 0) {
            const targetAudio = audios[0];
            let playPromise = targetAudio.play();
            if (playPromise !== undefined) {
                playPromise.then(() => {
                    targetAudio.pause();
                    targetAudio.currentTime = 0;
                }).catch(err => console.log("Audio pre-warming pending..."));
            }
        }

        window.speechSynthesis.cancel();

        const text = `${colName} 데이터의 최소값은 ${minVal.toFixed(2)}이고, 최대값은 ${maxVal.toFixed(2)}입니다. 이어서 재생을 시작합니다.`;
        const msg = new SpeechSynthesisUtterance(text);
        msg.lang = 'ko-KR';
        msg.rate = 1.1;

        const voices = window.speechSynthesis.getVoices();
        const maleVoice = voices.find(v => v.lang.includes('ko') && (v.name.includes('Male') || v.name.includes('남성')));
        if (maleVoice) {
            msg.voice = maleVoice;
        }

        msg.onend = function() {
            if (audios.length > 0) {
                audios[0].play();
            }
        };

        window.parent.currentTTS = msg; 
        window.speechSynthesis.speak(msg);
    };

    // --- [추가된 기능] 탭 전환 감지 및 오디오 자동 정지 ---
    doc.addEventListener('click', function(e) {
        // 스트림릿의 탭 버튼을 다양한 속성으로 넓게 감지합니다.
        const tabButton = e.target.closest('[data-baseweb="tab"], [data-testid="stTab"], button[role="tab"]');
        
        // 탭 영역이 클릭되었다면 조건 없이 즉시 모든 소리를 차단합니다.
        if (tabButton) {
            window.speechSynthesis.cancel(); // TTS 즉시 정지
            
            // 모든 iframe 내부의 오디오 정지
            const audios = getIframeElements('audio');
            audios.forEach(a => {
                a.pause();
                a.currentTime = 0;
            });
            console.log("탭 이동 감지: 오디오 및 TTS 강제 종료");
        }
    });
    // --- 키보드 이벤트 리스너 ---
    doc.addEventListener('keydown', function(e) {
        if (e.metaKey || e.ctrlKey || e.altKey) return;

        const active = doc.activeElement;
        const activeTag = active.tagName.toLowerCase();
        const activeType = active.type;
        const isTextInput = activeTag === 'textarea' || (activeTag === 'input' && (activeType === 'text' || activeType === 'number'));
        
        if (isTextInput) return;

        const isUKey = e.code === 'KeyU';
        const isDigitKey = e.code.startsWith('Digit') && e.code.length === 6; 
        const isSpaceKey = e.code === 'Space';

        if (isUKey || isDigitKey || isSpaceKey) {
            if (active && typeof active.blur === 'function') active.blur();
        }

        if (isUKey) {
            e.preventDefault(); e.stopPropagation();
            const fileInput = doc.querySelector('input[type="file"]');
            if (fileInput) fileInput.click();
            return;
        }

        if (isSpaceKey) {
            e.preventDefault(); e.stopPropagation();
            window.speechSynthesis.cancel(); 
            
            const audios = getIframeElements('audio');
            audios.forEach(a => {
                a.pause();
                a.currentTime = 0;
            });
            return; 
        }

        if (isDigitKey) {
            const activeTab = doc.querySelector('.stTabs [aria-selected="true"]');
            const isCsvTabActive = activeTab && activeTab.textContent.includes('CSV');
            
            if (!isCsvTabActive) {
                return; 
            }

            const index = parseInt(e.code.replace('Digit', '')) - 1; 
            const ttsButtons = getIframeElements(`button#tts_btn_${index}`);
            
            if (ttsButtons.length > 0) {
                e.preventDefault();  
                e.stopPropagation(); 
                ttsButtons[0].click(); 
            }
        }
    });
    
    window.parent.hasPythagorasShortcut = true; 
    console.log("🚀 [Pythagoras] 단축키 로드 완료 (탭 전환 시 오디오 정지 적용)");
}