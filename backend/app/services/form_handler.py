"""
Stateless 서식 처리 (계좌개설 그룹/약관 로직 포함)

흐름:
  텍스트 필수 추출 -> 필수 선택지 그룹(purpose/source/overseas) -> 약관 일괄동의 -> 완료
계좌개설:
  - 휴대폰 통신사/우편물/직업: 번호 선택지 (그룹 체크박스)
  - 직장 항목: 직업이 직장 있을 때만
  - 거래목적/자금원천/해외납세: 필수 번호 선택지
  - 약관 14개+: 한 번에 일괄 동의
  - 신청 날짜: 자동(오늘), 이름->서명옆 자동복사
"""
from __future__ import annotations

from app.core.field_mapping import (
    front_to_backend, backend_to_front, SCENARIO_TO_FORM_ID,
)
from app.core.slot_schema import load_form_schema
from app.core.account_groups import (
    REQUIRED_GROUPS, OPTIONAL_GROUPS, ALL_AGREE_KEYS,
    group_question, consent_display,
    PRODUCT_CHOICES, product_question,
)
from app.services.slot_extractor_hf import find_missing_required

# 선택지/약관을 이미 갖춘 언어 (번역 불필요)
_NATIVE_LANGS = {"Korean", "English"}


def _translate_texts(texts, target_language, engine):
    """문자열 리스트를 목표 언어로 번역 (로컬 Qwen).
    여러 항목을 한 번의 호출로 번역 (속도 최적화). 실패 시 원본 유지."""
    if not texts or engine is None:
        return texts
    # 비어있지 않은 것만
    items = [str(t) for t in texts if t and str(t).strip()]
    if not items:
        return texts
    # 한 번에 번역: 줄단위로 묶어서 1회 호출
    numbered = "\n".join(f"{i+1}. {t}" for i, t in enumerate(items))
    sys_msg = (
        f"You are a translator. Translate each numbered line into {target_language}.\n"
        f"RULES:\n"
        f"- Output the SAME number of lines, with the SAME numbering (1. 2. 3. ...).\n"
        f"- Translate the actual words into {target_language}. Do NOT keep English.\n"
        f"- Output ONLY the translated numbered lines.\n"
        f"- NO intro text, NO 'Here are', NO explanation, NO notes."
    )
    try:
        r = engine.generate(
            [{"role": "system", "content": sys_msg},
             {"role": "user", "content": numbered}],
            temperature=0.0, max_new_tokens=300)
        import re
        # 번호가 붙은 줄만 추출 (머리말/설명 줄 제거)
        numbered_lines = []
        for ln in r.strip().splitlines():
            ln = ln.strip()
            m = re.match(r"^(\d+)[.)]\s*(.+)$", ln)
            if m:
                numbered_lines.append((int(m.group(1)), m.group(2).strip()))
        # 번호 순 정렬 후 값만
        numbered_lines.sort(key=lambda x: x[0])
        cleaned = [v for _, v in numbered_lines]
        # 개수가 정확히 맞으면 그대로 매핑
        if len(cleaned) == len(items):
            result = []
            idx = 0
            for t in texts:
                if t and str(t).strip():
                    result.append(cleaned[idx]); idx += 1
                else:
                    result.append(t)
            return result
        # 개수가 안 맞아도: 매칭되는 만큼만 번역 적용, 나머지는 원본 유지
        # (Qwen이 줄 수를 약간 틀려도 번역을 통째로 버리지 않음)
        if cleaned:
            result = []
            idx = 0
            for t in texts:
                if t and str(t).strip():
                    if idx < len(cleaned) and cleaned[idx]:
                        result.append(cleaned[idx])
                    else:
                        result.append(t)
                    idx += 1
                else:
                    result.append(t)
            return result
    except Exception:
        pass
    return texts


def _translate_one(text, target_language, engine):
    """단일 텍스트 번역 (질문문용)."""
    if not text or engine is None:
        return text
    try:
        sys_msg = (
            f"Translate into {target_language}. "
            f"Keep leading numbers/symbols. Output ONLY the translation."
        )
        r = engine.generate(
            [{"role": "system", "content": sys_msg},
             {"role": "user", "content": str(text)}],
            temperature=0.0, max_new_tokens=200)
        return r.strip().strip('"').strip("'") or text
    except Exception:
        return text


def _translate_result(result, target_language, engine):
    """결과의 bot_reply / choices를 목표 언어로 번역.
    한국어·영어는 그대로(이미 갖춰짐).
    consent_items는 6개 언어로 직접 제공되므로 재번역하지 않음.
    _reply_localized=True면 bot_reply도 이미 해당 언어이므로 재번역 안 함
    (약관 안내문처럼 다국어로 직접 만든 경우 - 재번역 시 잘림 방지)."""
    if target_language in _NATIVE_LANGS or not target_language or engine is None:
        result.pop("_reply_localized", None)
        return result
    if result.get("bot_reply") and not result.get("_reply_localized"):
        result["bot_reply"] = _translate_one(
            result["bot_reply"], target_language, engine)
    if result.get("choices"):
        result["choices"] = _translate_texts(
            result["choices"], target_language, engine)
    # consent_items는 consent_display()가 이미 해당 언어로 반환 -> 재번역 안 함
    result.pop("_reply_localized", None)   # 내부 플래그 제거
    return result


DATE_SLOTS = {
    "remittance": ("req_application_year", "req_application_month", "req_application_day"),
    "account_opening": ("req_app_year_p0", "req_app_month_p0", "req_app_day_p0"),
}

# 텍스트로 받던 직업/우편물/통신사는 이제 그룹으로 처리하므로 텍스트 필수에서 제외
ACCOUNT_TEXT_SKIP = {
    "req_customer_mailing_to",        # -> mailing 그룹
    "req_customer_occupation",        # -> occupation 그룹
    "opt_customer_mobile_phone_category",
}


