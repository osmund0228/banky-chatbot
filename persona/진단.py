"""
진단 스크립트 v2 - frame_locator로 숨겨진 iframe 접근 테스트
"""
import time
from playwright.sync_api import sync_playwright

TARGET_URL = "https://ddalkkak-study-p6uwh6p35ykoidokq5fvwp.streamlit.app/"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, slow_mo=200)
    page = browser.new_page()

    print(f"접속 중: {TARGET_URL}")
    page.goto(TARGET_URL, timeout=60000)
    print("15초 대기...")
    time.sleep(15)

    # frame_locator로 각 iframe 안을 탐색
    print("\n[frame_locator 탐색]")
    found_index = -1
    for i in range(5):
        try:
            fl = page.frame_locator("iframe").nth(i)
            count = fl.locator("textarea").count()
            print(f"  iframe[{i}] → textarea {count}개")
            if count > 0 and found_index == -1:
                found_index = i
                print(f"  ✅ iframe[{i}]에서 textarea 발견!")
        except Exception as e:
            print(f"  iframe[{i}] → 더 이상 없음 ({e})")
            break

    if found_index >= 0:
        print(f"\n[fill 테스트] iframe[{found_index}] 사용")
        fl = page.frame_locator("iframe").nth(found_index)
        try:
            fl.locator("textarea").first.fill("안녕하세요 테스트입니다")
            print("  ✅ fill() 성공! 화면에 텍스트가 입력됐는지 확인하세요.")
            time.sleep(1)
            fl.locator("textarea").first.press("Enter")
            print("  ✅ Enter 전송 완료!")
        except Exception as e:
            print(f"  ❌ fill 실패: {e}")
    else:
        print("\n❌ 모든 iframe에서 textarea를 찾지 못했습니다.")

    print("\n30초 후 종료...")
    time.sleep(30)
    browser.close()
