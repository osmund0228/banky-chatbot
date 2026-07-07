"""
트러블슈팅(시나리오3: 그 외 규정·은행 업무) 상담 RAG — '뱅키2' 로직 포팅 버전

프롬프트 엔지니어가 전달한 `뱅키모델2.ipynb`의 BankySession.chat() 을 그대로 옮긴 것.
변경점은 단 하나: 모델을 직접 generate 하지 않고, 백엔드의 공유 LLMEngine을 사용한다.
(코랩 GPU 메모리 절약 — 모델 1개 공유 원칙 유지)

핵심 보존/개선 사항:
- [가드레일 1]   계좌개설/외화송금 키워드 → 고정 리다이렉트 (LLM 호출 전, 빠름)
- [가드레일 1]   금리/대출/환율/주식/투자 → 환각 차단 + 상담원 안내
- [가드레일 1.5] 키워드로 안 잡힌 발화 → 학습된 LLM이 의도 분류(ACCOUNT/REMIT/OTHER).
                 다국어(한·영·중·일·베·인니)·띄어쓰기 변형도 의미 기반으로 라우팅.
- [가드레일 2]   FAISS(LangChain) similarity_search → 규정집 청크를 system에 주입
- [가드레일 3]   ★★은행 / OO은행 → 인사이트뱅크 치환

RAG 백엔드: LangChain FAISS + jhgan/ko-sroberta-multitask (뱅키2와 동일).
  ※ 기존 ChromaDB/e5 방식과 다름. load_banky_vectorstore()로 사전빌드 store 로드.
  vectorstore가 없으면 RAG 컨텍스트 없이 답변(폴백)하되, 가드레일은 항상 동작.
"""
from __future__ import annotations