def _autofill(scenario, backend_slots):
    from datetime import date
    today = date.today()
    yk, mk, dk = DATE_SLOTS.get(scenario, (None, None, None))
    if yk:
        backend_slots.setdefault(yk, str(today.year))
        backend_slots.setdefault(mk, str(today.month))
        backend_slots.setdefault(dk, str(today.day))
    if scenario == "account_opening":
        name = backend_slots.get("req_customer_name")
        if name:
            # 서명 필드에 이름을 넣으면 렌더러가 '왼쪽=이름 + 오른쪽=서명'으로 분할
            for sk in ("req_applicant_signature_p0", "req_depositor_final_signature"):
                backend_slots.setdefault(sk, name)
    if scenario == "remittance":
        # 신청인 이름 = 송금인 이름으로 자동 채움
        sender = backend_slots.get("req_sender_name_eng")
        if sender:
            backend_slots.setdefault("req_applicant_name", sender)
            # 신청인 서명란에도 이름 (렌더러가 이름+서명 분할)
            backend_slots.setdefault("req_applicant_signature_p0", sender)
    return backend_slots


def _occupation_has_workplace(backend_slots):
    """직업 그룹 선택으로 직장 유무 판단. True/False/None."""
    occ = OPTIONAL_GROUPS["occupation"]
    for idx, key in enumerate(occ["keys"]):
        if backend_slots.get(key) == "V":
            return idx not in occ["no_workplace_idx"]
    return None  # 아직 직업 선택 안 함


def _next_basic_text(extractor, schema, backend_slots, conversation, language):
    """기본 req_ 텍스트 항목 질문 (직장 항목, 상품명 제외). 없으면 None.
    상품명은 선택지로 따로 처리.
    """
    workplace = {"opt_customer_address_office", "opt_customer_phone_office"}
    skip = ACCOUNT_TEXT_SKIP | workplace | {"req_product_name", "req_enrollment_amount"}
    for k, f in schema.fields.items():
        if f.field_type != "text" or not f.required:
            continue
        if k in skip:
            continue
        if not backend_slots.get(k):
            return extractor.make_question(f, conversation, user_language_hint=language)
    return None


def _extract_text_value(target_key: str, user_message: str) -> str:
    """text:stage 답변에서 해당 필드 값만 추출.
    전화/이메일/금액은 정규식으로, 그 외는 문장 정리 후 반환.
    페르소나가 문장으로 답해도 값만 깔끔하게 저장되도록."""
    import re
    msg = user_message.strip()
    low = target_key.lower()

    # ── 공통 전처리: 값 뒤에 붙은 추가 질문/요청 문장 제거 ──
    # 예: "BPHIPHMM. What should I do next?" -> "BPHIPHMM."
    #     "코드는 BFTVVNVX입니다. 다음은 무엇인가요?" -> "코드는 BFTVVNVX입니다."
    # 물음표가 있으면 그 앞까지만 사용 (질문은 값이 아님)
    for qm in ("?", "？"):
        if qm in msg:
            msg = msg.split(qm)[0].strip()
    # 물음표 제거 후, 마지막에 남은 질문성 절도 정리
    # "X. What next" 처럼 물음표가 없어도 뒤에 질문 키워드가 오면 그 앞까지
    _tail_phrases = ("what should", "what is the next", "what next", "what do i",
                     "다음 단계", "다음은", "어떻게 해", "무엇을 해", "next step")
    msg_low = msg.lower()
    cut = len(msg)
    for ph in _tail_phrases:
        idx = msg_low.find(ph)
        if idx > 0:
            cut = min(cut, idx)
    if cut < len(msg):
        # 그 앞 절까지만 (마침표 기준으로 깔끔히)
        head = msg[:cut].rstrip(" .,。")
        if head:
            msg = head

    # 전화번호: 숫자와 하이픈 패턴 추출
    if "phone" in low:
        m = re.search(r"\d{2,4}[-\s]?\d{3,4}[-\s]?\d{4}", msg)
        if m:
            return m.group().replace(" ", "")
        digits = re.sub(r"[^\d-]", "", msg)
        return digits or msg

    # 이메일: @ 포함 토큰 추출
    if "email" in low:
        m = re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", msg)
        if m:
            return m.group()
        return msg

    # SWIFT BIC / 은행코드: 영문+숫자 8~11자리 코드 추출
    if "code" in low or "swift" in low or "bic" in low:
        # SWIFT BIC: 알파벳 6자 + 영숫자 2자 (+ 선택 3자) = 8 또는 11자
        m = re.search(r"\b[A-Z]{4}[A-Z]{2}[A-Z0-9]{2}(?:[A-Z0-9]{3})?\b", msg.upper())
        if m:
            return m.group()
        # 일반 코드: 영숫자 덩어리 중 가장 긴 것
        tokens = re.findall(r"[A-Za-z0-9\-]{4,}", msg)
        if tokens:
            return max(tokens, key=len)
        return msg

    # 계좌번호 등 번호 필드: 숫자·하이픈 덩어리 추출
    if "id_no" in low or "passport" in low or "id" in low:
        m = re.search(r"[A-Za-z]*\d[A-Za-z0-9]*", msg)
        if m:
            return m.group()
        return msg

    if "_no" in low or "account" in low:
        m = re.search(r"[\d][\d\-]{3,}[\d]", msg)
        if m:
            return m.group()
        # 영숫자 계좌(해외)도 고려
        tokens = re.findall(r"[A-Za-z0-9\-]{5,}", msg)
        if tokens:
            return max(tokens, key=len)
        return msg

    # 금액: 점(.)·쉼표(,)는 천 단위 구분자로 보고 제거 후 추출
    if "amount" in low or "enrollment" in low:
        nums = re.findall(r"[\d.,]+", msg)
        cleaned = []
        for n in nums:
            digits = re.sub(r"[.,]", "", n)
            if digits.isdigit():
                cleaned.append(digits)
        if cleaned:
            return max(cleaned, key=len)
        return msg

    # 주소: 문장에서 주소 부분만 뽑기 (조사·질문 제거)
    if "address" in low:
        cleaned = msg
        parts = re.split(r"[.。\n]", cleaned)
        parts = [p.strip() for p in parts if p.strip()]
        if parts:
            addr_keywords = ("ro", "gu", "si", "dong", "구", "동", "로", "길", "시", "번지",
                             "street", "st", "ave", "city", "đường", "quận", "phố")
            scored = []
            for p in parts:
                score = 0
                if re.search(r"\d", p): score += 2
                pl = p.lower()
                score += sum(1 for kw in addr_keywords if kw in pl)
                scored.append((score, p))
            scored.sort(key=lambda x: -x[0])
            if scored[0][0] > 0:
                cleaned = scored[0][1]
        cleaned = re.sub(r"^.*?(주소는|주소가|주소|là|is|:)\s*", "", cleaned, count=1).strip()
        return cleaned or msg

    # 그 외(이름 등): 앞쪽 조사 제거하고 반환
    # "성명은 Maria Reyes입니다" -> "Maria Reyes"
    cleaned = re.sub(r"^.*?(성명은|이름은|name is|là|is|:)\s*", "", msg, count=1).strip()
    # 끝의 조사/서술 제거
    cleaned = re.sub(r"(입니다|이에요|예요|이다|입니당)\s*$", "", cleaned).strip()
    return cleaned or msg


