"""
필드 메타데이터
- 좌표 JSON에는 label과 좌표만 있고 '의미'가 없다.
- 여기서 각 label에 사람이 읽는 의미(한국어)와 입력 타입을 부여한다.
- 이 의미는 다국어 재질문 생성 시 LLM에 전달되어, 사용자 언어로 자연스럽게 번역된다.
- 좌표 JSON에 없는 label이 들어오면 label 자체를 의미로 사용(폴백).
"""

# label -> 한국어 의미. 가이드 명세서 기반.
FIELD_MEANINGS = {
    # === 외화송금 ===
    "req_sender_name_eng": "송금인 영문 성명",
    "opt_sender_name_kor": "송금인 국문 성명",
    "req_sender_id_no": "송금인 주민(여권)번호",
    "req_sender_account_no": "송금인 계좌번호",
    "req_sender_address": "송금인 주소",
    "req_sender_phone": "송금인 전화번호",
    "req_remittance_currency": "송금 통화(예: USD)",
    "req_remittance_amount": "송금 금액",
    "req_purpose_of_payment": "송금 목적",
    "opt_details_of_payment": "적요(추가 메모)",
    "opt_reimbursing_bank_swift": "결제은행 SWIFT 코드",
    "opt_reimbursing_bank_name": "결제은행 이름",
    "req_beneficiary_bank_name": "수취은행 이름",
    "opt_beneficiary_bank_address": "수취은행 주소",
    "req_beneficiary_bank_city": "수취은행 도시",
    "req_beneficiary_bank_country": "수취은행 국가",
    "req_beneficiary_bank_code": "수취은행 SWIFT 코드",
    "req_beneficiary_account_no": "수취인 계좌번호",
    "req_beneficiary_name": "수취인 성명",
    "req_relation_to_applicant": "송금인과의 관계",
    "req_beneficiary_address": "수취인 주소",
    "req_beneficiary_city": "수취인 도시",
    "req_beneficiary_country": "수취인 국가",
    "req_withdrawal_account_no": "출금 계좌번호",
    "req_withdrawal_account_name": "출금 계좌 예금주명",
    "req_withdrawal_signature": "출금 동의 서명",
    "req_application_year": "신청 연도",
    "req_application_month": "신청 월",
    "req_application_day": "신청 일",
    "req_applicant_signature": "신청인 서명",

    # === 계좌개설 page 0 ===
    "req_customer_name": "고객 성명",
    "req_customer_birth_date": "생년월일",
    "req_customer_mobile_phone": "휴대폰 번호",
    "opt_customer_email": "이메일 주소",
    "req_customer_address_home": "자택 주소",
    "opt_customer_address_office": "직장 주소",
    "opt_customer_mobile_phone_category": "휴대폰 통신사",
    "opt_customer_phone_home": "자택 전화번호",
    "opt_customer_phone_office": "직장 전화번호",
    "req_customer_mailing_to": "우편물 수령처 (자택/직장/안받음 중 하나 선택)",
    "opt_customer_calling_to": "연락 받을 곳",
    "req_customer_occupation": "직업",
    "req_product_name": "가입할 상품명",
    "req_enrollment_amount": "초기 가입(입금) 금액",
    "opt_initial_withdrawal_account": "연계 출금 계좌번호",
    "opt_initial_withdrawal_amount": "연계 출금 금액",
    "req_confirm_info_inquiry_sig": "금융정보 조회 동의 서명",
    "req_confirm_group_share_sig": "그룹사 정보제공 동의 서명",
    "req_confirm_product_explain_sig": "상품설명 청취 확인 서명",
    "req_applicant_signature_p0": "신청인 서명",
    "req_app_year_p0": "신청 연도",
    "req_app_month_p0": "신청 월",
    "req_app_day_p0": "신청 일",

    # === 계좌개설 page 1 ===
    "opt_ebanking_user_id": "전자금융 사용자 ID",
    "opt_ebanking_daily_limit": "전자금융 1일 이체한도",
    "opt_ebanking_one_time_limit": "전자금융 1회 이체한도",
    "opt_phone_daily_limit": "폰뱅킹 1일 이체한도",
    "opt_phone_one_time_limit": "폰뱅킹 1회 이체한도",
    "opt_ebanking_signature": "전자금융 신청 서명",
    "opt_e_passbook_note": "전자통장 비고",
    "opt_card_english_name": "카드에 인쇄될 영문 이름",
    "opt_card_signature": "체크카드 발급 동의 서명",
    "opt_beneficial_owner_name": "실소유자 성명",
    "opt_beneficial_owner_id": "실소유자 주민(여권)번호",
    "opt_purpose_other_text": "거래목적(기타) 내용",
    "opt_source_other_text": "자금원천(기타) 내용",
    "opt_chk_purpose_salary": "거래목적: 급여",
    "opt_chk_source_labor": "자금원천: 근로소득",
    "opt_renewal_applicant_signature": "자동재예치 동의 서명",
    "req_depositor_final_signature": "최종 예금주 서명",
}


