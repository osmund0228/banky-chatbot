# 은행 서식 자동완성 백엔드 (계좌개설 / 외화송금)

다국어 챗봇이 외국인 고객 발화에서 정보를 추출해, 빈 PDF 서식의 정확한 좌표에
텍스트·서명·체크를 자동 삽입하는 FastAPI 백엔드.

## 지원 서식 (2종)
- `account_opening` — 계좌개설신청서(외국인용), 2페이지
- `foreign_remittance` — 외화송금신청서, 1페이지

## 처리 흐름
```
다국어 발화 → POST /forms/{sid}/chat
   → SlotExtractor: 발화에서 슬롯값 추출 (원문 보존)
   → 빈 필수 슬롯 있으면 → 사용자 '언어로' 재질문
   → 모두 채워지면 completed
→ POST /forms/{sid}/render → 서명/체크 첨부 → 완성 PDF
```

## 모듈
| 파일 | 역할 |
|------|------|
| `core/slot_schema.py` | 좌표 JSON 로드, 멀티페이지 병합, 필드타입(텍스트/서명/체크박스) 판별 |
| `core/field_meanings.py` | 각 label의 한국어 의미 (다국어 재질문의 기반) |
| `services/slot_extractor.py` | 발화→슬롯 추출 + 다국어 재질문 생성 |
| `services/pdf_renderer.py` | 좌표에 텍스트/서명(좌우분할)/체크 삽입 |
| `services/session_manager.py` | 멀티턴 슬롯 누적 + 재질문 루프 |
| `main.py` | FastAPI 엔드포인트 + CORS |

## 데이터 배치 (`app/data/`)
- 좌표 JSON: 파일명은 `core/slot_schema.py`의 `FORM_REGISTRY`에 등록된 그대로
  - `외화송금신청서_하나은행_page_0_labels.json`
  - `계좌개설신청서_외국인용_하나은행_page_0_labels.json`
  - `계좌개설신청서_외국인용_하나은행_page_1_labels.json`
- 빈 PDF: `foreign_remittance.pdf`, `account_opening.pdf`
  - **주의:** PDF 크기가 좌표 라벨 해상도(약 900×1100px)와 다르면
    `render_form(scale=...)`로 보정 필요.

## 필드 타입 자동 분류
- **text**: 일반 입력 → 대화로 수집, 재질문 대상
- **signature**: label에 sig/signature → 박스 좌우 분할(이름+서명이미지), 대화 대상 아님
- **checkbox**: label에 chk 또는 박스 ≤20px → 체크표시(V), 대화 대상 아님

## LLM 설정
`main.py`의 SlotExtractor에서 환경에 맞게 변경:
```python
SlotExtractor(base_url="...", model="...", api_key="...")
```
- 코랩 vLLM: `base_url="http://localhost:8000/v1"`, `api_key="EMPTY"`
- 서버리스(Together/DeepInfra 등): 해당 base_url + 실제 api_key
- 권장 모델: Qwen2.5-7B-Instruct (T4면 3B, 코랩프로면 7B)

## 실행
```bash
pip install fastapi uvicorn pymupdf pydantic openai
uvicorn app.main:app --reload --port 8080
```

## 검증 완료
- 두 서식 좌표 JSON 로드 (외화송금 30필드 / 계좌개설 40필드, 2페이지 병합)
- 필드 타입 분류 (텍스트/서명/체크박스)
- PDF 렌더링: 텍스트, 서명 좌우분할, 체크박스, 날짜 분리, 한글/영문/베트남식 이름

## 미검증 / TODO
- [ ] 실제 LLM 연결 후 슬롯 추출 정확도 (가장 중요)
- [ ] 빈 서식 PDF 확보 및 scale 보정값 확정
- [ ] 언어 감지 자동화 (현재 start에서 language 지정 or 모델 추론)
- [ ] 세션 저장소 Redis 전환 (현재 인메모리)

## 코랩 검증 방법 (검증_노트북.ipynb)

실제 LLM으로 전체 파이프라인(발화→추출→재질문→PDF)을 검증하려면:

1. 코랩에서 **런타임 → GPU(T4)** 설정
2. `검증_노트북.ipynb`를 코랩에 업로드
3. `bank_form_filler.zip`을 노트북과 같은 위치에 업로드
4. 셀을 위에서 아래로 순서대로 실행

노트북 구성:
- 0~3단계: GPU 확인, 설치, 코드 업로드, Qwen 로드(transformers)
- 4단계: 슬롯 추출 단독 테스트 (베트남어 발화)
- 5단계: **전체 파이프라인** — 페르소나 발화 주입 → 추출/재질문/누적
- 6단계: PDF 생성 + 노트북에서 바로 미리보기
- 7단계: 직접 타이핑 대화 모드
- 8단계: 계좌개설 서식 테스트

### vLLM vs transformers
- 운영(서버): `slot_extractor.py` (vLLM, OpenAI 호환)
- 코랩 검증: `slot_extractor_hf.py` (transformers 직접 로드)
- 두 추출기는 동일 인터페이스(extract, make_question)라
  SessionManager가 그대로 둘 다 사용 가능.
