import cv2
import json
import os
import glob
import numpy as np

# --- 전역 변수 ---
drawing = False
ix, iy = -1, -1
boxes = []
img_copy = None
current_json_filename = "" # 현재 작업 중인 JSON 파일명 저장

# --- 마우스 드래그 이벤트 함수 ---
def draw_rectangle(event, x, y, flags, param):
    global ix, iy, drawing, img_copy, boxes, current_json_filename
    
    if event == cv2.EVENT_LBUTTONDOWN:
        drawing = True
        ix, iy = x, y
        
    elif event == cv2.EVENT_MOUSEMOVE:
        if drawing:
            img_temp = img_copy.copy()
            cv2.rectangle(img_temp, (ix, iy), (x, y), (0, 255, 0), 2)
            cv2.imshow('Labeling Tool', img_temp)
            
    elif event == cv2.EVENT_LBUTTONUP:
        drawing = False
        cv2.rectangle(img_copy, (ix, iy), (x, y), (0, 0, 255), 2)
        cv2.imshow('Labeling Tool', img_copy)
        
        print(f"\n📍 좌표 선택됨: ({ix}, {iy}) ~ ({x}, {y})")
        label_name = input("👉 영역 이름(예: Sender_Name) 입력 후 엔터 (취소하려면 'c' 입력): ")
        
        if label_name.lower() == 'c':
             print("🚫 취소되었습니다. 다시 드래그하세요.")
             # 취소 시 방금 그린 네모 지우기 위해 원본 이미지로 복구
             img_copy = img.copy() 
             # 기존에 그려둔 박스들 다시 그리기
             for box in boxes:
                 cv2.rectangle(img_copy, (box['x_min'], box['y_min']), (box['x_max'], box['y_max']), (0, 0, 255), 2)
             cv2.imshow('Labeling Tool', img_copy)
             return

        boxes.append({
            "label": label_name,
            "x_min": min(ix, x),
            "y_min": min(iy, y),
            "x_max": max(ix, x),
            "y_max": max(iy, y)
        })
        
        # 💡 [핵심 추가] 박스를 그릴 때마다 즉시 JSON 파일에 저장(덮어쓰기)하여 데이터 날아감 방지
        with open(current_json_filename, 'w', encoding='utf-8') as f:
            json.dump(boxes, f, indent=4, ensure_ascii=False)
            
        print(f"✅ '{label_name}' 저장 완료! (현재까지 총 {len(boxes)}개 저장됨) - 다음 영역 드래그 또는 'q' 눌러 종료")

# --- 메인 실행 함수 ---
def start_labeling():
    global img_copy, boxes, current_json_filename
    global img # draw_rectangle 함수에서 img를 사용할 수 있도록 전역 변수로 선언
    
    png_files = glob.glob("*.png")
    
    if not png_files:
        print("❌ 에러: 현재 폴더에 PNG 이미지가 없습니다.")
        return

    print("\n📁 [라벨링할 이미지 목록]")
    for idx, file in enumerate(png_files):
        print(f"[{idx}] {file}")
        
    try:
        choice = int(input("\n👉 작업할 번호를 선택하세요 (예: 0): "))
        image_path = png_files[choice]
    except (ValueError, IndexError):
        print("❌ 잘못된 입력입니다. 프로그램을 다시 실행해주세요.")
        return

    boxes = []
    current_json_filename = f"{os.path.splitext(image_path)[0]}_labels.json"
    
    # 💡 [핵심 추가] 기존에 저장된 JSON 파일이 있는지 확인하고 불러오기
    if os.path.exists(current_json_filename):
        print(f"\n📂 이전에 작업하던 데이터({current_json_filename})를 발견했습니다! 불러옵니다...")
        with open(current_json_filename, 'r', encoding='utf-8') as f:
            try:
                boxes = json.load(f)
                print(f"✅ 총 {len(boxes)}개의 라벨 데이터를 불러왔습니다.")
            except json.JSONDecodeError:
                print("⚠️ 기존 JSON 파일이 비어있거나 손상되었습니다. 새로 시작합니다.")
                boxes = []

    try:
        img_array = np.fromfile(image_path, np.uint8)
        img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
    except Exception as e:
        print(f"❌ 이미지를 읽는 중 오류가 발생했습니다: {e}")
        return

    if img is None:
        print("❌ 이미지를 불러올 수 없습니다. 파일이 손상되었는지 확인하세요.")
        return
        
    img_copy = img.copy()
    
    # 💡 [핵심 추가] 불러온 박스들이 있다면 화면에 미리 그려주기
    if boxes:
        for box in boxes:
            cv2.rectangle(img_copy, (box['x_min'], box['y_min']), (box['x_max'], box['y_max']), (0, 0, 255), 2)
    
    # 윈도우 창 설정 (WINDOW_NORMAL 옵션을 주면 창 크기를 마음대로 조절할 수 있습니다!)
    cv2.namedWindow('Labeling Tool', cv2.WINDOW_NORMAL)
    cv2.setMouseCallback('Labeling Tool', draw_rectangle)
    
    print("\n" + "="*50)
    print("🖱️  [라벨링 툴이 켜졌습니다]")
    print("1. 새로 뜬 이미지 창에서 마우스로 영역을 드래그하세요.")
    print("2. VS Code 터미널로 돌아와 영어 이름을 치고 엔터를 누르세요.")
    print("   (잘못 그렸다면 이름 입력할 때 'c' 를 누르면 취소됩니다.)")
    print("3. 모든 작업이 끝나면 이미지 창을 클릭하고 키보드 'q'를 누르세요.")
    print("="*50 + "\n")
    
    while True:
        cv2.imshow('Labeling Tool', img_copy)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
            
    cv2.destroyAllWindows()
    print(f"\n🎉 작업 종료! 최종 데이터는 '{current_json_filename}'에 안전하게 저장되어 있습니다.")

if __name__ == "__main__":
    start_labeling()