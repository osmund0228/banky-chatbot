# 📋 표준 필드 명세서 (Field Specification)

> **목적:** 프론트엔드 ↔ 백엔드가 `/api/chat`에서 주고받는 `form_state`의 필드명 표준
> **작성:** 백엔드 담당
> **버전:** v1

프론트와 백엔드가 **이 문서의 필드명을 그대로** 사용합니다.
`current_form_state` / `updated_form_state`의 key는 아래 표의 필드명을 씁니다.

---

## 🔑 핵심 규칙

1. **필드명은 이 문서 기준.** 프론트는 짧은 이름(`customer_name`)을 쓰고,
   백엔드가 내부에서 PDF 좌표용 이름으로 변환합니다. 프론트는 변환을 신경 쓸 필요 없음.
2. **값이 없으면 `null`.** 아직 안 받은 항목은 `null`로 주고받습니다.
   백엔드가 발화에서 알아내면 `updated_form_state`에서 채워 돌려줍니다.
3. **필수 항목이 모두 채워지면** 백엔드가 `form_complete: true`를 응답에 포함합니다.
   이때 프론트는 서명 입력 → PDF 생성 단계로 넘어갑니다. (아래 PDF 섹션 참고)
4. **서명/체크박스는 form_state에 없음.** 대화로 받지 않고 별도 단계에서 처리합니다.
   (서명은 사용자가 직접 그리고, 체크박스는 별도 UI)

---

## 1️⃣ 계좌개설 (`scenario: "account_opening"`)

### 필수 필드 (11개) — 모두 채워야 PDF 생성 가능
| 필드명 (key) | 의미 |
| --- | --- |
| `customer_name` | 고객 성명 |
| `birth_date` | 생년월일 |
| `mobile_phone` | 휴대폰 번호 |
| `address_home` | 자택 주소 |
| `mailing_to` | 우편물 수령처 |
| `occupation` | 직업 |
| `product_name` | 가입할 상품명 |
| `enrollment_amount` | 초기 가입(입금) 금액 |
| `app_month` | 신청 월 |
| `app_day` | 신청 일 |
| `app_year` | 신청 연도 |

### 선택 필드 (19개) — 있으면 채우고, 없으면 `null`
| 필드명 (key) | 의미 |
| --- | --- |
| `email` | 이메일 주소 |
| `address_office` | 직장 주소 |
| `mobile_carrier` | 휴대폰 통신사 |
| `phone_home` | 자택 전화번호 |
| `phone_office` | 직장 전화번호 |
| `calling_to` | 연락 받을 곳 |
| `initial_withdrawal_account` | 연계 출금 계좌번호 |
| `initial_withdrawal_amount` | 연계 출금 금액 |
| `ebanking_user_id` | 전자금융 사용자 ID |
| `ebanking_daily_limit` | 전자금융 1일 이체한도 |
| `ebanking_one_time_limit` | 전자금융 1회 이체한도 |
| `phone_daily_limit` | 폰뱅킹 1일 이체한도 |
| `phone_one_time_limit` | 폰뱅킹 1회 이체한도 |
| `e_passbook_note` | 전자통장 비고 |
| `card_english_name` | 카드에 인쇄될 영문 이름 |
| `beneficial_owner_name` | 실소유자 성명 |
| `beneficial_owner_id` | 실소유자 주민(여권)번호 |
| `purpose_other_text` | 거래목적(기타) 내용 |
| `source_other_text` | 자금원천(기타) 내용 |

---

## 2️⃣ 외화송금 (`scenario: "remittance"`)

