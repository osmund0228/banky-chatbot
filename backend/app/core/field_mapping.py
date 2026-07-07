"""
프론트엔드 ↔ 백엔드 필드명 매핑
- 프론트는 짧고 읽기 쉬운 이름(customer_name)을 사용
- 백엔드는 PDF 좌표용 긴 이름(req_customer_name)을 사용
- 이 매핑으로 양쪽을 변환한다.

대상: '텍스트형' 필드만 (대화로 주고받는 것).
서명(signature)·체크박스(checkbox)는 form_state에 포함하지 않고 별도 처리.

규칙:
- 프론트명 -> 백엔드명(좌표 label) 1:1 매핑
- 필수 여부는 백엔드 label의 req_/opt_ 접두사로 이미 결정됨
"""

# ===== 계좌개설 (account_opening) =====
# 프론트 짧은 이름 : 백엔드 좌표 label
ACCOUNT_OPENING_MAP = {
    # 필수
    "customer_name":          "req_customer_name",
    "name":                   "req_customer_name",   # OCR 응답 키 별칭
    "birth_date":             "req_customer_birth_date",
    "mobile_phone":           "req_customer_mobile_phone",
    "address_home":           "req_customer_address_home",
    "mailing_to":             "req_customer_mailing_to",
    "occupation":             "req_customer_occupation",
    "product_name":           "req_product_name",
    "enrollment_amount":      "req_enrollment_amount",
    "app_year":               "req_app_year_p0",
    "app_month":              "req_app_month_p0",
    "app_day":                "req_app_day_p0",
    # 선택
    "email":                  "opt_customer_email",
    "address_office":         "opt_customer_address_office",
    "mobile_carrier":         "opt_customer_mobile_phone_category",
    "phone_home":             "opt_customer_phone_home",
    "phone_office":           "opt_customer_phone_office",
    "calling_to":             "opt_customer_calling_to",
    "initial_withdrawal_account": "opt_initial_withdrawal_account",
    "initial_withdrawal_amount":  "opt_initial_withdrawal_amount",
    "ebanking_user_id":       "opt_ebanking_user_id",
    "ebanking_daily_limit":   "opt_ebanking_daily_limit",
    "ebanking_one_time_limit": "opt_ebanking_one_time_limit",
    "phone_daily_limit":      "opt_phone_daily_limit",
    "phone_one_time_limit":   "opt_phone_one_time_limit",
    "e_passbook_note":        "opt_e_passbook_note",
    "card_english_name":      "opt_card_english_name",
    "beneficial_owner_name":  "opt_beneficial_owner_name",
    "beneficial_owner_id":    "opt_beneficial_owner_id",
    "purpose_other_text":     "opt_purpose_other_text",
    "source_other_text":      "opt_source_other_text",
}

