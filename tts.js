/* One speech queue for every explicit read action and optional automatic prompt. */
class SpeechController {
    constructor(synth, Utterance, status) {
        this.synth = synth; this.Utterance = Utterance; this.status = status;
        this.generation = 0; this.current = null; this.voices = [];
        this.refreshVoices = () => { this.voices = this.synth?.getVoices() || []; };
        this.refreshVoices();
        this.synth?.addEventListener('voiceschanged', this.refreshVoices);
    }
    cancel() {
        this.generation++;
        clearTimeout(this.timer);
        this.synth?.cancel(); this.current = null;
    }
    speak(text) {
        this.cancel();
        if (!text?.trim()) { this.status('읽을 내용이 없습니다.', 'empty'); return; }
        if (!this.synth || !this.Utterance) { this.status('이 브라우저는 음성 합성을 지원하지 않습니다. 화면 텍스트를 스크린리더로 읽어주세요.', 'unsupported'); return; }
        this.refreshVoices();
        const id = this.generation;
        const utterance = new this.Utterance(text);
        utterance.lang = 'ko-KR'; utterance.rate = 1; utterance.volume = 1;
        const korean = this.voices.find(v => /^ko(?:-|_)/i.test(v.lang));
        if (korean) utterance.voice = korean;
        this.current = utterance; // Retain reference for browsers which collect utterances early.
        const update = (text, state) => { if (id === this.generation) this.status(text, state); };
        utterance.onstart = () => { clearTimeout(this.timer); update('한국어 음성 안내 중', 'speaking'); };
        utterance.onend = () => { clearTimeout(this.timer); if (id === this.generation) this.current = null; update('음성 안내 완료', 'complete'); };
        utterance.onerror = event => {
            if (id !== this.generation) return;
            clearTimeout(this.timer);
            console.error('[TTS]', event.error);
            update(`음성 재생 실패 (${event.error}). 한국어 음성 설치와 브라우저 소리 설정을 확인하세요.`, 'error');
        };
        update('한국어 음성 준비 중', 'pending');
        this.timer = setTimeout(() => update('음성 시작이 지연됩니다. 읽기 버튼을 다시 누르거나 한국어 음성 설정을 확인하세요.', 'delayed'), 8000);
        try {
            this.synth.resume();
            this.synth.speak(utterance); // Synchronous in the user click/keypress activation.
        } catch (error) {
            clearTimeout(this.timer); console.error('[TTS]', error);
            update('음성을 시작하지 못했습니다. 화면 텍스트는 계속 사용할 수 있습니다.', 'error');
        }
    }
}
if (typeof module !== 'undefined') module.exports = { SpeechController };