def _looks_like_value(target_key: str, extracted: str, original_msg: str) -> bool:
    """추출된 값이 실제 그 필드의 값처럼 보이는지 검증.
    페르소나가 값 대신 질문/딴소리를 하면 False -> 저장 안 하고 재질문."""
    import re
    if not extracted or not str(extracted).strip():
        return False
    val = str(extracted).strip()
    low = target_key.lower()

    # 전화: 숫자 7자리 이상 포함
    if "phone" in low:
        return len(re.sub(r"\D", "", val)) >= 7
    # 이메일: @ 포함
    if "email" in low:
        return "@" in val and "." in val
    # 금액: 숫자 포함
    if "amount" in low or "enrollment" in low:
        return bool(re.search(r"\d", val))
    # SWIFT/코드: 영숫자 4자 이상, 공백 없는 토큰
    if "code" in low or "swift" in low or "bic" in low:
        return bool(re.fullmatch(r"[A-Za-z0-9\-]{4,}", val))
    # 계좌번호/번호: 숫자가 4개 이상 포함, 너무 길지 않음
    if ("_no" in low or "account" in low) and "name" not in low:
        return len(re.sub(r"\D", "", val)) >= 4 and len(val) < 40

    # 주소·이름 등: 추출된 값이 합리적인지 검증
    # (추출 단계에서 이미 조사·질문을 제거했으므로, 여기선 명백한 실패만 거름)
    # 물음표가 있으면 추출 실패(질문이 그대로 남음) -> 값 아님
    if "?" in val or "？" in val:
        return False
    # 지나치게 길면(추출 실패로 문장 통째) 값 아님 (주소도 100자면 충분)
    if len(val) > 100:
        return False
    # 추출값이 원문과 똑같고 원문이 매우 길면(추출 전혀 안 됨) 값 아님
    if len(original_msg.strip()) > 80 and val == original_msg.strip():
        return False
    return True


def _id_card_prompt(language):
    """신분증 업로드 요청 안내문 (다국어)."""
    prompts = {
        "Korean": "먼저 본인 확인을 위해 외국인등록증(신분증) 사진을 올려주세요.",
        "English": "First, please upload a photo of your ID card (ARC) for verification.",
        "Chinese": "首先，请上传您的身份证（外国人登录证）照片以进行身份验证。",
        "Japanese": "まず、本人確認のため在留カード（身分証）の写真をアップロードしてください。",
        "Vietnamese": "Trước tiên, vui lòng tải lên ảnh thẻ cư trú (ARC) để xác minh danh tính.",
        "Indonesian": "Pertama, silakan unggah foto kartu identitas (ARC) Anda untuk verifikasi.",
        "French": "Veuillez d'abord télécharger une photo de votre carte de séjour (ARC) pour vérification.",
        "Thai": "ขั้นแรก กรุณาอัปโหลดรูปบัตรประจำตัว (ARC) ของคุณเพื่อยืนยันตัวตน",
    }
    return prompts.get(language, prompts["English"])


def _group_done(backend_slots, gname):
    """해당 그룹이 하나라도 선택됐는지."""
    gdef = REQUIRED_GROUPS.get(gname) or OPTIONAL_GROUPS.get(gname)
    if not gdef:
        return True
    return any(backend_slots.get(k) == "V" for k in gdef["keys"])


def _group_result(scenario, current_form_state, backend_slots, gname, gdef, language):
    """그룹 선택 질문 결과 생성."""
    return _result(scenario, current_form_state, backend_slots,
                   group_question(gdef, language), False,
                   stage=f"group:{gname}",
                   extra={"choices": (gdef["options"] if language == "Korean"
                                      else gdef["options_en"]),
                          "choice_group": gname})


def _next_workplace_key(schema, backend_slots):
    """다음에 채울 직장 슬롯 키 반환. 주부/학생/직업미선택이면 None."""
    if _occupation_has_workplace(backend_slots) is not True:
        return None
    for k in ("opt_customer_address_office", "opt_customer_phone_office"):
        if k in schema.fields and not backend_slots.get(k):
            return k
    return None


def _next_group(backend_slots):
    """다음에 물어볼 그룹. 직업/통신사/우편물도 필수로 물어봄 (JSON은 opt_지만 코드에서 필수 처리).
    순서: 직업 -> 통신사 -> 우편물 -> 거래목적 -> 자금출처 -> 해외납세.
    (직업을 먼저 물어야 직장항목 조건부 판단 가능)
    """
    # 필수 취급하는 선택 그룹 (직업 먼저)
    forced = [("occupation", OPTIONAL_GROUPS["occupation"]),
              ("carrier", OPTIONAL_GROUPS["carrier"]),
              ("mailing", OPTIONAL_GROUPS["mailing"])]
    for gname, gdef in forced:
        if not any(backend_slots.get(k) == "V" for k in gdef["keys"]):
            return gname, gdef, True
    # 진짜 필수 그룹 (req_group)
    for gname in ("purpose", "source", "overseas"):
        gdef = REQUIRED_GROUPS[gname]
        if not any(backend_slots.get(k) == "V" for k in gdef["keys"]):
            return gname, gdef, True
    return None, None, None