# ===== 외화송금 (remittance) =====
REMITTANCE_MAP = {
    # 필수
    "sender_name_eng":        "req_sender_name_eng",
    "sender_name":            "req_sender_name_eng",    # 별칭
    "sender_id_no":           "req_sender_id_no",
    "sender_id":              "req_sender_id_no",       # 별칭
    "sender_account_no":      "req_sender_account_no",
    "sender_account":         "req_sender_account_no",  # 별칭
    "sender_address":         "req_sender_address",
    "sender_phone":           "req_sender_phone",
    "remittance_currency":    "req_remittance_currency",
    "currency":               "req_remittance_currency", # 별칭
    "remittance_amount":      "req_remittance_amount",
    "amount":                 "req_remittance_amount",   # 별칭
    "purpose_of_payment":     "req_purpose_of_payment",
    "purpose":                "req_purpose_of_payment",  # 별칭
    "beneficiary_bank_name":  "req_beneficiary_bank_name",
    "beneficiary_bank_city":  "req_beneficiary_bank_city",
    "beneficiary_bank_country": "req_beneficiary_bank_country",
    "beneficiary_bank_code":  "req_beneficiary_bank_code",
    "beneficiary_account_no": "req_beneficiary_account_no",
    "beneficiary_account":    "req_beneficiary_account_no", # 별칭
    "beneficiary_name":       "req_beneficiary_name",
    "relation_to_applicant":  "req_relation_to_applicant",
    "relation":               "req_relation_to_applicant",  # 별칭
    "beneficiary_address":    "req_beneficiary_address",
    "beneficiary_city":       "req_beneficiary_city",
    "beneficiary_country":    "req_beneficiary_country",
    "withdrawal_account_no":  "req_withdrawal_account_no",
    "withdrawal_account":     "req_withdrawal_account_no",  # 별칭
    "withdrawal_account_name": "req_withdrawal_account_name",
    "withdrawal_name":        "req_withdrawal_account_name", # 별칭
    "app_year":               "req_application_year",
    "app_month":              "req_application_month",
    "app_day":                "req_application_day",
    # 수수료 체크박스 (백엔드 키 그대로)
    "req_fee_separate":       "req_fee_separate",
    "req_fee_deducted":       "req_fee_deducted",
    "req_fee_our":            "req_fee_our",
    "req_fee_sha":            "req_fee_sha",
    "req_fee_ben":            "req_fee_ben",
    "fee_separate":           "req_fee_separate",  # 별칭
    "fee_deducted":           "req_fee_deducted",
    "fee_our":                "req_fee_our",
    "fee_sha":                "req_fee_sha",
    "fee_ben":                "req_fee_ben",
    # 선택
    "sender_name_kor":        "opt_sender_name_kor",
    "details_of_payment":     "opt_details_of_payment",
    "reimbursing_bank_swift": "opt_reimbursing_bank_swift",
    "reimbursing_bank_name":  "opt_reimbursing_bank_name",
    "beneficiary_bank_address": "opt_beneficiary_bank_address",
}


