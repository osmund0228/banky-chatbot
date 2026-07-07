"""
LLM 슬롯 추출기 + 다국어 재질문 생성
- OpenAI 호환 엔드포인트(로컬 vLLM 또는 서버리스 API)로 LLM 호출.
- base_url / model / api_key만 바꾸면 환경 교체 가능 (코랩, 서버리스 등).
- 두 가지 역할:
    1. extract(): 외국인 발화 -> 슬롯값 추출 (원문 보존, 추측 금지)
    2. make_question(): 누락된 필수 슬롯을 사용자 '언어로' 자연스럽게 재질문
"""
from __future__ import annotations

import json
from typing import Any

from openai import OpenAI

from app.core.slot_schema import FormSchema, SlotField


class SlotExtractor:
    def __init__(
        self,
        base_url: str = "http://localhost:8000/v1",
        model: str = "Qwen/Qwen2.5-7B-Instruct",
        api_key: str = "EMPTY",
    ):
        self.client = OpenAI(base_url=base_url, api_key=api_key)
        self.model = model

    # ---------- 1. 슬롯 추출 ----------
    def _build_tool_schema(self, schema: FormSchema) -> dict[str, Any]:
        """텍스트형 슬롯만 추출 대상으로 tool 스키마 구성 (서명/체크박스 제외)."""
        properties = {}
        for key, fld in schema.fields.items():
            if fld.field_type != "text":
                continue
            desc = getattr(fld, "meaning_en", None) or fld.meaning
            if fld.required:
                desc = f"[required] {desc}"
            properties[key] = {"type": "string", "description": desc}
        return {
            "type": "function",
            "function": {
                "name": "fill_bank_form",
                "description": (
                    f"고객 발화에서 '{schema.title}'에 필요한 값을 추출한다. "
                    "발화에 없는 값은 생략(추측 금지). 이름·계좌번호 등은 원문 그대로."
                ),
                "parameters": {"type": "object", "properties": properties},
            },
        }

    def extract(self, schema, conversation, current_slots=None):
        current_slots = current_slots or {}
        tool = self._build_tool_schema(schema)

        system = (
            "당신은 은행 서식 작성을 돕는 다국어 정보 추출 어시스턴트입니다. "
            "고객은 어떤 언어로든 말할 수 있습니다. 발화에서 서식 필드 값을 정확히 추출하세요. "
            "이름·주소·계좌번호 등 고유명사는 원문 그대로 보존하고, 발화에 없는 값은 절대 지어내지 마세요. "
            "반드시 fill_bank_form 함수를 호출하세요."
        )
        if current_slots:
            system += f"\n이미 수집된 값: {json.dumps(current_slots, ensure_ascii=False)}"

        resp = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "system", "content": system}, *conversation],
            tools=[tool],
            tool_choice={"type": "function", "function": {"name": "fill_bank_form"}},
            temperature=0,
        )
        msg = resp.choices[0].message
        if not msg.tool_calls:
            return {}
        try:
            args = json.loads(msg.tool_calls[0].function.arguments)
        except (json.JSONDecodeError, TypeError):
            return {}
        return {k: v for k, v in args.items() if v not in (None, "", "null")}

    # ---------- 2. 다국어 재질문 ----------
    def make_question(self, missing_field: SlotField, conversation, user_language_hint=""):
        """
        누락된 필수 슬롯을 사용자 언어로 자연스럽게 묻는 문장 생성.
        user_language_hint: "Vietnamese" 등. 비우면 대화 맥락에서 모델이 추론.
        """
        lang_line = f"사용자 언어: {user_language_hint}." if user_language_hint else \
                    "직전 사용자 발화와 같은 언어로 질문하세요."
        system = (
            "당신은 은행 서식 작성을 돕는 친절한 다국어 어시스턴트입니다. "
            f"{lang_line} "
            f"지금 '{missing_field.meaning}' 정보가 필요합니다. "
            "이 정보를 요청하는 짧고 자연스러운 한 문장만 생성하세요. 설명·따옴표 없이 질문만."
        )
        resp = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "system", "content": system}, *conversation[-4:]],
            temperature=0.3,
            max_tokens=100,
        )
        return resp.choices[0].message.content.strip()


def find_missing_required(schema, filled):
    """채워지지 않은 '텍스트형 필수' 슬롯 반환. (서명/체크박스는 대화 대상 아님)"""
    return [
        fld for key, fld in schema.fields.items()
        if fld.required and fld.field_type == "text" and not filled.get(key)
    ]
