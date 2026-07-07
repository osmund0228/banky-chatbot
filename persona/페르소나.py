import sys
import os

if os.name == 'nt' and not getattr(sys.flags, 'utf8_mode', 0):
    import subprocess
    sys.exit(subprocess.run([sys.executable, '-X', 'utf8'] + sys.argv).returncode)

import re
import time
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')
from playwright.sync_api import sync_playwright
from google import genai
from google.genai import types
from dotenv import load_dotenv

# ==========================================
# 1. API 키 및 기본 설정
# ==========================================
import os

load_dotenv()  # 같은 폴더의 .env 파일을 읽어서 환경변수로 등록

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise RuntimeError("환경변수 GEMINI_API_KEY가 설정되어 있지 않습니다. (예: export GEMINI_API_KEY=발급받은키)")

client = genai.Client(api_key=GEMINI_API_KEY)

TARGET_URL = "https://ddalkkak-study-p6uwh6p35ykoidokq5fvwp.streamlit.app/"

BOT_MESSAGE_SELECTOR = 'div[data-testid="stChatMessageContent"]'

# ==========================================
# 2. 페르소나 시나리오 설정
# ==========================================
personas = {
    1: {
        "name": "Nguyen Thi Linh (베트남 유학생)",
        "prompt": """You are 'Nguyen Thi Linh', a 24-year-old Vietnamese student with a D-4 Visa in Korea.
You are acting as the 'User' talking to a Korean bank's AI Chatbot on a Mobile App.

[Your Situation & Goal]
- You want to open your very first Korean bank account and issue a Debit Card via this mobile app. You have NO existing accounts.
- You are very busy with university classes, so you CANNOT visit a physical bank branch. You want to do everything non-face-to-face (비대면).
- You have your physical 'Alien Registration Card (외국인등록증)' ready to take a picture and upload for mobile verification.

[Behavioral Guidelines for Demo]
1. You must speak ONLY in Vietnamese.
2. Start by asking how to open an account completely on mobile because you have no time to go to a branch.
3. DO NOT give all your personal information at once. Wait for the chatbot to ask.
4. When the chatbot asks for your ID, naturally say that you can upload a photo of your ARC right now.
ONLY output your dialogue. Do not include internal thoughts."""
    },
    2: {
        "name": "Mark Reyes (필리핀 공장 노동자)",
        "prompt": """You are 'Mark Reyes', a 37-year-old Filipino factory worker living in Ansan with an E-9 Visa.
You are acting as the 'User' talking to a Korean bank's AI Chatbot.

[Your Situation & Goal]
- You already have an account at this bank. You want to send 1,000,000 KRW to your family in the Philippines.
- If the chatbot asks for recipient details, use this exact data:
  * Recipient Name: Maria Reyes (Wife)
  * Bank Name: BDO Unibank
  * Account Number: 0053-1234-5678

[Behavioral Guidelines for Demo]
1. You must speak ONLY in English.
2. DO NOT give the recipient info in your first message. Just say you want to send money to the Philippines and ask about today's fee/rate.
3. Provide the recipient details ONLY when the chatbot asks for them.
4. Speak in clear, practical, and direct English.
ONLY output your dialogue. Do not include internal thoughts."""
    },
    3: {
        "name": "Wang Wei (중국인 식당 셰프)",
        "prompt": """You are 'Wang Wei', a 41-year-old head chef at a Chinese restaurant in Seoul, holding an F-5 (Permanent Resident) Visa.
You are acting as the 'User' talking to a Korean bank's AI Chatbot.

[Your Situation & Goal]
- You visited Shanghai for a family trip last week. You tried to pay for a hotel using your Korean Check Card, but it was declined with a "Transaction Restricted" error.
- You returned to Korea yesterday and need to lift this overseas restriction immediately because you have to order overseas food ingredients next week.

[Behavioral Guidelines for Demo]
1. You must speak ONLY in Simplified Chinese.
2. Start by complaining that your card didn't work in Shanghai and ask why it was blocked.
3. Since you hold an F-5 visa, you are a long-term customer. Express mild urgency.
4. Answer the chatbot's troubleshooting questions cooperatively.
ONLY output your dialogue. Do not include internal thoughts."""
    }
}

