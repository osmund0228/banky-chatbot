"""
PDF 렌더러
- 빈 서식 PDF의 좌표(픽셀)에 값을 삽입한다.
- 필드 타입별 처리:
    * text      : 박스에 맞춰 폰트 크기 자동 조정 후 텍스트 삽입
    * signature : 박스를 좌우 분할 → 왼쪽=정자 텍스트 이름, 오른쪽=서명 이미지(.png)
    * checkbox  : 값이 참이면 체크 표시(✓) 삽입
- 좌표 원점은 PDF 좌측 상단 (0,0), 픽셀 기준 (PyMuPDF/fitz 호환)
- 한글/CJK 출력을 위해 CJK 폰트를 명시 임베드.

주의: 좌표 라벨링이 특정 해상도(픽셀) 기준이라, PDF 실제 크기와 다르면
스케일 보정이 필요할 수 있다. render_form의 scale 인자로 조정.
"""
from __future__ import annotations

from pathlib import Path

import fitz  # PyMuPDF

CJK_FONT_CANDIDATES = [
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
]


def _resolve_font() -> str | None:
    for p in CJK_FONT_CANDIDATES:
        if Path(p).exists():
            return p
    return None


def _fit_fontsize(text: str, fontfile: str | None, max_w: float, max_h: float) -> float:
    font = fitz.Font(fontfile=fontfile) if fontfile else fitz.Font("cjk")
    size = min(max_h * 0.8, 12.0)
    while size > 5:
        if font.text_length(text, fontsize=size) <= max_w:
            return size
        size -= 0.5
    return 5.0


def _insert_text(page, rect, text, fontfile):
    pad = 2
    size = _fit_fontsize(text, fontfile, rect.width - 2 * pad, rect.height)
    baseline_y = rect.y0 + (rect.height + size * 0.7) / 2
    # 텍스트 너비 계산해서 가운데 정렬
    try:
        import fitz as _fitz
        tw = _fitz.get_text_length(text, fontname="cjk", fontfile=fontfile, fontsize=size)
        x = rect.x0 + max(pad, (rect.width - tw) / 2)
    except Exception:
        x = rect.x0 + pad
    page.insert_text((x, baseline_y), text,
                     fontsize=size, fontname="cjk", fontfile=fontfile)


def _insert_phone(page, rect, text, fontfile):
    """전화번호를 ( ) - 형식 칸에 맞춰 3등분 배치.
    예: 01029444300 -> 010 / 2944 / 4300
    칸 너비를 3구역으로 나눠 각 조각을 배치.
    """
    import re
    digits = re.sub(r"[^0-9]", "", text)
    if len(digits) >= 10:
        # 010 / 가운데 / 마지막4
        area = digits[:3]
        if len(digits) == 11:
            mid, last = digits[3:7], digits[7:]
        else:  # 10자리
            mid, last = digits[3:6], digits[6:]
    else:
        # 형식 불명: 그냥 통째로
        _insert_text(page, rect, text, fontfile)
        return
    size = min(10.0, rect.height * 0.6)
    by = rect.y0 + (rect.height + size * 0.7) / 2
    w = rect.width
    # ( 010 )  국번  -  뒷번호  : 칸 비율에 맞춰 x 위치 잡기
    positions = [
        (rect.x0 + w * 0.06, area),    # ( 010 )
        (rect.x0 + w * 0.42, mid),     # 국번
        (rect.x0 + w * 0.68, last),    # 뒷번호
    ]
    for x, part in positions:
        page.insert_text((x, by), part, fontsize=size,
                         fontname="cjk", fontfile=fontfile)


def _insert_email(page, rect, text, fontfile):
    """이메일을 @ 양옆에 배치. 예: abc@def.com -> abc | def.com."""
    if "@" in text:
        before, after = text.split("@", 1)
    else:
        _insert_text(page, rect, text, fontfile)
        return
    size = min(10.0, rect.height * 0.6)
    by = rect.y0 + (rect.height + size * 0.7) / 2
    w = rect.width
    # 앞부분(@왼쪽), 뒷부분(@오른쪽) - @ 기호가 칸 중앙쯤 인쇄됨
    page.insert_text((rect.x0 + w * 0.04, by), before,
                     fontsize=size, fontname="cjk", fontfile=fontfile)
    page.insert_text((rect.x0 + w * 0.55, by), after,
                     fontsize=size, fontname="cjk", fontfile=fontfile)