def process_form_turn(extractor, data_dir, scenario, user_message,
                      current_form_state, history=None, language="", stage=""):
    """서식 처리 + 결과를 목표 언어로 번역(선택지/약관/질문문)."""
    result = _process_form_turn_inner(
        extractor, data_dir, scenario, user_message,
        current_form_state, history=history, language=language, stage=stage)
    # 선택지·약관·질문문을 목표 언어로 (한/영은 그대로)
    engine = getattr(extractor, "engine", None)
    return _translate_result(result, language, engine)


def _process_form_turn_inner(extractor, data_dir, scenario, user_message,
                             current_form_state, history=None, language="", stage=""):
    history = history or []
    form_id = SCENARIO_TO_FORM_ID.get(scenario)
    if not form_id:
        return {"bot_reply": "지원하지 않는 시나리오입니다.",
                "updated_form_state": current_form_state, "form_complete": False}

    schema = load_form_schema(form_id, data_dir)
    conversation = [*history, {"role": "user", "content": user_message}]
    backend_slots = front_to_backend(scenario, current_form_state)

    # 외화송금은 기존 단순 흐름
    if scenario != "account_opening":
        return _handle_remittance(extractor, schema, scenario, user_message,
                                  current_form_state, conversation, language, stage)

    # ===== 계좌개설 =====
    # 단계: 상품선택 / 그룹 선택 / 약관 동의 / 일반
    if stage == "product":
        # 고른 번호 -> 상품명 텍스트로 채움
        import re
        m = re.search(r"\d+", str(user_message))
        if m:
            idx = int(m.group()) - 1
            if 0 <= idx < len(PRODUCT_CHOICES["values"]):
                # form_state에는 사용자 언어로 저장 (화면 표시용).
                # PDF 렌더링 시에는 별도 번역 단계에서 처리됨.
                vals = PRODUCT_CHOICES.get("values_by_lang", {}).get(
                    language, PRODUCT_CHOICES["values"])
                backend_slots[PRODUCT_CHOICES["target_key"]] = vals[idx]
    elif stage.startswith("group:"):
        gname = stage.split(":", 1)[1]
        backend_slots = _apply_group_choice(gname, user_message, backend_slots)
    elif stage.startswith("text:"):
        # 특정 텍스트 슬롯을 받는 중 (전화/이메일/주소 등)
        target_key = stage.split(":", 1)[1]
        low = target_key.lower()
        # 패턴이 명확한 필드(전화/이메일/금액)는 정규식 우선 (빠르고 정확)
        pattern_field = any(p in low for p in ("phone", "email", "amount", "enrollment",
                                                "code", "swift", "bic", "_no", "account"))
        if "_no" in low and "id" not in low:
            pattern_field = True
        
        if pattern_field:
            extracted = _extract_text_value(target_key, user_message)
            # 정규식이 못 뽑으면(원문 그대로 반환) LLM 백업
            if extracted == user_message.strip() and hasattr(extractor, "extract_single"):
                fld = schema.fields.get(target_key)
                fdesc = (getattr(fld, "meaning_en", None) or target_key) if fld else target_key
                llm_val = extractor.extract_single(target_key, fdesc, user_message)
                if llm_val:
                    extracted = llm_val
        else:
            # 주소 등 애매한 필드: LLM 추출 우선 (군더더기 제거)
            fld = schema.fields.get(target_key)
            fdesc = (getattr(fld, "meaning_en", None) or
                     getattr(fld, "meaning", None) or target_key) if fld else target_key
            extracted = None
            if hasattr(extractor, "extract_single"):
                extracted = extractor.extract_single(target_key, fdesc, user_message)
            if not extracted:
                extracted = _extract_text_value(target_key, user_message)

        # 추출값 검증: 값이 유효해 보일 때만 저장.
        # 페르소나가 값 대신 질문/딴소리를 하면 저장 안 하고 같은 필드 다시 질문.
        if _looks_like_value(target_key, extracted, user_message):
            backend_slots[target_key] = extracted
        else:
            # 값을 못 받음 -> 같은 필드를 다시 물어봄 (중복 저장 방지)
            f = schema.fields.get(target_key)
            if f:
                return _result(scenario, current_form_state, backend_slots,
                               extractor.make_question(f, conversation,
                                                       user_language_hint=language),
                               False, stage=f"text:{target_key}")
    elif stage == "consent":
        if _interpret_consent(user_message):
            for k in ALL_AGREE_KEYS:
                backend_slots[k] = "V"
            backend_slots["req_consent_agreed"] = "Y"
            bot_reply = _done_message(extractor, conversation, language)
            res = _result(scenario, current_form_state, backend_slots, bot_reply,
                          True, stage="done")
            try:
                from app.services.db_store import save_application
                res["saved"] = save_application(scenario, res["updated_form_state"])
            except Exception as e:
                res["saved"] = {"saved": False, "error": str(e)}
            return res
        return _result(scenario, current_form_state, backend_slots,
                       _consent_prompt(language), False, stage="consent",
                       extra={"consent_items": consent_display(language),
                              "_reply_localized": True})
    else:
        # 일반 텍스트 추출
        # 건너뛰는 경우:
        # 1) stage="id_card": 이름·생년월일은 form_state에서 직접 채워짐
        # 2) stage="" + 이름·생년월일 있음 + 신호성 메시지: 프론트가 id_card stage를
        #    안 보내고 "업로드 완료" 같은 신호만 보낸 경우 (추출하면 오염됨)
        _is_id_card_signal = (
            stage == "id_card" or
            (not stage and
             backend_slots.get("req_customer_name") and
             backend_slots.get("req_customer_birth_date") and
             not any(c.isdigit() for c in user_message) and
             "@" not in user_message and
             len(user_message.strip()) < 30)
        )
        if not _is_id_card_signal:
            new_slots = extractor.extract(schema, conversation, backend_slots)
            backend_slots.update(new_slots)

    backend_slots = _autofill(scenario, backend_slots)

    # ===== 질문 순서 =====
    # (신분증으로 이름·생년월일) → 폰번호 → 통신사 → 이메일 → 집주소 → 직업
    #   → (직장있으면 직장주소 → 직장전화) → mailing → calling
    #   → 상품 → 금액 → 거래목적 → 자금원천 → 해외납세 → 약관

    # 0) 신분증 요청 (이름·생년월일이 아직 없으면 먼저 신분증으로 받기)
    #    stage="id_card"를 받은 적 있으면(=이미 요청함) 건너뜀: 사용자가 업로드 못 해도 진행
    has_name = backend_slots.get("req_customer_name")
    has_birth = backend_slots.get("req_customer_birth_date")
    if not (has_name and has_birth) and stage != "id_card":
        return _result(scenario, current_form_state, backend_slots,
                       _id_card_prompt(language), False, stage="id_card",
                       extra={"request_id_card": True})

    # 1) 기본 텍스트 (순서대로): 폰번호, 이메일, 집주소
    #    (이름·생년월일은 신분증/이전 단계에서 채워짐)
    for tkey in ("req_customer_mobile_phone", "opt_customer_email",
                 "req_customer_address_home"):
        f = schema.fields.get(tkey)
        if f and not backend_slots.get(tkey):
            # 통신사는 폰번호 다음에 물어야 하므로, 폰번호만 먼저
            if tkey == "opt_customer_email":
                # 이메일 전에 통신사 먼저 확인
                if not _group_done(backend_slots, "carrier"):
                    g = OPTIONAL_GROUPS["carrier"]
                    return _group_result(scenario, current_form_state, backend_slots,
                                         "carrier", g, language)
            return _result(scenario, current_form_state, backend_slots,
                           extractor.make_question(f, conversation,
                                                   user_language_hint=language),
                           False, stage=f"text:{tkey}")

    # 2) 직업 선택
    if not _group_done(backend_slots, "occupation"):
        g = OPTIONAL_GROUPS["occupation"]
        return _group_result(scenario, current_form_state, backend_slots,
                             "occupation", g, language)

    # 3) 직장 항목 (직업이 직장 있으면): 직장주소 → 직장전화
    wkey = _next_workplace_key(schema, backend_slots)
    if wkey:
        return _result(scenario, current_form_state, backend_slots,
                       extractor.make_question(schema.fields[wkey], conversation,
                                               user_language_hint=language),
                       False, stage=f"text:{wkey}")

    # 4) mailing → calling
    for gn in ("mailing", "calling"):
        if not _group_done(backend_slots, gn):
            g = OPTIONAL_GROUPS[gn]
            return _group_result(scenario, current_form_state, backend_slots,
                                 gn, g, language)

    # 5) 상품 선택
    if not backend_slots.get("req_product_name"):
        return _result(scenario, current_form_state, backend_slots,
                       product_question(language), False, stage="product",
                       extra={"choices": (PRODUCT_CHOICES["options"] if language == "Korean"
                                          else PRODUCT_CHOICES["options_en"]),
                              "choice_group": "product"})

    # 6) 초기 금액
    if not backend_slots.get("req_enrollment_amount"):
        amt_field = schema.fields.get("req_enrollment_amount")
        if amt_field:
            return _result(scenario, current_form_state, backend_slots,
                           extractor.make_question(amt_field, conversation,
                                                   user_language_hint=language),
                           False, stage="text:req_enrollment_amount")

    # 7) 필수 그룹: 거래목적 → 자금원천 → 해외납세
    for gn in ("purpose", "source", "overseas"):
        if not _group_done(backend_slots, gn):
            g = REQUIRED_GROUPS[gn]
            return _group_result(scenario, current_form_state, backend_slots,
                                 gn, g, language)

    # 8) 약관 동의
    return _result(scenario, current_form_state, backend_slots,
                   _consent_prompt(language), False, stage="consent",
                   extra={"consent_items": consent_display(language),
                          "_reply_localized": True})