### 필수 필드 (23개) — 모두 채워야 PDF 생성 가능
| 필드명 (key) | 의미 |
| --- | --- |
| `sender_name_eng` | 송금인 영문 성명 |
| `sender_id_no` | 송금인 주민(여권)번호 |
| `sender_account_no` | 송금인 계좌번호 |
| `sender_address` | 송금인 주소 |
| `sender_phone` | 송금인 전화번호 |
| `remittance_currency` | 송금 통화(예: USD) |
| `remittance_amount` | 송금 금액 |
| `purpose_of_payment` | 송금 목적 |
| `beneficiary_bank_name` | 수취은행 이름 |
| `beneficiary_bank_city` | 수취은행 도시 |
| `beneficiary_bank_country` | 수취은행 국가 |
| `beneficiary_bank_code` | 수취은행 SWIFT 코드 |
| `beneficiary_account_no` | 수취인 계좌번호 |
| `beneficiary_name` | 수취인 성명 |
| `relation_to_applicant` | 송금인과의 관계 |
| `beneficiary_address` | 수취인 주소 |
| `beneficiary_city` | 수취인 도시 |
| `beneficiary_country` | 수취인 국가 |
| `withdrawal_account_no` | 출금 계좌번호 |
| `withdrawal_account_name` | 출금 계좌 예금주명 |
| `app_year` | 신청 연도 |
| `app_month` | 신청 월 |
| `app_day` | 신청 일 |

### 선택 필드 (5개) — 있으면 채우고, 없으면 `null`
| 필드명 (key) | 의미 |
| --- | --- |
| `sender_name_kor` | 송금인 국문 성명 |
| `details_of_payment` | 적요(추가 메모) |
| `reimbursing_bank_swift` | 결제은행 SWIFT 코드 |
| `reimbursing_bank_name` | 결제은행 이름 |
| `beneficiary_bank_address` | 수취은행 주소 |

---

## 3️⃣ 트러블슈팅 (`scenario: "troubleshooting"`)

서식이 없는 상담 시나리오. `current_form_state` / `updated_form_state`는 빈 객체 `{}`.
백엔드는 RAG 챗봇으로 답변만 생성하고 `form_state`는 건드리지 않습니다.

---

## 📤 요청/응답 예시 (외화송금)

**요청 (프론트 → 백엔드)**
```json
{
  "scenario": "remittance",
  "user_message": "Tôi muốn gửi 1000 USD cho mẹ tôi",
  "current_form_state": {
    "sender_name_eng": "NGUYEN VAN AN",
    "remittance_amount": null,
    "beneficiary_name": null
  }
}
```

**응답 (백엔드 → 프론트)**
```json
{
  "bot_reply": "Số tiền 1000 USD đã được ghi nhận. Tên người nhận là gì ạ?",
  "updated_form_state": {
    "sender_name_eng": "NGUYEN VAN AN",
    "remittance_amount": "1000",
    "beneficiary_name": null
  },
  "form_complete": false
}
```

---

## 📄 PDF 생성 단계 (합의 필요)

필수 필드가 모두 채워지면 (`form_complete: true`), 서명·체크박스를 받아 PDF를 만듭니다.
**제안:** 별도 엔드포인트 `POST /api/render` 를 둡니다.

**요청 (프론트 → 백엔드)**
```json
{
  "scenario": "remittance",
  "form_state": { ...채워진 전체 필드... },
  "signatures": {
    "applicant_signature": "<base64 PNG>",
    "withdrawal_signature": "<base64 PNG>"
  },
  "checks": { "chk_purpose_salary": true }
}
```

**응답:** 완성된 PDF 파일 (`application/pdf`)

> 서명/체크박스 필드명 목록은 백엔드가 별도로 제공합니다 (서식마다 다름).
> 이 부분은 프론트와 추가 협의해서 확정합니다.

---

## ✅ 합의 체크리스트

- [ ] 필드명을 이 문서 기준으로 통일 (프론트/백엔드 양쪽)
- [ ] PDF 생성: `/api/render` 별도 엔드포인트 방식으로 OK?
- [ ] 서명 입력 UI: 프론트가 그린 서명을 base64 PNG로 전달하는 방식 OK?
- [ ] 체크박스(거래목적/자금원천): 프론트 UI에서 선택 → `checks`로 전달 OK?
