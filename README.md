# Banky — 다국어 은행 챗봇

외국인을 위한 다국어(한/영/중/일/베트남/태국/프랑스) 은행 챗봇입니다.
계좌 개설 서식 자동완성, 외화 송금 신청서 작성, 일반 은행 상담을 지원합니다.
대학생 학회 인사이트(Insight) 2차 인사이콘(경진대회) 프로젝트입니다.

## 데모 영상

- 계좌 개설 데모: https://youtu.be/DQAWZhw36Ek
- 해외 송금 데모: https://youtu.be/LCpXjMtz130
- 일반 채팅 데모: https://youtu.be/verNWZtXRYA

## 구조

```
banky-chatbot/
├── frontend/         # 챗봇 웹 화면 (Docker + nginx)
├── backend/          # FastAPI 백엔드 — 서식 인식/작성, RAG 상담, LLM 연동
├── model/            # 모델 파인튜닝 · RAG 프롬프트 엔지니어링 · 서빙 노트북
├── data-labeling/    # 은행 서식 위치 라벨링 도구 및 라벨 데이터
├── persona/          # 페르소나 기반 대화 스크립트
├── docs/             # 발표/데모 자료
└── docker-compose.yml
```

## 아키텍처

전체 구조는 **웹 화면(Docker)** 이 **모델 서버(Colab, GPU)** 에 연결되어 동작합니다.

1. `model/banky_model_notebook.ipynb` 를 Colab(T4 GPU)에서 실행 → 백엔드+모델 서버 기동, 외부 접속 주소 발급
2. `docker compose up` 으로 `frontend/` 실행 → `http://localhost:3000` 에서 챗봇 화면 접속
3. 챗봇 화면의 서버 설정에 1번에서 발급된 주소 입력

모델 파인튜닝은 `model/파인튜닝.ipynb`, RAG 기반 규정집 프롬프트 엔지니어링은
`model/프롬프트_엔지니어링_규정집_RAG.ipynb` 에서 진행했습니다.

## 포함하지 않은 것

- 파인튜닝된 LoRA 모델 가중치(`adapter_model.safetensors`) 및 RAG 벡터스토어 — 코드 산출물이라 용량(각 150MB+) 문제로 제외
- 데모 원본 영상 — 용량 문제로 제외, 유튜브 링크로 대체 예정

## 기술 스택

FastAPI, LangChain(RAG), LoRA Fine-tuning, HuggingFace Transformers, OCR, Docker/nginx