def _apply_group_choice(gname, user_message, backend_slots):
    """사용자가 고른 번호를 해당 그룹 체크박스에 V 표시.
    버튼 누르면 번호가 오지만, 페르소나(A2A)는 'KT'처럼 텍스트로 답하므로
    번호 우선 매칭 후, 실패하면 선택지 텍스트로도 매칭."""
    gdef = REQUIRED_GROUPS.get(gname) or OPTIONAL_GROUPS.get(gname)
    
    if not gdef :
        if gname == "fee_payment":
            gdef = FEE_PAYMENT_GROUP
        elif gname == "fee_bearer":
            gdef = FEE_BEARER_GROUP
        
    if not gdef:
        return backend_slots
    import re
    msg = str(user_message).strip()
    keys = gdef["keys"]

    # 1) 번호 우선 (버튼 클릭 시 번호 전송) - 메시지가 숫자 하나일 때만
    m = re.fullmatch(r"\s*(\d+)\s*", msg)
    if m:
        idx = int(m.group(1)) - 1
        if 0 <= idx < len(keys):
            backend_slots[keys[idx]] = "V"
        return backend_slots

    # 2) 텍스트 매칭 (페르소나가 'KT', 'SKT' 등 글자로 답한 경우)
    #    정확 일치를 먼저 시도 (KT가 SKT에 포함돼 오인되는 것 방지)
    msg_low = msg.lower()
    opts = gdef.get("options", [])
    opts_en = gdef.get("options_en", [])

    def cands_for(i):
        c = []
        if i < len(opts):    c.append(str(opts[i]).lower())
        if i < len(opts_en): c.append(str(opts_en[i]).lower())
        return [x for x in c if x]

    # 2a) 정확 일치 (공백 제거 비교)
    msg_compact = msg_low.replace(" ", "")
    for i, key in enumerate(keys):
        for cand in cands_for(i):
            if msg_compact == cand.replace(" ", ""):
                backend_slots[key] = "V"
                return backend_slots

    # 2b) 단어 단위 포함 (메시지에 옵션이 독립 단어로 들어있는지)
    for i, key in enumerate(keys):
        for cand in cands_for(i):
            # 옵션이 메시지 안에 단어 경계로 등장하면 매칭
            if re.search(r"(^|\W)" + re.escape(cand) + r"($|\W)", msg_low):
                backend_slots[key] = "V"
                return backend_slots
    return backend_slots


