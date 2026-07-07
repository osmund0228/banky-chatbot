"""
슬롯 스키마 로더
- 라벨링된 좌표 JSON(7번 데이터)을 읽어 슬롯 정의를 구성한다.
- 실제 데이터 구조에 맞춤:
    * JSON은 평면 리스트 [{"label","x_min","y_min","x_max","y_max"}, ...]
    * 한 서식이 여러 페이지 파일로 분리됨 (계좌개설 = page_0 + page_1)
- Key 접두사 규칙: req_ = 필수, opt_ = 선택
- 필드 타입 자동 판별: 서명(signature/sig), 체크박스(chk), 일반 텍스트
- 좌표는 PDF 좌측 상단 (0,0) 기준 픽셀 (PyMuPDF/fitz 호환)
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from app.core.field_meanings import get_meaning, get_meaning_en


@dataclass
class SlotField:
    key: str                 # 예: req_customer_name
    page: int                # 0-based 페이지 번호
    bbox: tuple[float, float, float, float]  # (x_min, y_min, x_max, y_max)
    required: bool
    meaning: str             # 사람이 읽는 한국어 의미 (재질문/사용자 대면용)
    meaning_en: str          # 영어 의미 (LLM 추출 지시용, 소형모델 혼동 감소)
    field_type: str          # "text" | "signature" | "checkbox"

    @property
    def width(self) -> float:
        return self.bbox[2] - self.bbox[0]

    @property
    def height(self) -> float:
        return self.bbox[3] - self.bbox[1]


@dataclass
class FormSchema:
    form_id: str
    title: str
    page_files: list[str]    # 페이지 순서대로의 좌표 JSON 경로 (참고용)
    pdf_path: str            # 빈 서식 PDF 경로
    scale: float = 1.0       # 좌표→PDF 변환 배율
    fields: dict[str, SlotField] = field(default_factory=dict)

    @property
    def required_keys(self) -> list[str]:
        return [k for k, f in self.fields.items() if f.required]

    @property
    def optional_keys(self) -> list[str]:
        return [k for k, f in self.fields.items() if not f.required]

    @property
    def text_required_keys(self) -> list[str]:
        """재질문 대상이 되는 '텍스트형 필수 슬롯'. 서명/체크박스는 대화로 안 받음."""
        return [k for k, f in self.fields.items()
                if f.required and f.field_type == "text"]


# 서식 종류별 정의: 제목 + 페이지 좌표파일 + 빈 PDF + 좌표 스케일
# scale: 라벨 좌표(픽셀) → PDF(pt) 변환 배율. 라벨이 PDF의 1.5배 해상도에서
#        작성되어 1/1.5 ≈ 0.6667. (실측 검증값, 두 서식 공통)
LABEL_SCALE = 0.6667

FORM_REGISTRY = {
    "account_opening": {
        "title": "계좌개설신청서 (외국인용)",
        "page_files": [
            "계좌개설신청서_외국인용_하나은행_page_0_labels.json",
            "계좌개설신청서_외국인용_하나은행_page_1_labels.json",
        ],
        "pdf_file": "계좌개설신청서_외국인용_하나은행-1.pdf",
        "scale": LABEL_SCALE,
    },
    "foreign_remittance": {
        "title": "외화송금신청서",
        "page_files": [
            "외화송금신청서_하나은행_page_0_labels.json",
        ],
        "pdf_file": "외화송금신청서_하나은행.pdf",
        "scale": LABEL_SCALE,
    },
}


def _classify_field(key: str, width: float, height: float) -> str:
    """label과 박스 크기로 필드 타입 판별.
    반환: text | signature | checkbox | group_checkbox | agree_checkbox
    """
    low = key.lower()
    # 약관 동의 체크박스 먼저 (assign 등이 sig로 오분류되지 않도록)
    if low.startswith("req_agree_"):
        return "agree_checkbox"
    # 선택지 그룹 체크박스
    if low.startswith("req_group_") or low.startswith("opt_group_"):
        return "group_checkbox"
    # 서명: _sig로 끝나거나 signature 포함 (assign의 'sig'는 제외)
    if low.endswith("_sig") or "signature" in low:
        return "signature"
    if "chk" in low or "check" in low:
        return "checkbox"
    # 아주 작은 박스(가로세로 모두 ~20px 이하)는 체크박스로 간주
    if width <= 20 and height <= 20:
        return "checkbox"
    return "text"


def load_form_schema(form_id: str, data_dir: str | Path,
                     pdf_path: str | Path | None = None) -> FormSchema:
    """
    form_id에 해당하는 좌표 JSON(들)을 읽어 FormSchema 생성.
    여러 페이지 파일을 페이지 번호(0,1,...)로 병합한다.
    pdf_path를 안 주면 FORM_REGISTRY의 pdf_file을 data_dir 기준으로 사용.
    """
    data_dir = Path(data_dir)
    meta = FORM_REGISTRY.get(form_id)
    if not meta:
        raise ValueError(f"알 수 없는 form_id: {form_id}")

    if pdf_path is None:
        pdf_path = data_dir / meta["pdf_file"]

    schema = FormSchema(
        form_id=form_id,
        title=meta["title"],
        page_files=[str(data_dir / f) for f in meta["page_files"]],
        pdf_path=str(pdf_path),
        scale=meta.get("scale", 1.0),
    )

    for page_idx, fname in enumerate(meta["page_files"]):
        fpath = data_dir / fname
        entries = json.loads(fpath.read_text(encoding="utf-8"))
        for entry in entries:
            key = entry["label"]
            bbox = (
                float(entry["x_min"]), float(entry["y_min"]),
                float(entry["x_max"]), float(entry["y_max"]),
            )
            width = bbox[2] - bbox[0]
            height = bbox[3] - bbox[1]
            schema.fields[key] = SlotField(
                key=key,
                page=page_idx,
                bbox=bbox,
                required=key.startswith("req_"),
                meaning=get_meaning(key),
                meaning_en=get_meaning_en(key),
                field_type=_classify_field(key, width, height),
            )

    return schema