START_MESSAGES = {
    1: "Start the conversation by asking how to open a new bank account.",
    2: "Start the conversation by asking about today's exchange rate to the Philippines.",
    3: "Start the conversation by complaining that your card was blocked overseas."
}

# ==========================================
# 3. 유틸리티 함수
# ==========================================
def send_gemini_message(chat_session, message, max_retries=5):
    import traceback
    for attempt in range(max_retries):
        try:
            response = chat_session.send_message(message)
            return response.text.strip()
        except Exception as e:
            tb = traceback.format_exc()
            with open('error_traceback.txt', 'w', encoding='utf-8') as f:
                f.write(tb)
            err_str = str(e)
            if "RESOURCE_EXHAUSTED" in err_str:
                if "PerDay" in err_str:
                    print("❌ 일일 API 한도 초과. 내일 자정(태평양 시간) 이후 다시 시도하세요.")
                    raise
                delay_match = re.search(r"retryDelay.*?(\d+)s", err_str)
                wait = int(delay_match.group(1)) + 5 if delay_match else 30
                print(f"⚠️ 분당 한도 초과 → {wait}초 후 재시도 ({attempt + 1}/{max_retries})")
                time.sleep(wait)
            else:
                print(f"❌ API 오류: {e}")
                raise
    raise Exception("최대 재시도 횟수 초과")


def find_app_frame_locator(page, max_wait=30):
    """frame_locator로 textarea가 있는 iframe 탐색"""
    print("앱 iframe 탐색 중...")
    for elapsed in range(max_wait):
        for i in range(5):
            try:
                fl = page.frame_locator("iframe").nth(i)
                if fl.locator("textarea").count() > 0:
                    print(f"  ✅ iframe[{i}]에서 입력창 발견! ({elapsed}초 경과)")
                    return fl
            except Exception:
                break
        if elapsed % 5 == 0:
            print(f"  [{elapsed}초] 탐색 중...")
        time.sleep(1)
    return None


MSG_SELECTORS = [
    'div[data-testid="stChatMessageContent"]',
    '[data-testid="stChatMessageContent"]',
    '[data-testid="stMarkdownContainer"]',
    '[data-testid="stChatMessage"]',
]

def get_messages(fl):
    for sel in MSG_SELECTORS:
        try:
            texts = fl.locator(sel).all_inner_texts()
            if texts and any(t.strip() for t in texts):
                return [t for t in texts if t.strip()]
        except Exception:
            pass
    return []


def get_body_length(fl):
    """모든 셀렉터가 실패할 때 body 전체 텍스트 길이로 변화 감지"""
    try:
        return len(fl.locator("body").inner_text())
    except Exception:
        return 0


def wait_for_count(fl, target_count, timeout=10):
    for _ in range(timeout):
        if len(get_messages(fl)) >= target_count:
            return True
        time.sleep(1)
    return False


LOADING_TEXTS = {"생각 중...", "생각 중", "..."}


def extract_last_bot_message(body_text):
    """body 전체 텍스트에서 마지막 봇(smart_toy) 답변만 추출"""
    parts = body_text.split("smart_toy")
    if len(parts) >= 2:
        # 마지막 smart_toy 이후 텍스트, 다음 face(유저) 이전까지
        last = parts[-1].split("face")[0].strip()
        if last:
            return last
    return body_text.strip()