# 외화송금 수수료 납부방법 (버튼으로 선택)


FEE_PAYMENT_GROUP = {
    "ask": {
        "Korean": "수수료 납부 방법을 선택해 주세요",
        "English": "Please select the fee payment method",
        "Vietnamese": "Vui lòng chọn phương thức thanh toán phí",
        "Chinese": "请选择手续费支付方式",
        "Japanese": "手数料の支払い方法を選択してください",
        "Indonesian": "Pilih metode pembayaran biaya",
        "French": "Choisissez le mode de paiement des frais",
        "Thai": "เลือกวิธีการชำระค่าธรรมเนียม",
    },
    "options": ["수수료 별도납부","수수료차감후 송금",],
    "options_en": ["Fee separate","Fee deducted",],
    "keys": ["req_fee_separate", "req_fee_deducted"],
}

FEE_BEARER_GROUP = {
    "ask": {
       "Korean": "결제은행 수수료는 누가 부담하시겠습니까?",
        "English": "Who will bear the reimbursing bank charges?",
        "Vietnamese": "Ai sẽ chịu phí ngân hàng trung gian?",
        "Chinese": "请选择中转银行手续费承担方。",
        "Japanese": "中継銀行手数料の負担者を選択してください。",
        "Indonesian": "Siapa yang akan menanggung biaya bank perantara?",
        "French": "Qui prendra en charge les frais de la banque intermédiaire ?",
        "Thai": "ใครจะเป็นผู้รับผิดชอบค่าธรรมเนียมธนาคารตัวกลาง",
    },
    "options": ["송금인 (OUR)", "수취인 (SHA)", "수취인 (BEN)"],
    "options_en": ["OUR (Sender)", "SHA (Shared)", "BEN (Recipient)"],
    "keys": ["req_fee_our", "req_fee_sha", "req_fee_ben"],
}


# 외화송금에서 city+country를 한 번에 받는 필드 쌍
# "도시, 나라" 형태로 받아서 각각 추출
_REMITTANCE_COMBINED_FIELDS = {
    # (city_key, country_key): 합쳐서 물어볼 때 쓸 설명
    ("req_beneficiary_city", "req_beneficiary_country"):
        "Beneficiary's city and country (e.g. 'Ho Chi Minh City, Vietnam')",
    ("req_beneficiary_bank_city", "req_beneficiary_bank_country"):
        "Beneficiary bank's city and country (e.g. 'Ho Chi Minh City, Vietnam')",
}

# 외화송금 필수 처리 순서 (이 순서대로 물어봄)
_REMITTANCE_QUESTION_ORDER = [
    "req_sender_name_eng",
    "req_sender_id_no",
    "req_sender_account_no",
    "req_sender_address",
    "req_sender_phone",
    "req_remittance_currency",
    "req_remittance_amount",
    "_fee_payment",
    "_fee_bearer",          # 수수료 선택 (버튼)
    "req_beneficiary_bank_name",
    "req_beneficiary_bank_code",        # SWIFT BIC (필수)
    "opt_beneficiary_bank_address",     # 은행 주소 (도시·나라 포함해서 받음)
    "req_beneficiary_account_no",
    "req_beneficiary_name",
    "req_relation_to_applicant",
    "req_beneficiary_address",          # 수취인 주소 (도시·나라 포함해서 받음)
    "req_purpose_of_payment",
    "req_withdrawal_account_no",
    "req_withdrawal_account_name",
]

# 주소 입력 시 도시·나라도 함께 추출해서 채울 city/country 키 매핑
# (주소 필드 -> 그 주소에서 도시/나라를 뽑아 넣을 키)
_ADDRESS_CITY_COUNTRY = {
    "opt_beneficiary_bank_address": ("req_beneficiary_bank_city", "req_beneficiary_bank_country"),
    "req_beneficiary_address": ("req_beneficiary_city", "req_beneficiary_country"),
}


def _fee_payment_done(backend_slots):
    return any(
        backend_slots.get(k) == "V"
        for k in FEE_PAYMENT_GROUP["keys"]
    )

def _fee_bearer_done(backend_slots):
    return any(
        backend_slots.get(k) == "V"
        for k in FEE_BEARER_GROUP["keys"]
    )


def _extract_city_country_from_address(address, city_key, country_key,
                                       backend_slots, extractor):
    """전체 주소에서 도시와 나라를 추출해 city/country 칸을 채움.
    예: '456 Rizal Street, Makati City, Philippines'
        -> city='Makati City', country='Philippines'
    주소는 그대로 두고, city/country만 추가로 채움."""
    if not address:
        return backend_slots
    addr = str(address).strip()
    # 쉼표로 분리: 보통 마지막이 나라, 그 앞이 도시
    parts = [p.strip() for p in addr.split(",") if p.strip()]
    if len(parts) >= 2:
        # 마지막 = 나라, 마지막 직전 = 도시 (가장 흔한 형식)
        backend_slots.setdefault(country_key, parts[-1])
        backend_slots.setdefault(city_key, parts[-2])
    elif hasattr(extractor, "extract_single"):
        # 쉼표가 없으면 LLM으로 추출
        city = extractor.extract_single(
            city_key,
            "City name only from this address. "
            "Example: '123 Rizal St Makati City Philippines' -> 'Makati City'",
            addr)
        country = extractor.extract_single(
            country_key,
            "Country name only from this address. "
            "Example: '123 Rizal St Makati City Philippines' -> 'Philippines'",
            addr)
        if city: backend_slots.setdefault(city_key, city)
        if country: backend_slots.setdefault(country_key, country)
    return backend_slots