class ConsultRAG:
    MAX_NEW_TOKENS = 200

    # 프롬프트팀 SYSTEM_TEMPLATE 원본 (가장 안정적이었던 1번 후보)
    SYSTEM_TEMPLATE = """You MUST write your ENTIRE reply in {language}. Even though the rules below are written in Korean, you must TRANSLATE their content into {language}. Never copy Korean text directly into your answer unless {language} is Korean.

당신은 인사이트뱅크의 친절하고 전문적인 AI 은행원 '뱅키(Banky)'입니다.
아래의 [사내 규정]과 [대화 기록]을 바탕으로 고객의 질문에 답변하세요.

## 뱅키의 행동 규칙
1. [사내 규정]을 참고하되, 그 내용을 반드시 {language}(으)로 번역해서 자연스럽게 답하세요. 규정의 한국어 문구를 그대로 베끼지 마세요.
2. 규정에 없는 일반적인 은행 업무는 학습된 지식으로 친절히 답하되, 확실하지 않은 구체적 수치·절차는 지어내지 마세요.
3. 고객의 이전 대화 맥락(이름 등)을 기억하고 대화에 반영하세요.
4. 고객이 질문한 내용에만 답변하세요. 규정의 모든 내용을 나열하지 마세요.
5. 한 번에 최대 3개의 핵심 안내만 제공하세요.
6. 고객이 이미 알고 있는 내용은 반복하지 마세요.
7. 답변은 실제 은행 상담사처럼 자연스럽고 간결하게 작성하세요.
8. 고객이 추가 질문을 하면 그때 다음 절차를 설명하세요.
9. 절대로 고객의 질문을 그대로 따라 말하거나 되풀이하지 마세요. 반드시 실질적인 답변·해결책·안내를 제공하세요.
10. 아래 규정이 질문과 관련 없어 보이면 규정에 얽매이지 말고, 은행원으로서 학습된 지식으로 도움이 되는 답을 하세요.

## 사내 규정 (참고용 — 반드시 {language}(으)로 번역해 전달)
{context}

[중요] 반드시 {language}(으)로만 답변하세요. 한국어 규정도 {language}(으)로 번역하세요. 첫 문장부터 {language}(으)로 작성하세요.
"""

    # ---- 가드레일 키워드 ----
    # 매칭은 _norm()으로 공백을 제거한 소문자 기준 → "계좌개설"/"계좌 개설" 모두 매칭.
    # 따라서 여기 키워드도 공백 없이 적는다. 다국어 챗봇이므로 영어도 함께 등록.
    REDIRECT_ACCOUNT = [
        "계좌개설", "계좌를개설", "통장만들", "통장개설", "신규계좌", "새통장", "계좌만들",
        "openanaccount", "openabankaccount", "bankaccount", "newaccount", "openaccount",
    ]
    REDIRECT_REMIT = [
        "외화송금", "해외송금", "해외로달러", "외환송금", "달러송금", "해외로돈", "해외이체",
        "sendmoneyabroad", "overseasremittance", "foreignremittance",
        "internationaltransfer", "wiretransfer", "remittance",
    ]
    BLOCK_HALLU = [
        "금리", "대출", "환율", "주식", "투자",
        "interestrate", "loan", "exchangerate", "stock", "invest",
    ]

    # ---- 리다이렉트/차단 메시지 (언어별 사전) ----
    # 약관처럼 언어별로 문장을 미리 정해둠. _msg(키, lang)로 선택, 없으면 English 폴백.
    MESSAGES = {
        "account": {
            "Korean": "계좌 개설은 전담 채팅에서 더 정확하게 안내해 드릴 수 있습니다! 아래 [① 계좌 개설] 버튼을 눌러 주세요.",
            "English": "We can help you open an account more accurately in the dedicated chat. Please tap the [① Open Account] button below.",
            "Chinese": "开户可以在专属聊天中为您更准确地办理。请点击下方的 [① 开户] 按钮。",
            "Japanese": "口座開設は専用チャットでより正確にご案内できます。下の [① 口座開設] ボタンを押してください。",
            "Vietnamese": "Việc mở tài khoản sẽ được hướng dẫn chính xác hơn trong cuộc trò chuyện chuyên biệt. Vui lòng nhấn nút [① Mở tài khoản] bên dưới.",
            "Indonesian": "Pembukaan rekening dapat kami bantu lebih akurat di obrolan khusus. Silakan ketuk tombol [① Buka Rekening] di bawah.",
            "French": "Nous pouvons vous aider à ouvrir un compte plus précisément dans le chat dédié. Veuillez appuyer sur le bouton [① Ouvrir un compte] ci-dessous.",
            "Thai": "การเปิดบัญชีสามารถให้บริการได้แม่นยำยิ่งขึ้นในแชทเฉพาะทาง กรุณากดปุ่ม [① เปิดบัญชี] ด้านล่าง",
        },
        "remit": {
            "Korean": "외화 송금은 전담 채팅에서 더 정확하게 안내해 드릴 수 있습니다! 아래 [② 외화 송금] 버튼을 눌러 주세요.",
            "English": "We can help you with overseas remittance more accurately in the dedicated chat. Please tap the [② Overseas Remittance] button below.",
            "Chinese": "外汇汇款可以在专属聊天中为您更准确地办理。请点击下方的 [② 外汇汇款] 按钮。",
            "Japanese": "外貨送金は専用チャットでより正確にご案内できます。下の [② 外貨送金] ボタンを押してください。",
            "Vietnamese": "Việc chuyển tiền ra nước ngoài sẽ được hướng dẫn chính xác hơn trong cuộc trò chuyện chuyên biệt. Vui lòng nhấn nút [② Chuyển tiền quốc tế] bên dưới.",
            "Indonesian": "Pengiriman uang ke luar negeri dapat kami bantu lebih akurat di obrolan khusus. Silakan ketuk tombol [② Kirim Uang ke Luar Negeri] di bawah.",
            "French": "Nous pouvons vous aider pour le virement à l'étranger plus précisément dans le chat dédié. Veuillez appuyer sur le bouton [② Virement international] ci-dessous.",
            "Thai": "การโอนเงินต่างประเทศสามารถให้บริการได้แม่นยำยิ่งขึ้นในแชทเฉพาะทาง กรุณากดปุ่ม [② โอนเงินต่างประเทศ] ด้านล่าง",
        },
        "block": {
            "Korean": "해당 내용은 제가 정확히 안내드리기 어려운 부분입니다. 전문 상담원(1588-0000) 연결을 도와드릴까요?",
            "English": "I'm unable to advise accurately on this. Would you like me to connect you to a specialist (1588-0000)?",
            "Chinese": "该内容我无法准确为您解答。需要为您转接专业客服(1588-0000)吗？",
            "Japanese": "こちらは正確にご案内が難しい内容です。専門相談員(1588-0000)へのおつなぎをご希望ですか？",
            "Vietnamese": "Tôi không thể tư vấn chính xác về nội dung này. Bạn có muốn tôi kết nối với chuyên viên (1588-0000) không?",
            "Indonesian": "Saya tidak dapat memberikan informasi akurat tentang hal ini. Apakah Anda ingin saya menghubungkan ke petugas spesialis (1588-0000)?",
            "French": "Je ne peux pas vous conseiller précisément sur ce point. Souhaitez-vous que je vous mette en relation avec un conseiller spécialisé (1588-0000) ?",
            "Thai": "เรื่องนี้ฉันไม่สามารถให้คำแนะนำได้อย่างถูกต้อง ต้องการให้ฉันโอนสายไปยังเจ้าหน้าที่ผู้เชี่ยวชาญ (1588-0000) หรือไม่",
        },
    }

    @classmethod
    def _msg(cls, key: str, lang: str) -> str:
        d = cls.MESSAGES[key]
        return d.get(lang, d["English"])

    # ---- 프론트로 보낼 빠른이동 버튼 신호 ----
    # 프론트 요청대로 단순 문자열 라벨 배열로 전달 → 프론트가 알아서 버튼 생성.
    # 예: quick_links = ["계좌개설"]  /  ["외화송금"]  /  [](버튼 없음)
    LINK_ACCOUNT = "계좌개설"
    LINK_REMIT = "외화송금"

    # ---- 의도 분류 프롬프트 ----
    # [가드레일 1.5] 키워드로 안 잡힌 발화를 학습된 LLM에게 의도 분류시킨다.
    # 어떤 언어(한/영/중/일/베/인니)로 들어와도 '의미'로 판단 → 다국어 라우팅.
    # 모델이 정해진 한 단어만 뱉도록 강제(다른 설명 금지).
    # ※ 프롬프트 엔지니어가 더 좋은 문구를 주면 이 상수만 교체하면 됨.
    INTENT_SYSTEM = """You are an intent classifier for a bank chatbot.
Read the user's message (it may be in any language: Korean, English, Chinese, Japanese, Vietnamese, Indonesian, French, Thai).
Classify the user's primary intent into exactly ONE of these labels:

- ACCOUNT : The user wants to OPEN/CREATE a new bank account or bankbook.
    Examples: "계좌 개설", "통장 만들기", "open an account", "ouvrir un compte",
    "เปิดบัญชี", "mở tài khoản", "开户", "口座開設", "buka rekening"
- REMIT   : The user wants to SEND money abroad (foreign/overseas remittance or transfer).
    Examples: "외화 송금", "해외 송금", "send money abroad", "virement à l'étranger",
    "โอนเงินต่างประเทศ", "chuyển tiền ra nước ngoài", "汇款到国外", "海外送金",
    "kirim uang ke luar negeri", "fill out the remittance form", "แบบฟอร์มโอนเงินต่างประเทศ"
- OTHER   : anything else (general banking questions, card issues, hours, rules, chit-chat, etc.)

IMPORTANT: ACCOUNT is about CREATING an account. REMIT is about SENDING money overseas.
Do not confuse them. If the message mentions sending/transferring money abroad or a
remittance form, it is REMIT, not ACCOUNT.

Rules:
- Output ONLY the single label word: ACCOUNT, REMIT, or OTHER.
- No explanation, no punctuation, no other text.
- If unsure, output OTHER."""

    # 분류기가 헷갈려 라벨 외 텍스트를 뱉어도 안전하게 파싱하기 위한 매핑
    _INTENT_LABELS = ("ACCOUNT", "REMIT", "OTHER")

    def __init__(self, engine, vectorstore=None, top_k: int = 1,
                 use_llm_router: bool = True):
        """
        engine:      공유 LLMEngine (시나리오1·2 추출기와 동일 모델)
        vectorstore: LangChain FAISS store (load_banky_vectorstore로 로드해 주입).
                     None이면 RAG 컨텍스트 없이 답변(폴백). 가드레일은 그대로 동작.
        top_k:       유사 규정 청크 검색 개수 (뱅키2 기본 1)
        use_llm_router: 키워드로 안 잡힌 발화를 LLM 의도분류로 한 번 더 거를지.
                     True면 다국어/띄어쓰기 변형까지 의미 기반 라우팅(추론 1회 추가).
                     False면 키워드 매칭만(빠르지만 변형에 약함).
        """
        self.engine = engine
        self.vectorstore = vectorstore
        self.top_k = top_k
        self.use_llm_router = use_llm_router
        
    
     # ---------- 언어 감지 (language 미전달 시 폴백) ----------
    @staticmethod
    def _detect_language(text: str) -> str:
        """발화의 언어를 영어 언어명으로 반환. 폼 추출기와 동일한 문자범위 기반.
        프론트가 language를 안 보냈을 때만 쓰는 폴백."""
        import re
        if not text:
            return "Korean"
        if re.search(r"[\u3040-\u30ff]", text):            # 히라가나/가타카나
            return "Japanese"
        if re.search(r"[\uac00-\ud7a3]", text):             # 한글
            return "Korean"
        if re.search(r"[\u0e00-\u0e7f]", text):             # 태국 문자
            return "Thai"
        if re.search(r"[\u4e00-\u9fff]", text):             # 한자(일/한 제외 후)
            return "Chinese"
        if re.search(r"[ăâđêôơưĂÂĐÊÔƠƯ]", text) or \
           re.search(r"[\u0300-\u0323]", text):             # 베트남어 성조
            return "Vietnamese"
        # 라틴 문자권 세분 (langdetect 있으면 사용, 없으면 English)
        try:
            from langdetect import detect
            code = detect(text)
            return {"en": "English", "fr": "French", "es": "Spanish",
                    "de": "German", "id": "Indonesian", "vi": "Vietnamese",
                    "pt": "Portuguese", "it": "Italian"}.get(code, "English")
        except Exception:
            return "English"

    # ---------- RAG 검색 (뱅키2 _retrieve 동일) ----------
    def _retrieve(self, query: str) -> str:
        if self.vectorstore is None:
            return ""
        try:
            docs = self.vectorstore.similarity_search(query, k=self.top_k)
            return "\n".join(d.page_content for d in docs)
        except Exception:
            return ""

    # ---------- 후처리 (가드레일 3) ----------
    @staticmethod
    def _normalize_bank_name(response: str) -> str:
        response = response.replace("★★은행으로", "인사이트뱅크로")
        response = response.replace("★★은행은", "인사이트뱅크는")
        response = response.replace("★★은행이", "인사이트뱅크가")
        response = response.replace("★★은행", "인사이트뱅크").replace("OO은행", "인사이트뱅크")
        return response

    # ---------- history 정리 (뱅키2 동일: 첫 대화 보존) ----------
    @staticmethod
    def _trim_history(history: list[dict]) -> list[dict]:
        h = list(history)
        while len(h) > 6:
            h.pop(2)
            h.pop(2)
        return h

    # ---------- 발화 정규화 (가드레일 매칭용) ----------
    @staticmethod
    def _norm(text: str) -> str:
        """공백 전부 제거 + 소문자화.
        '계좌 개설'/'계좌개설', 'open a bank account'/'openabankaccount'를
        같은 형태로 만들어 부분문자열 매칭이 띄어쓰기에 흔들리지 않게 한다.
        """
        return "".join(text.split()).lower()

    # ---------- LLM 의도 분류 (가드레일 1.5) ----------
    def _classify_intent(self, user_query: str) -> str:
        """학습된 LLM으로 발화 의도를 ACCOUNT / REMIT / OTHER 중 하나로 분류.
        키워드로 못 잡은 다국어·변형 발화를 의미 기반으로 라우팅하기 위함.
        분류 실패·예외 시 안전하게 'OTHER' 반환(=상담 계속 진행, 오라우팅 방지).
        """
        try:
            messages = [
                {"role": "system", "content": self.INTENT_SYSTEM},
                {"role": "user", "content": user_query},
            ]
            # 분류는 한 단어만 필요 → 짧게, 결정적으로(temperature=0)
            out = self.engine.generate(messages, temperature=0.0,
                                       max_new_tokens=5)
            up = out.strip().upper()
            # 모델이 라벨 외 텍스트를 섞어도 라벨만 골라냄
            for label in self._INTENT_LABELS:
                if label in up:
                    return label
            return "OTHER"
        except Exception:
            return "OTHER"

    # ---------- 메인 진입점 ----------
    def answer(self, user_query: str, history: list[dict] | None = None,
               language: str = "") -> dict:
        """
        상담 한 턴 처리. 반환은 dict:
            {"bot_reply": str, "quick_links": ["계좌개설"] 또는 ["외화송금"] 또는 []}
        quick_links 가 비어있지 않으면 프론트가 그 라벨로 버튼을 띄우고,
        사용자가 누르면 scenario 값으로 화면(시나리오)을 전환한다.

        history: [{"role","content"}, ...] — 프론트가 누적해 보내줌 (stateless).
        language: 시나리오3 규정 답변은 한국어 기준이라 사용 안 함(받기만 함).
        """
        history = history or []

        # 답변 언어를 가장 먼저 결정 (리다이렉트 메시지도 사용자 언어로 내보내기 위함).
        # 프론트가 보낸 language 우선, 없으면 발화에서 감지(폼 추출기와 동일 로직).
        lang = language or self._detect_language(user_query)

        # ====== [가드레일 1] LLM 호출 전 키워드 방어 (빠른 확실 케이스) ======
        # 공백 제거·소문자화한 발화로 매칭 → 띄어쓰기/대소문자 변형에 강함
        q = self._norm(user_query)
        if any(k in q for k in self.REDIRECT_ACCOUNT):
            return {"bot_reply": self._msg("account", lang),
                    "quick_links": [self.LINK_ACCOUNT]}
        if any(k in q for k in self.REDIRECT_REMIT):
            return {"bot_reply": self._msg("remit", lang),
                    "quick_links": [self.LINK_REMIT]}
        if any(k in q for k in self.BLOCK_HALLU):
            return {"bot_reply": self._msg("block", lang), "quick_links": []}

        # ====== [가드레일 1.5] LLM 의도 분류 (다국어/변형 케이스) ======
        # 키워드로 안 잡혔지만 의미상 계좌개설·외화송금이면 여기서 라우팅.
        # 어떤 언어로 들어와도 모델이 의미로 판단 → 베트남어/중국어 등도 커버.
        if self.use_llm_router:
            intent = self._classify_intent(user_query)
            if intent == "ACCOUNT":
                return {"bot_reply": self._msg("account", lang),
                        "quick_links": [self.LINK_ACCOUNT]}
            if intent == "REMIT":
                return {"bot_reply": self._msg("remit", lang),
                        "quick_links": [self.LINK_REMIT]}
            # OTHER면 그대로 아래 상담 RAG로 진행

        # ====== [가드레일 2] RAG + 생성 ======
        context = self._retrieve(user_query)
        system_prompt = self.SYSTEM_TEMPLATE.format(context=context, language=lang)

        # 프론트가 보낸 history + 이번 질문 (백엔드는 상태 저장 안 함)
        # 언어 지시를 '마지막 user 메시지'에도 덧붙인다. 모델은 직전 메시지에
        # 가장 강하게 반응하므로 system 지시만으로 언어가 새는 것을 크게 줄인다.
        user_turn = f"{user_query}\n\n(Reply ONLY in {lang}. 반드시 {lang}(으)로만 답변. 한국어 규정도 {lang}(으)로 번역.)"
        convo = self._trim_history([*history,
                                    {"role": "user", "content": user_turn}])
        messages = [{"role": "system", "content": system_prompt}, *convo]

        # 원본 BankySession이 "가장 자연스러웠던 1번 후보"로 검증한 생성 파라미터.
        # repetition_penalty=1.15가 핵심: 반복·되풀이를 억제해 답변 품질을 살린다.
        response = self.engine.generate(
            messages,
            temperature=0.1,
            max_new_tokens=self.MAX_NEW_TOKENS,
            top_p=0.9,
            repetition_penalty=1.15,
        )

        # ====== [가드레일 3] 은행명 치환 ======
        reply = self._normalize_bank_name(response)
        return {"bot_reply": reply, "quick_links": []}

    # ---------- 하위호환용: 문자열만 필요할 때 ----------
    def answer_text(self, user_query: str, history: list[dict] | None = None,
                    language: str = "") -> str:
        """quick_links 없이 답변 문자열만 반환 (구버전 호출 호환)."""
        return self.answer(user_query, history, language)["bot_reply"]


