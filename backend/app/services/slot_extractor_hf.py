"""
SlotExtractor (transformers 버전) - 코랩 검증용
- vLLM 서버 없이 HuggingFace transformers로 직접 모델을 호출한다.
- vLLM의 tool_choice 강제 호출 대신, 프롬프트로 JSON만 출력하게 유도 후 파싱.
  (transformers 환경에서 가장 안정적인 방식)
- 원래 slot_extractor.py와 동일한 인터페이스(extract, make_question)를 제공해
  session_manager가 그대로 사용 가능.

사용 예:
    from transformers import AutoModelForCausalLM, AutoTokenizer
    model = AutoModelForCausalLM.from_pretrained("Qwen/Qwen2.5-3B-Instruct", ...)
    tokenizer = AutoTokenizer.from_pretrained("Qwen/Qwen2.5-3B-Instruct")
    extractor = HFSlotExtractor(model, tokenizer)
"""
from __future__ import annotations

import json
import re


class HFSlotExtractor:
    def __init__(self, engine=None, model=None, tokenizer=None, max_new_tokens: int = 512):
        """
        engine: 공유 LLMEngine (권장 - 모델 공유)
        model/tokenizer: 직접 주입 (단독 사용 시 하위호환)
        """
        if engine is not None:
            self.engine = engine
        else:
            # 하위호환: model/tokenizer로 자체 엔진 생성
            from app.services.llm_engine import LLMEngine
            self.engine = LLMEngine(model, tokenizer, max_new_tokens)

    def _generate(self, messages, temperature=0.0, max_new_tokens=None):
        """공유 엔진으로 생성 (인터페이스 유지)."""
        return self.engine.generate(messages, temperature=temperature,
                                    max_new_tokens=max_new_tokens)

    # ---------- 1. 슬롯 추출 ----------
    def _slot_descriptions(self, schema) -> str:
        """텍스트형 슬롯들을 'key: 의미' 목록 문자열로 (영어 의미 사용)."""
        lines = []
        for key, fld in schema.fields.items():
            if fld.field_type != "text":
                continue
            mark = "[required]" if fld.required else "[optional]"
            # 영어 의미 사용 (소형 모델 혼동 감소). 없으면 한국어 폴백.
            desc = getattr(fld, "meaning_en", None) or fld.meaning
            lines.append(f"- {key}: {mark} {desc}")
        return "\n".join(lines)

    def extract(self, schema, conversation, current_slots=None):
        """발화에서 슬롯값 추출 -> dict 반환."""
        current_slots = current_slots or {}
        slot_list = self._slot_descriptions(schema)

        # 대화 내용을 하나의 텍스트로 (마지막 사용자 발화 중심)
        convo_text = "\n".join(
            f"{m['role']}: {m['content']}" for m in conversation
        )

        system = (
            "You are a multilingual information extractor for bank forms.\n"
            "The customer may speak any language. Extract field values from the conversation below.\n"
            "RULES:\n"
            "1. Preserve proper nouns (names, addresses, account numbers) exactly as written.\n"
            "2. NEVER invent values not in the conversation. Omit fields you cannot fill.\n"
            "3. Only output fields that you ACTUALLY found a value for. Do NOT output empty strings.\n"
            "4. A romanized/Latin-letter name goes into the *_name_eng field, NOT the *_kor field. "
            "Korean-script names go into *_kor.\n"
            "5. Output ONLY a JSON object. No explanation, no code blocks, no markdown.\n"
            "6. The [FIELDS] list shows field NAMES and their DESCRIPTIONS. "
            "NEVER use a field's description text as its value. "
            "Descriptions only tell you what to look for in the conversation.\n"
            "7. If the customer only greeted or asked a question without giving personal data, "
            "output an empty JSON object {}. Do NOT fill any field with guessed or example data.\n\n"
            f"[FIELDS]\n{slot_list}\n\n"
            f"[ALREADY COLLECTED]\n{json.dumps(current_slots, ensure_ascii=False)}\n\n"
            "Output a JSON object mapping field names to values you found. "
            "If you found nothing, output {}."
        )
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": f"[CONVERSATION]\n{convo_text}\n\nOutput JSON only:"},
        ]
        raw = self._generate(messages, temperature=0.0, max_new_tokens=256)
        parsed = self._parse_json(raw)
        # 빈 값 제거 (모델이 빈 문자열을 출력해도 방어)
        return {k: v for k, v in parsed.items()
                if v not in (None, "", "null") and str(v).strip()}

    @staticmethod
    def _parse_json(text: str) -> dict:
        """모델 출력에서 JSON 객체만 안전하게 추출."""
        # 코드블록 제거
        text = re.sub(r"```(?:json)?", "", text).strip()
        # 첫 { 부터 마지막 } 까지
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1:
            return {}
        snippet = text[start:end + 1]
        try:
            return json.loads(snippet)
        except json.JSONDecodeError:
            return {}

    # ---------- 2. 다국어 재질문 ----------
    def extract_single(self, field_key, field_desc, user_message):
        """사용자 발화에서 특정 필드 값 하나만 추출 (군더더기 제거).
        예: '제 주소는 마포구 백범로 35입니다' -> '마포구 백범로 35'
        실패 시 None 반환 (호출측에서 정규식 백업)."""
        system = (
            "You extract a single field value from the user's message for a bank form.\n"
            f"Field to extract: {field_desc}\n"
            "RULES:\n"
            "1. Output ONLY the value itself, removing particles, polite endings, "
            "and surrounding sentence (e.g. '제 주소는 X입니다' -> 'X').\n"
            "2. Preserve the value exactly (names, numbers, addresses as written).\n"
            "3. If the message contains no such value, output exactly: NONE\n"
            "4. No quotes, no explanation, no extra words."
        )
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user_message},
        ]
        try:
            result = self._generate(messages, temperature=0.0, max_new_tokens=60).strip()
            result = result.strip('"').strip("'").strip()
            if not result or result.upper() == "NONE":
                return None
            return result
        except Exception:
            return None

    # 주요 필드별 다국어 질문문 (LLM 없이 확실하게)
    _FIELD_QUESTIONS = {
        "req_customer_mobile_phone": {
            "Korean": "휴대폰 번호를 알려주세요.",
            "English": "What is your mobile phone number?",
            "Vietnamese": "Số điện thoại di động của bạn là gì?",
            "Chinese": "请提供您的手机号码。",
            "Japanese": "携帯電話番号を教えてください。",
            "Indonesian": "Apa nomor telepon seluler Anda?",
            "French": "Quel est votre numéro de téléphone portable ?",
            "Thai": "หมายเลขโทรศัพท์มือถือของคุณคืออะไร",
        },
        "opt_customer_email": {
            "Korean": "이메일 주소를 알려주세요.",
            "English": "What is your email address?",
            "Vietnamese": "Địa chỉ email của bạn là gì?",
            "Chinese": "请提供您的电子邮件地址。",
            "Japanese": "メールアドレスを教えてください。",
            "Indonesian": "Apa alamat email Anda?",
            "French": "Quelle est votre adresse e-mail ?",
            "Thai": "อีเมลของคุณคืออะไร",
        },
        "req_customer_address_home": {
            "Korean": "자택 주소를 알려주세요.",
            "English": "What is your home address?",
            "Vietnamese": "Địa chỉ nhà của bạn là gì?",
            "Chinese": "请提供您的家庭住址。",
            "Japanese": "ご自宅の住所を教えてください。",
            "Indonesian": "Apa alamat rumah Anda?",
            "French": "Quelle est votre adresse de domicile ?",
            "Thai": "ที่อยู่บ้านของคุณคืออะไร",
        },
        "req_customer_address_office": {
            "Korean": "직장 주소를 알려주세요.",
            "English": "What is your office address?",
            "Vietnamese": "Địa chỉ văn phòng của bạn là gì?",
            "Chinese": "请提供您的公司地址。",
            "Japanese": "勤務先の住所を教えてください。",
            "Indonesian": "Apa alamat kantor Anda?",
            "French": "Quelle est votre adresse professionnelle ?",
            "Thai": "ที่อยู่ที่ทำงานของคุณคืออะไร",
        },
        "req_customer_phone_office": {
            "Korean": "직장 전화번호를 알려주세요.",
            "English": "What is your office phone number?",
            "Vietnamese": "Số điện thoại văn phòng của bạn là gì?",
            "Chinese": "请提供您的公司电话号码。",
            "Japanese": "勤務先の電話番号を教えてください。",
            "Indonesian": "Apa nomor telepon kantor Anda?",
            "French": "Quel est votre numéro de téléphone professionnel ?",
            "Thai": "หมายเลขโทรศัพท์ที่ทำงานของคุณคืออะไร",
        },
        "req_enrollment_amount": {
            "Korean": "초기 입금 금액을 알려주세요.",
            "English": "What is the initial deposit amount?",
            "Vietnamese": "Số tiền gửi ban đầu là bao nhiêu?",
            "Chinese": "请提供初始存款金额。",
            "Japanese": "初期入金額を教えてください。",
            "Indonesian": "Berapa jumlah setoran awal?",
            "French": "Quel est le montant du dépôt initial ?",
            "Thai": "จำนวนเงินฝากเริ่มต้นคือเท่าไร",
        },
        "req_sender_name_eng": {
            "Korean": "송금인의 영문 이름을 알려주세요 (여권에 적힌 대로).",
            "English": "What is the sender's name in English (as on the passport)?",
            "Vietnamese": "Tên người gửi bằng chữ Latinh là gì (như trên hộ chiếu)?",
            "Chinese": "请提供汇款人的英文姓名（与护照一致）。",
            "Japanese": "送金人の英語の氏名を教えてください（パスポート記載のとおり）。",
            "Indonesian": "Siapa nama pengirim dalam huruf Latin (sesuai paspor)?",
            "French": "Quel est le nom de l'expéditeur en lettres latines (comme sur le passeport) ?",
            "Thai": "ชื่อผู้ส่งเป็นอักษรละตินคืออะไร (ตามหนังสือเดินทาง)",
        },
    }

    def make_question(self, missing_field, conversation, user_language_hint=""):
        """누락된 필수 슬롯을 사용자 언어로 묻는 문장 생성.
        주요 필드는 하드코딩된 다국어 질문을 사용 (LLM 오동작 방지)."""
        target_lang = user_language_hint or self._detect_language(conversation)
        field_key = getattr(missing_field, "key", None) or ""

        # 주요 필드는 하드코딩 (Qwen이 엉뚱한 필드를 물어보는 것 방지)
        if field_key in self._FIELD_QUESTIONS:
            q = self._FIELD_QUESTIONS[field_key]
            return q.get(target_lang, q.get("English", ""))

        # 나머지 필드는 LLM
        field_desc = getattr(missing_field, "meaning_en", None) or missing_field.meaning
        system = (
            "You are a bank assistant helping a customer fill out a form.\n"
            f"Ask the customer for this information: {field_desc}.\n"
            f"Write ONE short, clear question in {target_lang}.\n"
            "Output only the question. No quotes, no explanation."
        )
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": f"Ask for: {field_desc} (in {target_lang})"},
        ]
        return self._generate(messages, temperature=0.3, max_new_tokens=60).strip()

    @staticmethod
    def _detect_language(conversation) -> str:
        """마지막 사용자 발화의 언어 감지. 문자 범위 체크 + langdetect 병행."""
        last_user = ""
        for m in reversed(conversation):
            if m["role"] == "user":
                last_user = m["content"]
                break
        if not last_user:
            return "English"

        # 1) 문자 범위로 1차 판별 (짧은 문장에서 langdetect보다 안정적)
        import re
        if re.search(r"[\u3040-\u30ff]", last_user):       # 히라가나/가타카나
            return "Japanese"
        if re.search(r"[\uac00-\ud7a3]", last_user):        # 한글
            return "Korean"
        if re.search(r"[\u4e00-\u9fff]", last_user):        # 한자 (일/한 제외 후)
            return "Chinese"
        if re.search(r"[\u0e00-\u0e7f]", last_user):        # 태국 문자
            return "Thai"
        # 베트남어 특유의 성조 문자
        if re.search(r"[ăâđêôơưĂÂĐÊÔƠƯ]", last_user) or \
           re.search(r"[\u0300-\u0323]", last_user):
            return "Vietnamese"

        # 2) 라틴 문자권은 langdetect로 세분
        try:
            from langdetect import detect
            code = detect(last_user)
            return {
                "vi": "Vietnamese", "id": "Indonesian",
                "en": "English", "ko": "Korean",
                "fr": "French", "th": "Thai",
            }.get(code, "English")
        except Exception:
            return "English"


def find_missing_required(schema, filled):
    """채워지지 않은 '텍스트형 필수' 슬롯 반환."""
    return [
        fld for key, fld in schema.fields.items()
        if fld.required and fld.field_type == "text" and not filled.get(key)
    ]