def _split_city_country(text, city_key, country_key, backend_slots, extractor):
    """'도시, 나라' 형태에서 city와 country 추출."""
    import re
    text = text.strip()
    # 쉼표로 나누기
    parts = [p.strip() for p in text.split(",")]
    if len(parts) >= 2:
        backend_slots[city_key] = parts[0]
        backend_slots[country_key] = parts[-1]
    else:
        # 쉼표 없으면 LLM으로 추출 시도
        if hasattr(extractor, "extract_single"):
            city = extractor.extract_single(
            city_key,
            "City only. Do NOT include the country. "
            "Example: 'Ho Chi Minh City Vietnam' -> 'Ho Chi Minh City'",
            text,
            )
            country = extractor.extract_single(
            country_key,
            "Country only. Example: 'Ho Chi Minh City Vietnam' -> 'Vietnam'",
            text,
            )
            if city: backend_slots[city_key] = city
            if country: backend_slots[country_key] = country
        else:
            backend_slots[city_key] = text
    return backend_slots


def _handle_remittance(extractor, schema, scenario, user_message,
                       current_form_state, conversation, language, stage=""):
    backend_slots = front_to_backend(scenario, current_form_state)

    # 직전에 특정 필드/단계를 물어봤으면 답 처리
    if stage.startswith("text:"):
        target_key = stage.split(":", 1)[1]
        low = target_key.lower()

        pattern_field = any(p in low for p in ("phone", "amount", "_no", "year",
                                               "month", "day", "code", "swift", "bic"))
        if pattern_field:
            extracted = _extract_text_value(target_key, user_message)
            if extracted == user_message.strip() and hasattr(extractor, "extract_single"):
                fld = schema.fields.get(target_key)
                fdesc = (getattr(fld, "meaning_en", None) or target_key) if fld else target_key
                llm_val = extractor.extract_single(target_key, fdesc, user_message)
                if llm_val:
                    extracted = llm_val
        else:
            fld = schema.fields.get(target_key)
            fdesc = (getattr(fld, "meaning_en", None) or
                     getattr(fld, "meaning", None) or target_key) if fld else target_key
            extracted = None
            if hasattr(extractor, "extract_single"):
                extracted = extractor.extract_single(target_key, fdesc, user_message)
            if not extracted:
                extracted = _extract_text_value(target_key, user_message)
        if _looks_like_value(target_key, extracted, user_message):
            backend_slots[target_key] = extracted
            # 주소 필드면 도시·나라도 자동 추출해서 채움
            if target_key in _ADDRESS_CITY_COUNTRY:
                city_key, country_key = _ADDRESS_CITY_COUNTRY[target_key]
                backend_slots = _extract_city_country_from_address(
                    extracted, city_key, country_key, backend_slots, extractor)

    elif stage == "group:fee_payment":
        backend_slots = _apply_group_choice(
        "fee_payment",
        user_message,
        backend_slots,
        )

    elif stage == "group:fee_bearer":
        backend_slots = _apply_group_choice(
        "fee_bearer",
        user_message,
        backend_slots,
    )

    else:
        # 일반 추출
        new_slots = extractor.extract(schema, conversation, backend_slots)
        backend_slots.update(new_slots)

    backend_slots = _autofill(scenario, backend_slots)

    # ===== 질문 순서 (정해진 순서대로) =====
    # 주소 필드는 "도시·나라까지 포함해서" 한 번에 받도록 안내 문구 사용
    address_q = {
        "opt_beneficiary_bank_address": {
            "Korean": "받으실 분 거래은행의 주소를 입력해 주세요. 도시와 나라도 함께 적어주세요. (예: 123 Main St, Makati City, Philippines)",
            "English": "Enter the beneficiary bank's address, including the city and country. (e.g. 123 Main St, Makati City, Philippines)",
            "Vietnamese": "Vui lòng nhập địa chỉ ngân hàng thụ hưởng, bao gồm cả thành phố và quốc gia. (VD: 123 Main St, Makati City, Philippines)",
            "Chinese": "请输入收款银行的地址，包括城市和国家。（例：123 Main St, Makati City, Philippines）",
            "Japanese": "受取銀行の住所を、都市名と国名も含めて入力してください。（例：123 Main St, Makati City, Philippines）",
            "Indonesian": "Masukkan alamat bank penerima, termasuk kota dan negara. (contoh: 123 Main St, Makati City, Philippines)",
            "French": "Saisissez l'adresse de la banque bénéficiaire, y compris la ville et le pays. (ex. : 123 Main St, Makati City, Philippines)",
            "Thai": "กรอกที่อยู่ของธนาคารผู้รับ รวมถึงเมืองและประเทศ (ตัวอย่าง: 123 Main St, Makati City, Philippines)",
        },
        "req_beneficiary_address": {
            "Korean": "받으실 분의 주소를 입력해 주세요. 도시와 나라도 함께 적어주세요. (예: 456 Rizal St, Makati City, Philippines)",
            "English": "Enter the beneficiary's address, including the city and country. (e.g. 456 Rizal St, Makati City, Philippines)",
            "Vietnamese": "Vui lòng nhập địa chỉ người thụ hưởng, bao gồm cả thành phố và quốc gia. (VD: 456 Rizal St, Makati City, Philippines)",
            "Chinese": "请输入收款人的地址，包括城市和国家。（例：456 Rizal St, Makati City, Philippines）",
            "Japanese": "受取人の住所を、都市名と国名も含めて入力してください。（例：456 Rizal St, Makati City, Philippines）",
            "Indonesian": "Masukkan alamat penerima, termasuk kota dan negara. (contoh: 456 Rizal St, Makati City, Philippines)",
            "French": "Saisissez l'adresse du bénéficiaire, y compris la ville et le pays. (ex. : 456 Rizal St, Makati City, Philippines)",
            "Thai": "กรอกที่อยู่ของผู้รับ รวมถึงเมืองและประเทศ (ตัวอย่าง: 456 Rizal St, Makati City, Philippines)",
        },
    }

    for order_key in _REMITTANCE_QUESTION_ORDER:
        # 수수료 버튼
        if order_key == "_fee_payment":
            if not _fee_payment_done(backend_slots):
                q = FEE_PAYMENT_GROUP["ask"].get(
                language,
                FEE_PAYMENT_GROUP["ask"]["English"]
                )
                res = _result(
                    scenario,current_form_state,backend_slots,q,False,stage="group:fee_payment",
                    extra={"choices": (
                        FEE_PAYMENT_GROUP["options"]
                        if language == "Korean"
                        else FEE_PAYMENT_GROUP["options_en"]
                    ),
                    "choice_group": "fee_payment"
                    }
                )
                return _translate_result(res,language,getattr(extractor, "engine", None))
            continue

        if order_key == "_fee_bearer":
            if not _fee_bearer_done(backend_slots):
                q = FEE_BEARER_GROUP["ask"].get(
                language,
                FEE_BEARER_GROUP["ask"]["English"]
                )
                res = _result(scenario,current_form_state,backend_slots,q,False,stage="group:fee_bearer",
                    extra={"choices": (
                        FEE_BEARER_GROUP["options"]
                        if language == "Korean"
                        else FEE_BEARER_GROUP["options_en"]
                    ),
                    "choice_group": "fee_bearer"
                    }
                )
                return _translate_result(res,language,getattr(extractor, "engine", None))
            continue

        # 주소 필드: 도시·나라 포함 안내 문구로 질문
        if order_key in address_q:
            if not backend_slots.get(order_key):
                qm = address_q[order_key]
                q = qm.get(language, qm["English"])
                res = _result(scenario, current_form_state, backend_slots, q, False,
                              stage=f"text:{order_key}")
                return _translate_result(res, language, getattr(extractor, "engine", None))
            continue

        # opt_ 필드는 건너뜀 (필수 아님) — 단 reimbursing_bank는 물어봄
        fld = schema.fields.get(order_key)
        if not fld:
            continue
        if not backend_slots.get(order_key):
            next_key = order_key
            q = extractor.make_question(fld, conversation, user_language_hint=language)
            res = _result(scenario, current_form_state, backend_slots, q, False,
                          stage=f"text:{next_key}")
            return _translate_result(res, language, getattr(extractor, "engine", None))

    # 모든 필수 필드 완료
    missing = find_missing_required(schema, backend_slots)
    # city/country는 별도 처리했으니 제외
    real_missing = [f for f in missing
                    if f.key not in ("req_beneficiary_city", "req_beneficiary_country",
                                     "req_beneficiary_bank_city", "req_beneficiary_bank_country")]
    if real_missing:
        next_field = real_missing[0]
        q = extractor.make_question(next_field, conversation, user_language_hint=language)
        res = _result(scenario, current_form_state, backend_slots, q, False,
                      stage=f"text:{next_field.key}")
        return _translate_result(res, language, getattr(extractor, "engine", None))

    bot_reply = _done_message(extractor, conversation, language)
    res = _result(scenario, current_form_state, backend_slots, bot_reply, True, stage="done")
    try:
        from app.services.db_store import save_application
        res["saved"] = save_application(scenario, res["updated_form_state"])
    except Exception as e:
        res["saved"] = {"saved": False, "error": str(e)}
    return _translate_result(res, language, getattr(extractor, "engine", None))