def _insert_checkmark(page, rect, fontfile):
    """체크박스에 V 표시. 작은 박스(약관 등)에도 잘 보이도록 최소 크기 보장."""
    # 박스가 작아도 최소 9pt는 되도록, 너무 크지 않게 상한도 둠
    size = max(9.0, min(rect.height, rect.width) * 1.3)
    size = min(size, 14.0)
    # 박스 중앙 정렬: 가로는 약간 왼쪽, 세로는 baseline을 박스 하단 근처로
    cx = rect.x0 + (rect.width - size * 0.55) / 2
    by = rect.y1 - (rect.height - size) / 2 - rect.height * 0.1
    page.insert_text((cx, by), "V",
                     fontsize=size, fontname="cjk", fontfile=fontfile)


def render_form(
    schema,
    values: dict[str, str],
    signatures: dict[str, bytes] | None = None,
    checks: dict[str, bool] | None = None,
    output_path: str | Path | None = None,
    scale_x: float | None = None,
    scale_y: float | None = None,
) -> bytes:
    """
    values:     {slot_key: 텍스트값}
    signatures: {slot_key: PNG 바이트}
    checks:     {slot_key: True/False}  체크박스
    scale_x/y:  좌표→PDF 스케일 보정. None이면 schema.scale 사용 (실측 기본값).
    반환: 생성된 PDF 바이트
    """
    if scale_x is None:
        scale_x = getattr(schema, "scale", 1.0)
    if scale_y is None:
        scale_y = getattr(schema, "scale", 1.0)
    signatures = signatures or {}
    checks = checks or {}
    doc = fitz.open(schema.pdf_path)
    fontfile = _resolve_font()

    for key, fld in schema.fields.items():
        if fld.page >= len(doc):
            continue
        page = doc[fld.page]
        bx0, by0, bx1, by1 = fld.bbox
        x0, y0, x1, y1 = bx0 * scale_x, by0 * scale_y, bx1 * scale_x, by1 * scale_y
        rect = fitz.Rect(x0, y0, x1, y1)

        if fld.field_type == "signature":
            name_text = values.get(key, "")
            sig_png = signatures.get(key)
            if name_text:
                # 이름이 있으면 좌우 분할: 왼쪽=이름, 오른쪽=서명
                mid = x0 + (x1 - x0) / 2
                _insert_text(page, fitz.Rect(x0, y0, mid, y1), name_text, fontfile)
                if sig_png:
                    page.insert_image(fitz.Rect(mid, y0, x1, y1), stream=sig_png,
                                      keep_proportion=True)
            elif sig_png:
                # 이름 없이 서명만: 박스 전체에 가운데 정렬로 넣기
                # 서명이 너무 크지 않게 약간 여백을 두고 중앙 배치
                box_w = x1 - x0
                box_h = y1 - y0
                # 서명 영역을 박스의 80% 폭으로, 가운데
                pad_x = box_w * 0.1
                page.insert_image(fitz.Rect(x0 + pad_x, y0, x1 - pad_x, y1),
                                  stream=sig_png, keep_proportion=True)

        elif fld.field_type == "checkbox":
            if checks.get(key) or values.get(key) == "V":
                _insert_checkmark(page, rect, fontfile)

        elif fld.field_type in ("group_checkbox", "agree_checkbox"):
            # 그룹 선택지/약관 동의: 값이 "V"(또는 참)이면 체크
            val = values.get(key) or checks.get(key)
            if val in ("V", "v", True, "true", "Y", "yes", 1):
                _insert_checkmark(page, rect, fontfile)

        else:  # text
            text = values.get(key, "")
            if text:
                # 전화번호: ( ) - 형식에 맞춰 3등분 배치
                if "phone" in key.lower() and key != "opt_customer_phone_office":
                    _insert_phone(page, rect, text, fontfile)
                # 이메일: @ 양옆에 배치
                elif "email" in key.lower():
                    _insert_email(page, rect, text, fontfile)
                else:
                    _insert_text(page, rect, text, fontfile)

    out = doc.tobytes()
    doc.close()
    if output_path:
        Path(output_path).write_bytes(out)
    return out
