from gtts import gTTS
import os

# 태현님이 필요한 멘트들을 여기 정의합니다.
# "파일이름": "실제 나올 목소리"
voice_messages = {
    "intro_3.mp3": "총 세 개의 그래프를 불러들였습니다.",
    "step_1.mp3": "먼저 첫 번째 그래프입니다.",
    "step_2.mp3": "이어서 두 번째 그래프입니다.",
    "step_3.mp3": "마지막 세 번째 그래프입니다.",
    "finish.mp3": "모든 그래프를 표현하였습니다."
}

print("🔊 음성 파일 제작 중... 잠시만 기다려주세요.")

for filename, text in voice_messages.items():
    # 구글 TTS 엔진을 사용해 목소리 생성
    tts = gTTS(text=text, lang='ko')
    # 현재 폴더에 mp3 파일로 저장
    tts.save(filename)
    print(f"✅ 생성 완료: {filename}")

print("\n✨ 모든 음성 파일이 준비되었습니다! 이제 폴더를 확인해보세요.")