def _result(scenario, current_form_state, backend_slots, bot_reply,
            form_complete, stage="", extra=None):
    merged = dict(current_form_state)
    merged.update(backend_to_front(scenario, backend_slots))
    out = {"bot_reply": bot_reply, "updated_form_state": merged,
           "form_complete": form_complete, "stage": stage}
    if extra:
        out.update(extra)
    return out


def _interpret_consent(msg):
    m = str(msg).strip().lower()
    yes = ["동의", "예", "네", "yes", "agree", "同意", "はい", "đồng ý", "ya", "ok", "확인"]
    return any(k in m for k in yes) or m == "y"


def _consent_prompt(language):
    items = consent_display(language)
    body = "\n".join(f"  · {it}" for it in items)
    head = {
        "Korean": "모든 정보가 입력되었습니다. 아래 약관에 모두 동의하시면 '동의'를 입력해 주세요:",
        "English": "All information collected. Type 'agree' to consent to all terms below:",
        "Chinese": "所有信息已填写。同意以下全部条款请输入'同意':",
        "Japanese": "全ての情報が入力されました。下記全てに同意する場合「同意」と入力してください:",
        "Vietnamese": "Đã thu thập đủ thông tin. Gõ 'đồng ý' để chấp thuận tất cả điều khoản:",
        "Indonesian": "Semua informasi terkumpul. Ketik 'ya' untuk menyetujui semua ketentuan:",
        "French": "Toutes les informations sont collectées. Tapez « accepter » pour consentir à toutes les conditions :",
        "Thai": "รวบรวมข้อมูลครบถ้วนแล้ว พิมพ์ 'ตกลง' เพื่อยอมรับเงื่อนไขทั้งหมด:",
    }.get(language, "All information collected. Type 'agree' to consent:")
    return f"{head}\n{body}"


def _done_message(extractor, conversation, language=""):
    lang = language or extractor._detect_language(conversation)
    system = (
        "You are a friendly bank assistant. The form is complete and the customer "
        f"agreed to all terms. Write ONE short sentence in {lang} saying the "
        "application is complete and they can now generate/submit the form. "
        "Output only the sentence."
    )
    messages = [{"role": "system", "content": system},
                {"role": "user", "content": f"(in {lang})"}]
    return extractor.engine.generate(messages, temperature=0.3, max_new_tokens=80)