def load_banky_vectorstore(store_dir: str,
                           embed_model: str = "jhgan/ko-sroberta-multitask"):
    """
    프롬프트팀이 전달한 사전빌드 FAISS store(banky_vectorstore/) 로드 헬퍼.
    구성: index.faiss + index.pkl (LangChain FAISS.save_local 산출물)
    반환: LangChain FAISS vectorstore — ConsultRAG(vectorstore=...)에 주입.
    실패 시 None 반환 → 폴백 모드(가드레일만 동작).

    코랩 사용 예:
        vs = load_banky_vectorstore("/content/.../banky_vectorstore")
        consultant = ConsultRAG(engine=engine, vectorstore=vs)
    """
    try:
        import torch
        from langchain_community.embeddings import HuggingFaceEmbeddings
        from langchain_community.vectorstores import FAISS

        device = "cuda" if torch.cuda.is_available() else "cpu"
        embeddings = HuggingFaceEmbeddings(
            model_name=embed_model,
            model_kwargs={"device": device},
            encode_kwargs={"normalize_embeddings": True},
        )
        vs = FAISS.load_local(
            store_dir, embeddings,
            allow_dangerous_deserialization=True,  # 자체 빌드 pkl이라 허용
        )
        return vs
    except Exception as e:
        print(f"[ConsultRAG] 벡터스토어 로드 실패, 폴백 모드: {e}")
        return None