def wait_for_bot_reply(fl, count_after_user_msg, baseline_length, timeout=180):
    """
    셀렉터 감지 + body 길이 변화 이중 방식.
    '생각 중...' 같은 로딩 텍스트는 무시하고 계속 대기.
    스트리밍 완료는 3초간 내용 변화 없음으로 판단.
    """
    for _ in range(timeout):
        msgs = get_messages(fl)

        # 방법 1: 셀렉터로 새 메시지 감지
        if len(msgs) > count_after_user_msg:
            last = msgs[-1].strip()
            if last in LOADING_TEXTS or not last:
                time.sleep(1)
                continue
            time.sleep(3)
            msgs2 = get_messages(fl)
            if msgs2 and msgs2[-1].strip() == last:
                return msgs2

        # 방법 2: body 길이 변화로 감지
        current_len = get_body_length(fl)
        if current_len > baseline_length + 50:
            time.sleep(3)
            stable_len = get_body_length(fl)
            if stable_len >= current_len:
                body = fl.locator("body").inner_text()
                extracted = extract_last_bot_message(body)
                return [extracted]

        time.sleep(1)
    return None


# ==========================================
# 4. 핵심 자동화 로직
# ==========================================
def run_persona(scenario_num):
    print(f"\n{'='*50}")
    print(f"[시나리오 {scenario_num} 시작] {personas[scenario_num]['name']}")
    print(f"{'='*50}")

    config = types.GenerateContentConfig(
        system_instruction=personas[scenario_num]["prompt"],
    )
    chat_session = client.chats.create(
        model="gemini-3.1-flash-lite",
        config=config
    )

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=100)
        page = browser.new_page()

        print(f"페이지 접속: {TARGET_URL}")
        page.goto(TARGET_URL, timeout=60000)
        print("5초 대기 (Streamlit 로딩)...")
        time.sleep(5)

        # frame_locator로 앱 iframe 탐색
        fl = find_app_frame_locator(page, max_wait=30)
        if fl is None:
            print("⚠️ 입력창을 찾지 못했습니다.")
            browser.close()
            return

        textarea = fl.locator("textarea").first

        # 첫 메시지 생성
        persona_reply = send_gemini_message(chat_session, START_MESSAGES[scenario_num])
        previous_bot_message_count = 0

        for turn in range(3):
            print(f"\n[Turn {turn+1}] {personas[scenario_num]['name']} 입력:\n>> {persona_reply}")

            textarea.fill(persona_reply)
            textarea.press("Enter")

            # 페르소나 메시지가 화면에 반영될 때까지 대기
            wait_for_count(fl, previous_bot_message_count + 1, timeout=10)
            count_after_user = len(get_messages(fl))
            baseline_length = get_body_length(fl)

            print("챗봇 답변 대기 중...")
            bot_messages = wait_for_bot_reply(fl, count_after_user, baseline_length, timeout=90)

            if bot_messages is None:
                print("⚠️ 90초 내 챗봇 답변 없음. 종료.")
                break

            latest_bot_message = bot_messages[-1]
            previous_bot_message_count = len(bot_messages)
            print(f"은행원 답변:\n>> {latest_bot_message}")

            if turn < 2:
                persona_reply = send_gemini_message(chat_session, latest_bot_message)

            time.sleep(2)

        print(f"\n✅ 시나리오 {scenario_num} 완료!")
        print("결과를 확인하세요. 브라우저 X 버튼으로 직접 닫으면 됩니다.")
        try:
            time.sleep(600)  # 최대 10분 유지, 브라우저 닫으면 자동 종료
        except Exception:
            pass


# ==========================================
# 5. 실행부
# ==========================================
if __name__ == "__main__":
    while True:
        try:
            choice = int(input("\n시나리오 번호 입력 (1: 베트남, 2: 필리핀, 3: 중국, 0: 종료): "))
            if choice == 0:
                print("종료합니다.")
                break
            elif choice in [1, 2, 3]:
                run_persona(choice)
            else:
                print("⚠️ 1, 2, 3 중 하나만 입력해 주세요.")
        except ValueError:
            print("⚠️ 숫자로 입력해 주세요.")
