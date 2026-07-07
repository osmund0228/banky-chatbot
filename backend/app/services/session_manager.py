"""
서식 작성 대화 세션 관리
- 멀티턴 슬롯 누적 + 빈 필수 슬롯 다국어 재질문.
- 메모리 저장소(데모용). 운영 시 Redis 등으로 교체.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from app.core.slot_schema import FormSchema, load_form_schema
from app.services.slot_extractor import SlotExtractor, find_missing_required


@dataclass
class FormSession:
    session_id: str
    form_id: str
    schema: FormSchema
    slots: dict[str, str] = field(default_factory=dict)
    history: list[dict[str, str]] = field(default_factory=list)
    language: str = ""          # 감지/지정된 사용자 언어
    completed: bool = False


class SessionManager:
    def __init__(self, extractor: SlotExtractor, data_dir: str):
        self.extractor = extractor
        self.data_dir = data_dir
        self._sessions: dict[str, FormSession] = {}

    def start(self, form_id: str, language: str = "") -> FormSession:
        schema = load_form_schema(form_id, self.data_dir)  # PDF 경로 자동
        sid = str(uuid.uuid4())
        session = FormSession(session_id=sid, form_id=form_id,
                              schema=schema, language=language)
        self._sessions[sid] = session
        return session

    def get(self, session_id: str):
        return self._sessions.get(session_id)

    def process_message(self, session: FormSession, user_text: str) -> dict:
        session.history.append({"role": "user", "content": user_text})

        # 1. 슬롯 추출 + 누적
        new_slots = self.extractor.extract(
            session.schema, session.history, session.slots)
        session.slots.update(new_slots)

        # 2. 남은 필수 텍스트 슬롯 확인
        missing = find_missing_required(session.schema, session.slots)

        if not missing:
            session.completed = True
            return {
                "filled": session.slots,
                "missing_required": [],
                "next_question": None,
                "completed": True,
            }

        # 3. 다음 빈 슬롯을 사용자 언어로 재질문
        target = missing[0]
        question = self.extractor.make_question(
            target, session.history, session.language)
        session.history.append({"role": "assistant", "content": question})

        return {
            "filled": session.slots,
            "missing_required": [m.key for m in missing],
            "next_question": question,
            "completed": False,
        }