def build_banky_vectorstore(rules_file_path: str,
                            embed_model: str = "jhgan/ko-sroberta-multitask",
                            save_dir: str | None = None):
    """
    (선택) 규정집.txt 가 바뀌었을 때 store를 새로 빌드 — 뱅키2 셀2 로직 동일.
    '===' 섹션 단위로 청킹해 문맥 유실을 막는다.
    save_dir 주면 save_local 까지 수행. 반환: FAISS vectorstore.
    """
    import torch
    from langchain_text_splitters import CharacterTextSplitter
    from langchain_community.embeddings import HuggingFaceEmbeddings
    from langchain_community.vectorstores import FAISS

    with open(rules_file_path, "r", encoding="utf-8") as f:
        raw_text = f.read()

    chunks = CharacterTextSplitter(
        separator="===", chunk_size=2000, chunk_overlap=0
    ).split_text(raw_text)
    chunks = ["===" + c.strip() for c in chunks if len(c.strip()) > 10]

    device = "cuda" if torch.cuda.is_available() else "cpu"
    embeddings = HuggingFaceEmbeddings(
        model_name=embed_model,
        model_kwargs={"device": device},
        encode_kwargs={"normalize_embeddings": True},
    )
    vs = FAISS.from_texts(chunks, embeddings)
    if save_dir:
        vs.save_local(save_dir)
    return vs