# --- 그룹 체크박스 / 약관 동의 (백엔드 키 그대로 사용) ---
ACCOUNT_OPENING_MAP["opt_group_phone_type_smart"] = "opt_group_phone_type_smart"
ACCOUNT_OPENING_MAP["opt_group_phone_type_non_smart"] = "opt_group_phone_type_non_smart"
ACCOUNT_OPENING_MAP["opt_group_phone_type_budget"] = "opt_group_phone_type_budget"
ACCOUNT_OPENING_MAP["opt_group_mobile_carrier_skt"] = "opt_group_mobile_carrier_skt"
ACCOUNT_OPENING_MAP["opt_group_mobile_carrier_lgu"] = "opt_group_mobile_carrier_lgu"
ACCOUNT_OPENING_MAP["opt_group_mobile_carrier_kt"] = "opt_group_mobile_carrier_kt"
ACCOUNT_OPENING_MAP["opt_group_mobile_carrier_other"] = "opt_group_mobile_carrier_other"
ACCOUNT_OPENING_MAP["opt_group_mailing_to_home"] = "opt_group_mailing_to_home"
ACCOUNT_OPENING_MAP["opt_group_mailing_to_office"] = "opt_group_mailing_to_office"
ACCOUNT_OPENING_MAP["opt_group_mailing_to_none"] = "opt_group_mailing_to_none"
ACCOUNT_OPENING_MAP["opt_group_calling_to_home"] = "opt_group_calling_to_home"
ACCOUNT_OPENING_MAP["opt_group_calling_to_office"] = "opt_group_calling_to_office"
ACCOUNT_OPENING_MAP["opt_group_calling_to_mobile"] = "opt_group_calling_to_mobile"
ACCOUNT_OPENING_MAP["opt_group_calling_to_none"] = "opt_group_calling_to_none"
ACCOUNT_OPENING_MAP["opt_group_occ_salaried"] = "opt_group_occ_salaried"
ACCOUNT_OPENING_MAP["opt_group_occ_professional"] = "opt_group_occ_professional"
ACCOUNT_OPENING_MAP["opt_group_occ_business"] = "opt_group_occ_business"
ACCOUNT_OPENING_MAP["opt_group_occ_public"] = "opt_group_occ_public"
ACCOUNT_OPENING_MAP["opt_group_occ_pensioner"] = "opt_group_occ_pensioner"
ACCOUNT_OPENING_MAP["opt_group_occ_homemaker"] = "opt_group_occ_homemaker"
ACCOUNT_OPENING_MAP["opt_group_occ_student"] = "opt_group_occ_student"
ACCOUNT_OPENING_MAP["opt_group_occ_other"] = "opt_group_occ_other"
ACCOUNT_OPENING_MAP["req_agree_product_guide_1"] = "req_agree_product_guide_1"
ACCOUNT_OPENING_MAP["req_agree_terms_1"] = "req_agree_terms_1"
ACCOUNT_OPENING_MAP["req_agree_contract_1"] = "req_agree_contract_1"
ACCOUNT_OPENING_MAP["req_agree_product_guide_2"] = "req_agree_product_guide_2"
ACCOUNT_OPENING_MAP["req_agree_terms_2"] = "req_agree_terms_2"
ACCOUNT_OPENING_MAP["req_agree_contract_2"] = "req_agree_contract_2"
ACCOUNT_OPENING_MAP["req_agree_product_guide_3"] = "req_agree_product_guide_3"
ACCOUNT_OPENING_MAP["req_agree_terms_3"] = "req_agree_terms_3"
ACCOUNT_OPENING_MAP["req_agree_contract_3"] = "req_agree_contract_3"
ACCOUNT_OPENING_MAP["req_agree_financial_info_inquiry"] = "req_agree_financial_info_inquiry"
ACCOUNT_OPENING_MAP["req_agree_set_off"] = "req_agree_set_off"
ACCOUNT_OPENING_MAP["req_agree_customer_info_policy"] = "req_agree_customer_info_policy"
ACCOUNT_OPENING_MAP["opt_group_housing_area_85_less"] = "opt_group_housing_area_85_less"
ACCOUNT_OPENING_MAP["opt_group_housing_area_102_less"] = "opt_group_housing_area_102_less"
ACCOUNT_OPENING_MAP["opt_group_housing_area_135_less"] = "opt_group_housing_area_135_less"
ACCOUNT_OPENING_MAP["opt_group_housing_area_over_135"] = "opt_group_housing_area_over_135"
ACCOUNT_OPENING_MAP["opt_group_ebanking_cat_new"] = "opt_group_ebanking_cat_new"
ACCOUNT_OPENING_MAP["opt_group_ebanking_cat_add"] = "opt_group_ebanking_cat_add"
ACCOUNT_OPENING_MAP["opt_group_ebanking_svc_internet"] = "opt_group_ebanking_svc_internet"
ACCOUNT_OPENING_MAP["opt_group_ebanking_svc_phone"] = "opt_group_ebanking_svc_phone"
ACCOUNT_OPENING_MAP["opt_group_ebanking_svc_inquiry"] = "opt_group_ebanking_svc_inquiry"
ACCOUNT_OPENING_MAP["opt_group_ebanking_svc_quick"] = "opt_group_ebanking_svc_quick"
ACCOUNT_OPENING_MAP["opt_group_ebanking_sec_card"] = "opt_group_ebanking_sec_card"
ACCOUNT_OPENING_MAP["opt_group_ebanking_sec_otp"] = "opt_group_ebanking_sec_otp"
ACCOUNT_OPENING_MAP["opt_group_ebanking_sec_braille"] = "opt_group_ebanking_sec_braille"
ACCOUNT_OPENING_MAP["opt_group_ebanking_consent_yes"] = "opt_group_ebanking_consent_yes"
ACCOUNT_OPENING_MAP["opt_group_ebanking_consent_no"] = "opt_group_ebanking_consent_no"
ACCOUNT_OPENING_MAP["opt_group_ic_card_cash"] = "opt_group_ic_card_cash"
ACCOUNT_OPENING_MAP["opt_group_ic_card_bankbook"] = "opt_group_ic_card_bankbook"
ACCOUNT_OPENING_MAP["opt_group_ic_card_k_cash"] = "opt_group_ic_card_k_cash"
ACCOUNT_OPENING_MAP["opt_group_ic_card_add_withdrawal"] = "opt_group_ic_card_add_withdrawal"
ACCOUNT_OPENING_MAP["opt_group_ic_card_non_passbook"] = "opt_group_ic_card_non_passbook"
ACCOUNT_OPENING_MAP["opt_group_ic_card_atm"] = "opt_group_ic_card_atm"
ACCOUNT_OPENING_MAP["req_group_purpose_salary"] = "req_group_purpose_salary"
ACCOUNT_OPENING_MAP["req_group_purpose_savings"] = "req_group_purpose_savings"
ACCOUNT_OPENING_MAP["req_group_purpose_insurance"] = "req_group_purpose_insurance"
ACCOUNT_OPENING_MAP["req_group_purpose_publicfee"] = "req_group_purpose_publicfee"
ACCOUNT_OPENING_MAP["req_group_purpose_creditcard"] = "req_group_purpose_creditcard"
ACCOUNT_OPENING_MAP["req_group_purpose_loan"] = "req_group_purpose_loan"
ACCOUNT_OPENING_MAP["req_group_purpose_business"] = "req_group_purpose_business"
ACCOUNT_OPENING_MAP["req_group_purpose_other"] = "req_group_purpose_other"
ACCOUNT_OPENING_MAP["req_group_source_labor"] = "req_group_source_labor"
ACCOUNT_OPENING_MAP["req_group_source_retirement"] = "req_group_source_retirement"
ACCOUNT_OPENING_MAP["req_group_source_business"] = "req_group_source_business"
ACCOUNT_OPENING_MAP["req_group_source_realestate_lease"] = "req_group_source_realestate_lease"
ACCOUNT_OPENING_MAP["req_group_source_financial"] = "req_group_source_financial"
ACCOUNT_OPENING_MAP["req_group_source_inheritance"] = "req_group_source_inheritance"
ACCOUNT_OPENING_MAP["req_group_source_temporary"] = "req_group_source_temporary"
ACCOUNT_OPENING_MAP["req_group_source_other"] = "req_group_source_other"
ACCOUNT_OPENING_MAP["req_group_overseas_yes"] = "req_group_overseas_yes"
ACCOUNT_OPENING_MAP["req_group_overseas_no"] = "req_group_overseas_no"
ACCOUNT_OPENING_MAP["req_agree_depositor_protection"] = "req_agree_depositor_protection"
ACCOUNT_OPENING_MAP["req_agree_ban_borrowed_name"] = "req_agree_ban_borrowed_name"
ACCOUNT_OPENING_MAP["req_agree_prohibition_assignment"] = "req_agree_prohibition_assignment"
ACCOUNT_OPENING_MAP["req_ebanking_legal_consent"] = "req_ebanking_legal_consent"
ACCOUNT_OPENING_MAP["req_consent_agreed"] = "req_consent_agreed"