def get_meaning(label: str) -> str:
    """label의 한국어 의미를 반환. 없으면 label을 사람이 읽기 쉽게 변환."""
    if label in FIELD_MEANINGS:
        return FIELD_MEANINGS[label]
    # 폴백: req_/opt_ 접두사 제거하고 밑줄을 공백으로
    cleaned = label.replace("req_", "").replace("opt_", "").replace("_", " ")
    return cleaned


# label -> 영어 의미. 추출 단계에서 소형 모델(3B)의 혼동을 줄이기 위해 사용.
# (한국어 의미는 재질문 등 사용자 대면에, 영어 의미는 LLM 추출 지시에 사용)
FIELD_MEANINGS_EN = {
    # 외화송금
    "req_sender_name_eng": "Sender's name in English/Latin letters",
    "opt_sender_name_kor": "Sender's name in Korean script only",
    "req_sender_id_no": "Sender's ID or passport number",
    "req_sender_account_no": "Sender's account number",
    "req_sender_address": "Sender's address",
    "req_sender_phone": "Sender's phone number",
    "req_remittance_currency": "Remittance currency (e.g. USD)",
    "req_remittance_amount": "Remittance amount",
    "req_purpose_of_payment": "Purpose of payment",
    "opt_details_of_payment": "Payment details/memo",
    "opt_reimbursing_bank_swift": "Reimbursing bank SWIFT code",
    "opt_reimbursing_bank_name": "Reimbursing bank name",
    "req_beneficiary_bank_name": "Beneficiary bank name",
    "opt_beneficiary_bank_address": "Beneficiary bank address",
    "req_beneficiary_bank_city": "Beneficiary bank city",
    "req_beneficiary_bank_country": "Beneficiary bank country",
    "req_beneficiary_bank_code": "Beneficiary bank SWIFT code",
    "req_beneficiary_account_no": "Beneficiary account number",
    "req_beneficiary_name": "Beneficiary's name",
    "req_relation_to_applicant": "Relationship to the sender",
    "req_beneficiary_address": "Beneficiary's address",
    "req_beneficiary_city": "Beneficiary's city",
    "req_beneficiary_country": "Beneficiary's country",
    "req_withdrawal_account_no": "Withdrawal account number",
    "req_withdrawal_account_name": "Withdrawal account holder name",
    "req_application_year": "Application year",
    "req_application_month": "Application month",
    "req_application_day": "Application day",
    # 계좌개설 p0
    "req_customer_name": "Customer's full name",
    "req_customer_birth_date": "Date of birth",
    "req_customer_mobile_phone": "Mobile phone number",
    "opt_customer_email": "Email address",
    "req_customer_address_home": "Home address",
    "opt_customer_address_office": "Office address",
    "opt_customer_mobile_phone_category": "Mobile carrier",
    "opt_customer_phone_home": "Home phone number",
    "opt_customer_phone_office": "Office phone number",
    "req_customer_mailing_to": "Where to receive mail: choose one of Home, Office, or Don't Receive (NOT a full address)",
    "opt_customer_calling_to": "Contact destination",
    "req_customer_occupation": "Occupation",
    "req_product_name": "Product name to open",
    "req_enrollment_amount": "Initial deposit amount",
    "opt_initial_withdrawal_account": "Linked withdrawal account number",
    "opt_initial_withdrawal_amount": "Linked withdrawal amount",
    "req_app_year_p0": "Application year",
    "req_app_month_p0": "Application month",
    "req_app_day_p0": "Application day",
    # 계좌개설 p1
    "opt_ebanking_user_id": "E-banking user ID",
    "opt_ebanking_daily_limit": "E-banking daily transfer limit",
    "opt_ebanking_one_time_limit": "E-banking per-transaction limit",
    "opt_phone_daily_limit": "Phone banking daily limit",
    "opt_phone_one_time_limit": "Phone banking per-transaction limit",
    "opt_e_passbook_note": "E-passbook note",
    "opt_card_english_name": "English name printed on card",
    "opt_beneficial_owner_name": "Beneficial owner name",
    "opt_beneficial_owner_id": "Beneficial owner ID number",
    "opt_purpose_other_text": "Transaction purpose (other)",
    "opt_source_other_text": "Source of funds (other)",
}


def get_meaning_en(label: str) -> str:
    """label의 영어 의미. 없으면 한국어 의미로 폴백."""
    if label in FIELD_MEANINGS_EN:
        return FIELD_MEANINGS_EN[label]
    return get_meaning(label)
