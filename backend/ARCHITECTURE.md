# 통합 아키텍처 (서식 + 상담)

## 전체 구조
```
                  POST /api/chat
                       │
              ┌────────┴────────┐
         scenario?              scenario?
     account_opening,        troubleshooting
        remittance               │
            │                    │
     [form_handler]         [consult_rag]
     서식 추출+재질문         상담 RAG 답변
            │                    │
            └────────┬───────────┘
                [LLMEngine]  ← 모델 1개 공유 (핵심!)
                  Qwen 3B/7B

         POST /api/render → 한국어 제출용 PDF
```

## 핵심: 모델 공유
- `LLMEngine`이 Qwen 1개를 감싸고, 서식 추출기와 상담 RAG가 **같은 엔진**을 주입받음.
- 코랩 GPU 메모리 절약: 모델을 한 번만 로드.

## 모듈
| 파일 | 역할 |
|------|------|
| `services/llm_engine.py` | 모델 1개 공유 래퍼 |
| `services/slot_extractor_hf.py` | 서식 슬롯 추출 + 다국어 재질문 |
| `services/form_handler.py` | stateless 서식 처리 (form_state 주고받음) |
| `services/consult_rag.py` | 트러블슈팅 상담 RAG |
| `services/pdf_renderer.py` | 한국어 제출용 PDF |
| `core/field_mapping.py` | 프론트 필드명 ↔ 백엔드 슬롯 매핑 |
| `main.py` | /api/chat 분기 + /api/render |

## API
- `POST /api/chat` — scenario로 서식/상담 분기, form_state 주고받음 (stateless)
- `POST /api/render` — 채워진 form_state → 한국어 제출용 PDF
- `POST /api/ocr-arc` — 신분증 OCR (추후 구현)

## PDF 전략 (선택 2)
- **확인용:** 프론트가 form_state(JSON)를 영어 라벨로 화면 표시
- **제출용:** 백엔드가 /api/render로 한국어 하나은행 PDF 생성

## 서비스 초기화 (코랩/서버)
```python
from app.main import init_services
init_services(extractor, consultant)  # 공유 엔진 기반
```

## 미구현 / TODO
- [ ] /api/ocr-arc (EasyOCR)
- [ ] 상담 RAG에 실제 ChromaDB 연결 (build_db 산출물)
- [ ] 3B → 7B 정확도 재검증 (코랩 결제 후)
- [ ] A2A 데모 스크립트 (카드차단 페르소나)
