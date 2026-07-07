"""
PDF 작성 언어 통일
- 계좌개설 -> 영어 서식, 외화송금 -> 한국어 서식
- 사용자가 어떤 언어로 대화했든, PDF에 들어가는 텍스트 값을 타겟 언어로 변환.
- 로컬 Qwen 사용 (외부 API 없음).

변환 대상: 언어 영향받는 텍스트 (주소 등)
변환 제외: 숫자(전화/금액/날짜), 이메일, 영문 이름, 체크박스(V) -> 그대로
"""
from __future__ import annotations

import re

# 시나리오별 PDF 작성 언어
SCENARIO_PDF_LANGUAGE = {
    "account_opening": "English",
    "remittance": "English",   # 영어 서식 (한국어 번역 시 오역 방지)
}

# 번역하지 않는 키 (숫자/이메일/이름/체크박스 등)
#  - 체크박스(V)는 값이 "V"라서 자동 제외되지만, 명시적으로도 거름
_NO_TRANSLATE_PATTERNS = [
    "phone", "email", "amount", "_no", "account", "number", "date",
    "year", "month", "day", "birth",
    "signature", "_sig", "agree", "group",     # 체크박스/서명
]
# 이름 관련 (사람 이름은 보통 영문 그대로) - product_name은 제외 안 함
_NO_TRANSLATE_EXACT = [
    "customer_name", "sender_name_eng", "beneficiary_name",
    "applicant_name", "depositor_name",
]


def _should_translate(key: str, value) -> bool:
    """이 값을 번역해야 하나? (텍스트이고, 제외 패턴이 아니고, 숫자/V가 아님)"""
    if not isinstance(value, str) or not value.strip():
        return False
    v = value.strip()
    # 체크박스 값
    if v in ("V", "v", "Y", "yes", "true", "1"):
        return False
    # 순수 숫자/기호 (전화·금액·날짜 등)
    if re.fullmatch(r"[\d\s\-.,@/+()]+", v):
        return False
    # 이메일
    if "@" in v:
        return False
    low = key.lower()
    # 사람 이름은 정확 매칭으로 제외 (product_name은 번역됨)
    if any(low == ex or low == "req_" + ex or low == "opt_" + ex
           for ex in _NO_TRANSLATE_EXACT):
        return False
    if any(p in low for p in _NO_TRANSLATE_PATTERNS):
        return False
    return True


def translate_form_values(scenario: str, backend_slots: dict, engine) -> dict:
    """PDF 작성 언어로 텍스트 값 번역. backend_slots(번역본) 반환.
    engine: 로컬 Qwen (LLMEngine).
    """
    target = SCENARIO_PDF_LANGUAGE.get(scenario)
    if not target:
        return backend_slots

    # 번역 대상만 추림
    to_translate = {k: v for k, v in backend_slots.items()
                    if _should_translate(k, v)}
    if not to_translate:
        return backend_slots

    out = dict(backend_slots)
    for key, value in to_translate.items():
        translated = _translate_one(value, target, engine)
        if translated:
            out[key] = translated
    return out


def _translate_one(text: str, target_language: str, engine) -> str:
    """한 값을 타겟 언어로 번역 (로컬 Qwen)."""
    system = (
        f"You are a translator for bank form fields. "
        f"Translate the given text into {target_language}. "
        f"For addresses, use standard {target_language} romanization/notation. "
        f"Output ONLY the translated text, no quotes, no explanation. "
        f"If already in {target_language}, return as-is."
    )
    messages = [{"role": "system", "content": system},
                {"role": "user", "content": text}]
    try:
        result = engine.generate(messages, temperature=0.0, max_new_tokens=100)
        return result.strip().strip('"').strip("'")
    except Exception:
        return text  # 실패 시 원본 유지
