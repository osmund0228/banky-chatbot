"""
외국인등록증 OCR (전부 로컬 처리, 외부 API 미사용)
- EasyOCR(로컬): 신분증 이미지 -> 텍스트 추출
- 정규식: 등록번호/날짜 1차 파싱
- LLMEngine(로컬 Qwen): 텍스트 -> 구조화 JSON 정제

★ 보안: 신분증 이미지가 외부로 나가지 않음 (Gemini 등 외부 API 미사용).
  본 챗봇과 동일하게 로컬 모델만 사용.

출력: {name, arc_number, visa_type, nationality}
  -> /api/ocr-arc 가 이 형식으로 반환 (프론트 규격)
"""
from __future__ import annotations

import re
import json
import io


# ---- EasyOCR 리더 (지연 초기화: 처음 호출 때만 로드) ----
_reader = None


def _get_reader():
    global _reader
    if _reader is None:
        import easyocr
        # 한국어 + 영어 (외국인등록증은 영문 이름 포함)
        _reader = easyocr.Reader(["ko", "en"], gpu=True)
    return _reader


def _preprocess(image_bytes: bytes):
    """OCR 정확도 향상 전처리 (그레이스케일/대비/이진화)."""
    import numpy as np
    import cv2
    from PIL import Image

    image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    img = np.array(image)
    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)
    denoised = cv2.GaussianBlur(enhanced, (3, 3), 0)
    _, binary = cv2.threshold(denoised, 0, 255,
                              cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return binary


def _extract_text(image_bytes: bytes) -> list[str]:
    """EasyOCR로 텍스트 라인 추출 (신뢰도 낮은 것 제외)."""
    reader = _get_reader()
    processed = _preprocess(image_bytes)
    results = reader.readtext(processed)
    lines = []
    for (_bbox, text, conf) in results:
        if conf < 0.2 or len(text.strip()) < 1:
            continue
        lines.append(text.strip())
    return lines


def _birth_from_arc(full_number: str) -> str | None:
    """외국인등록번호에서 생년월일 추출.
    형식: YYMMDD-Gxxxxxx (G=뒷자리 첫 숫자로 세기 판단)
      - G가 5,6 -> 1900년대
      - G가 7,8 -> 2000년대
    반환: "YYYY-MM-DD" 또는 None
    """
    nums = re.sub(r"[^0-9]", "", full_number)
    if len(nums) < 7:
        return None
    yy, mm, dd = nums[0:2], nums[2:4], nums[4:6]
    g = nums[6]  # 뒷자리 첫 숫자
    if g in "56":
        century = "19"
    elif g in "78":
        century = "20"
    else:
        # 내국인 코드(1,2=19xx / 3,4=20xx)도 대비
        century = "19" if g in "12" else "20"
    # 유효성 간단 체크
    try:
        if not (1 <= int(mm) <= 12 and 1 <= int(dd) <= 31):
            return None
    except ValueError:
        return None
    return f"{century}{yy}-{mm}-{dd}"


def _regex_hints(lines: list[str]) -> dict:
    """정규식 1차 파싱 (등록번호/체류자격/생년월일 힌트)."""
    full = " ".join(lines)
    hints = {}
    # 외국인등록번호: 6자리-7자리
    m = re.search(r"\d{6}[\s\-]?\d{7}", full)
    if m:
        num = re.sub(r"\s", "", m.group())
        # 생년월일 먼저 추출 (마스킹 전, 뒷자리 첫 숫자 필요)
        birth = _birth_from_arc(num)
        if birth:
            hints["birth_date"] = birth
        # 뒷자리 첫 숫자는 보존, 그 다음부터 마스킹
        hints["arc_number"] = num[:7] + "******"
    # 체류자격: 영문자-숫자 (예: D-4, E-9, F-2)
    m = re.search(r"\b([A-Z]-\d{1,2})\b", full)
    if m:
        hints["visa_type"] = m.group(1)
    return hints


def extract_id_info(image_bytes: bytes, engine) -> dict:
    """
    외국인등록증 이미지 -> 구조화 정보.
    engine: LLMEngine (로컬 Qwen). 텍스트 정제용.
    반환: {name, arc_number, visa_type, nationality}
    """
    # 1. EasyOCR로 텍스트 추출 (로컬)
    lines = _extract_text(image_bytes)
    ocr_text = "\n".join(lines)

    # 2. 정규식 1차 파싱 (로컬)
    hints = _regex_hints(lines)

    # 3. 로컬 Qwen으로 구조화 정제
    system = (
        "You extract structured info from Korean Alien Registration Card OCR text. "
        "Output ONLY a JSON object, no explanation, no markdown. "
        "Fields: name (English name on card), arc_number (registration number, "
        "keep masking like 901010-1******), visa_type (e.g. D-4, E-9, F-2), "
        "nationality (country in English). "
        "If a field is not found, use null. "
        "Use the regex hints if provided."
    )
    user = (
        f"OCR text:\n{ocr_text}\n\n"
        f"Regex hints: {json.dumps(hints, ensure_ascii=False)}\n\n"
        "Return JSON: {\"name\":..., \"arc_number\":..., "
        "\"visa_type\":..., \"nationality\":...}"
    )
    messages = [{"role": "system", "content": system},
                {"role": "user", "content": user}]

    raw = engine.generate(messages, temperature=0.0, max_new_tokens=200)

    # JSON 파싱 (마크다운/설명 제거)
    cleaned = re.sub(r"```json|```", "", raw).strip()
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        # 파싱 실패 시 정규식 힌트라도 반환
        data = {"name": None, "arc_number": hints.get("arc_number"),
                "visa_type": hints.get("visa_type"), "nationality": None}

    # 정규식 힌트로 보강 (Qwen이 놓친 것)
    for k in ("arc_number", "visa_type"):
        if not data.get(k) and hints.get(k):
            data[k] = hints[k]

    # 생년월일: 등록번호에서 추출한 값을 우선 (가장 정확)
    birth = hints.get("birth_date") or data.get("birth_date")

    # 필수 키 보장
    return {
        "name": data.get("name"),
        "birth_date": birth,
        "arc_number": data.get("arc_number"),
        "visa_type": data.get("visa_type"),
        "nationality": data.get("nationality"),
    }
