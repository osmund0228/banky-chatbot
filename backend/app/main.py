"""
FastAPI 통합 API - 은행 다국어 챗봇 (서식 + 상담 분기)

엔드포인트:
  POST /api/chat    통합 대화 (scenario로 서식/상담 분기)
  POST /api/render  완성된 서식 -> 한국어 제출용 PDF
  POST /api/ocr-arc 신분증 OCR (추후 구현)

scenario:
  - account_opening / remittance : 서식 자동완성 (form_handler)
  - troubleshooting              : 상담 RAG (consult_rag)

모델 공유: 서식 추출기와 상담 RAG가 같은 LLMEngine을 사용.
※ engine/extractor/consultant는 앱 기동 시 init_services()로 주입.
"""
from __future__ import annotations

import base64
from pathlib import Path

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel

from app.core.slot_schema import load_form_schema
from app.core.field_mapping import front_to_backend, SCENARIO_TO_FORM_ID
from app.services.form_handler import process_form_turn
from app.services.pdf_renderer import render_form

app = FastAPI(title="Bank Multilingual Chatbot API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)

DATA_DIR = str(Path(__file__).parent / "data")

# ===== 서비스 핸들 (init_services로 주입) =====
_services = {"extractor": None, "consultant": None}


def init_services(extractor, consultant):
    """코랩/서버 기동 시 호출. 공유 엔진 기반 추출기·상담기를 주입."""
    _services["extractor"] = extractor
    _services["consultant"] = consultant


# ===== 요청/응답 모델 =====
class ChatRequest(BaseModel):
    scenario: str                       # account_opening | remittance | troubleshooting
    user_message: str
    current_form_state: dict = {}
    history: list[dict] = []            # [{"role","content"}, ...] 선택
    language: str = ""                  # 프론트에서 선택한 언어 (예: "Chinese"). 비면 자동 감지
    stage: str = ""                     # 진행 단계 ("", "consent"). 응답의 stage를 다음 요청에 그대로


class ChatResponse(BaseModel):
    bot_reply: str
    updated_form_state: dict
    form_complete: bool
    stage: str = ""                     # "", "consent", "done"
    choices: list = []                  # 번호 선택지가 있으면 (예: 통신사, 우편물수령처)
    choice_field: str = ""              # 어느 항목의 선택지인지
    consent_items: list = []            # 약관 동의 항목들 (stage=consent일 때)
    saved: dict = {}                    # DB 저장 결과 (완료 시 {saved, id, summary})
    quick_links: list = []              # 빠른이동 버튼 [{"label","scenario"}, ...]
                                        #  상담(시나리오3)에서 계좌개설/외화송금으로 유도 시


class RenderRequest(BaseModel):
    scenario: str
    form_state: dict                    # 프론트 필드명으로 채워진 전체
    # 서명: 문자열(단일 base64) 또는 딕셔너리({label: base64}) 둘 다 허용
    #  - 프론트가 "signatures": "iVBOR..." (문자열 하나)로 보내면 자동 분배
    #  - "signatures": {"signature": "..."} 또는 개별 label도 가능
    signatures: dict | str = {}
    checks: dict = {}                   # {백엔드 체크label: bool}


# ===== /api/chat : 통합 분기 =====
def _process_chat(payload: dict) -> dict:
    """채팅 한 턴 처리 (HTTP/websocket 공통).
    payload: {scenario, user_message, current_form_state, history, language, stage}
    반환: dict (bot_reply, updated_form_state, form_complete, stage, choices...)
    """
    extractor = _services["extractor"]
    consultant = _services["consultant"]

    scenario = payload.get("scenario", "")
    user_message = payload.get("user_message", "")
    current_form_state = payload.get("current_form_state", {}) or {}
    history = payload.get("history", []) or []
    # language는 payload 최상위에 오는 게 기본이지만, 프론트가 form_state 안에
    # 넣어 보내는 경우도 있어 양쪽 모두 확인한다(최상위 우선). 둘 다 없으면 ""→자동감지.
    language = (payload.get("language", "")
                or current_form_state.get("language", "")
                or "")
    stage = payload.get("stage", "") or ""

    # --- 트러블슈팅: 상담 RAG ---
    if scenario == "troubleshooting":
        if consultant is None:
            return {"error": "상담 서비스 미초기화"}
        result = consultant.answer(user_message, history, language=language)
        # answer()는 {"bot_reply","quick_links"} dict 반환 (구버전 str도 호환)
        if isinstance(result, dict):
            bot_reply = result.get("bot_reply", "")
            quick_links = result.get("quick_links", [])
        else:
            bot_reply, quick_links = result, []
        return {"bot_reply": bot_reply, "updated_form_state": {},
                "form_complete": False, "stage": "", "quick_links": quick_links}

    # --- 서식: account_opening / remittance ---
    if scenario not in SCENARIO_TO_FORM_ID:
        return {"error": f"지원하지 않는 시나리오: {scenario}"}
    if extractor is None:
        return {"error": "서식 서비스 미초기화"}

    result = process_form_turn(
        extractor, DATA_DIR, scenario,
        user_message, current_form_state, history,
        language=language, stage=stage,
    )
    return {
        "bot_reply": result["bot_reply"],
        "updated_form_state": result["updated_form_state"],
        "form_complete": result["form_complete"],
        "stage": result.get("stage", ""),
        "choices": result.get("choices", []),
        "choice_field": result.get("choice_field", ""),
        "consent_items": result.get("consent_items", []),
        "saved": result.get("saved", {}),
    }


@app.post("/api/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    """HTTP 방식 (테스트/호환용)."""
    result = _process_chat(req.model_dump())
    if "error" in result:
        code = 503 if "미초기화" in result["error"] else 400
        raise HTTPException(code, result["error"])
    return ChatResponse(**result)


@app.websocket("/ws/chat")
async def ws_chat(websocket: WebSocket):
    """WebSocket 방식 (프론트 연결용).
    프론트가 JSON을 보내면 같은 형식으로 응답.
    연결을 유지하며 여러 턴을 주고받는다.
    """
    await websocket.accept()
    try:
        while True:
            payload = await websocket.receive_json()
            result = _process_chat(payload)
            await websocket.send_json(result)
    except WebSocketDisconnect:
        pass
    except Exception as e:
        # 에러가 나도 연결을 닫고 메시지 전달
        try:
            await websocket.send_json({"error": str(e)})
        except Exception:
            pass


# ===== /api/render : 한국어 제출용 PDF =====
@app.post("/api/render")
def render(req: RenderRequest):
    form_id = SCENARIO_TO_FORM_ID.get(req.scenario)
    if not form_id:
        raise HTTPException(400, f"PDF 미지원 시나리오: {req.scenario}")

    schema = load_form_schema(form_id, DATA_DIR)
    # 프론트 필드명 -> 백엔드 슬롯
    backend_slots = front_to_backend(req.scenario, req.form_state)
    # 서명란 이름 등 자동 채움 재적용 (이름 -> 신청인/예금주 서명란 텍스트)
    try:
        from app.services.form_handler import _autofill
        backend_slots = _autofill(req.scenario, backend_slots)
    except Exception:
        pass

    # 서명 정규화: 문자열 하나로 오면 {"signature": ...}로 변환
    raw_sigs = req.signatures
    if isinstance(raw_sigs, str):
        raw_sigs = {"signature": raw_sigs} if raw_sigs.strip() else {}
    # base64 디코딩 (data:image/png;base64, 접두사가 있으면 제거)
    signatures = {}
    for k, v in raw_sigs.items():
        if not v:
            continue
        if isinstance(v, str) and "," in v and v.strip().startswith("data:"):
            v = v.split(",", 1)[1]   # data URL 접두사 제거
        try:
            signatures[k] = base64.b64decode(v)
        except Exception:
            continue

    # 서명 자동 분배: 'signature' 하나면 필요한 칸에 복사
    # (계좌개설/외화송금에서 같은 사람 서명을 여러 칸에 넣음)
    signatures = _distribute_signature(req.scenario, signatures)

    # PDF 작성 언어로 텍스트 값 번역 (계좌=영어, 송금=한국어)
    extractor = _services.get("extractor")
    if extractor is not None:
        try:
            from app.services.pdf_translate import translate_form_values
            backend_slots = translate_form_values(req.scenario, backend_slots,
                                                  extractor.engine)
        except Exception:
            pass  # 번역 실패해도 원본으로 PDF 생성

    pdf_bytes = render_form(schema, backend_slots,
                            signatures=signatures, checks=req.checks)
    return Response(
        content=pdf_bytes, media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{form_id}_filled.pdf"'},
    )


# 시나리오별 '같은 서명을 넣을 칸' 목록 (상품 1개 가정)
SIGNATURE_TARGETS = {
    "account_opening": [
        "req_applicant_signature_p0",      # 1페이지 맨아래 신청인
        "req_confirm_info_inquiry_sig",    # ①번 상품 줄 확인
        "req_depositor_final_signature",   # 2페이지 예금주
    ],
    "remittance": [
        "req_applicant_signature",
        "req_withdrawal_signature",
    ],
}


def _distribute_signature(scenario: str, signatures: dict) -> dict:
    """프론트가 'signature' 하나만 보내면 필요한 모든 칸에 복사.
    이미 개별 키로 보냈으면 그대로 사용 (유연성).
    """
    targets = SIGNATURE_TARGETS.get(scenario, [])
    if not targets:
        return signatures
    # 'signature'(통합) 키가 있으면 그걸 모든 타겟에 복사
    one = signatures.get("signature")
    if one is not None:
        out = dict(signatures)
        for key in targets:
            out.setdefault(key, one)   # 이미 개별 지정된 건 유지
        out.pop("signature", None)     # 통합 키는 제거
        return out
    return signatures


# ===== /api/ocr-arc : 외국인등록증 OCR (로컬 처리) =====
@app.post("/api/ocr-arc")
async def ocr_arc(file: UploadFile = File(...), language: str = Form("")):
    """외국인등록증 이미지 -> {name, birth_date, arc_number, visa_type, nationality}.
    EasyOCR(로컬) + Qwen(로컬). 신분증이 외부로 나가지 않음.
    language를 받으면 완료 메시지를 그 언어로 함께 반환.
    """
    extractor = _services["extractor"]
    if extractor is None:
        raise HTTPException(503, "서비스 미초기화")
    try:
        image_bytes = await file.read()
        from app.services.ocr_arc import extract_id_info
        # extractor.engine = 로컬 Qwen (LLMEngine)
        result = extract_id_info(image_bytes, extractor.engine)
        return {"status": "success", "data": result,
                "message": _ocr_done_message(language)}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def _ocr_done_message(language: str) -> str:
    """신분증 인식 완료 메시지 (다국어)."""
    msgs = {
        "Korean": "신분증 인식이 완료되었습니다.",
        "English": "Your ID card has been verified.",
        "Chinese": "身份证识别已完成。",
        "Japanese": "身分証の認識が完了しました。",
        "Vietnamese": "Đã xác minh thẻ cư trú của bạn.",
        "Indonesian": "Kartu identitas Anda telah diverifikasi.",
        "French": "Votre pièce d'identité a été vérifiée.",
        "Spanish": "Su documento de identidad ha sido verificado.",
        "Thai": "ยืนยันบัตรประจำตัวของคุณเรียบร้อยแล้ว",
    }
    return msgs.get(language, msgs["English"])


@app.get("/api/applications")
def applications():
    """저장된 신청 목록 조회 (데모: DB에 쌓인 것 보여주기)."""
    from app.services.db_store import list_applications, count_applications
    return {"count": count_applications(), "items": list_applications()}


@app.get("/health")
def health():
    return {
        "status": "ok",
        "extractor": _services["extractor"] is not None,
        "consultant": _services["consultant"] is not None,
    }