# 시나리오(scenario) -> 매핑 테이블
SCENARIO_MAPS = {
    "account_opening": ACCOUNT_OPENING_MAP,
    "remittance":      REMITTANCE_MAP,
    # troubleshooting은 서식 없음 (빈 매핑)
    "troubleshooting": {},
}

# 시나리오(프론트) -> form_id(백엔드 슬롯스키마)
SCENARIO_TO_FORM_ID = {
    "account_opening": "account_opening",
    "remittance":      "foreign_remittance",
}

# 역매핑 (백엔드 label -> 프론트명)
SCENARIO_MAPS_REVERSE = {
    scenario: {v: k for k, v in m.items()}
    for scenario, m in SCENARIO_MAPS.items()
}


def front_to_backend(scenario: str, front_state: dict) -> dict:
    """프론트 form_state({짧은이름: 값}) -> 백엔드 슬롯({긴label: 값})."""
    m = SCENARIO_MAPS.get(scenario, {})
    result = {}
    for fk, val in front_state.items():
        if val in (None, "", "null"):
            continue
        backend_key = m.get(fk)
        if backend_key:
            result[backend_key] = val
    return result


def backend_to_front(scenario: str, backend_slots: dict) -> dict:
    """백엔드 슬롯({긴label: 값}) -> 프론트 form_state({짧은이름: 값})."""
    rm = SCENARIO_MAPS_REVERSE.get(scenario, {})
    result = {}
    for bk, val in backend_slots.items():
        front_key = rm.get(bk)
        if front_key:
            result[front_key] = val
    return result


def all_front_fields(scenario: str) -> list[str]:
    """해당 시나리오의 모든 프론트 필드명 목록."""
    return list(SCENARIO_MAPS.get(scenario, {}).keys())
