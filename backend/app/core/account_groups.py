"""
계좌개설 체크박스 그룹 + 약관 동의 정의
- 필수 선택지 그룹(purpose/source/overseas): 번호로 질문, 고른 것만 체크
- 직업/우편물/통신사/연락처 그룹: 번호 선택지
- 약관 동의(req_agree_*): 한 번에 일괄 동의

각 그룹: 질문(다국어) + 선택지 + 선택지별 체크할 키
"""

# ===== 상품명 선택지 (체크박스 아님 - 고른 값을 텍스트로 채움) =====
# 외국인이 한국 상품명을 모르므로 유형을 선택지로 제공
PRODUCT_CHOICES = {
    "ask": {"Korean": "가입하실 상품을 선택해 주세요",
            "English": "Please choose a product to open",
            "Chinese": "请选择要开通的产品",
            "Japanese": "開設する商品を選択してください",
            "Vietnamese": "Vui lòng chọn sản phẩm",
            "Indonesian": "Silakan pilih produk",
                "French": "Veuillez choisir un produit", "Thai": "กรุณาเลือกผลิตภัณฑ์"},
    "options": ["자유 입출금 통장", "정기예금", "정기적금", "자유적금", "외화예금"],
    "options_en": ["Free Checking Account", "Time Deposit", "Fixed Installment Savings",
                   "Free Installment Savings", "Foreign Currency Deposit"],
    # 고른 인덱스 -> 서식(form_state)에 채울 상품명. 언어별로 저장.
    # (PDF 렌더링 시에는 별도 번역 단계에서 처리되므로, 여기선 사용자 언어로 표시)
    "values": ["자유 입출금 통장", "정기예금", "정기적금", "자유적금", "외화예금"],
    "values_by_lang": {
        "Korean":     ["자유 입출금 통장", "정기예금", "정기적금", "자유적금", "외화예금"],
        "English":    ["Free Checking Account", "Time Deposit", "Fixed Installment Savings",
                       "Free Installment Savings", "Foreign Currency Deposit"],
        "Vietnamese": ["Tài khoản thanh toán tự do", "Tiền gửi có kỳ hạn", "Tiết kiệm định kỳ cố định",
                       "Tiết kiệm định kỳ tự do", "Tiền gửi ngoại tệ"],
        "Chinese":    ["自由存取账户", "定期存款", "定期定额储蓄", "自由储蓄", "外币存款"],
        "Japanese":   ["自由入出金口座", "定期預金", "定期積立", "自由積立", "外貨預金"],
        "Indonesian": ["Rekening Bebas", "Deposito Berjangka", "Tabungan Berjangka Tetap",
                       "Tabungan Berjangka Bebas", "Deposito Mata Uang Asing"],
        "French":     ["Compte courant libre", "Dépôt à terme", "Épargne à versements fixes",
                       "Épargne à versements libres", "Dépôt en devises"],
        "Thai":       ["บัญชีเงินฝากออมทรัพย์", "เงินฝากประจำ", "เงินฝากประจำแบบกำหนด",
                       "เงินฝากประจำแบบอิสระ", "เงินฝากสกุลเงินต่างประเทศ"],
    },
    "target_key": "req_product_name",
}


def product_question(language: str) -> str:
    """상품 선택 질문 (선택지는 choices 버튼으로 따로 보냄)."""
    pc = PRODUCT_CHOICES
    return pc["ask"].get(language, pc["ask"]["English"])


# ===== 필수 선택지 그룹 (반드시 1개) =====
REQUIRED_GROUPS = {
    "purpose": {
        "order": 1,
        "ask": {"Korean": "거래 목적을 선택해 주세요",
                "English": "Purpose of transaction",
                "Chinese": "交易目的", "Japanese": "取引目的",
                "Vietnamese": "Mục đích giao dịch", "Indonesian": "Tujuan transaksi",
                "French": "Objet de la transaction", "Thai": "วัตถุประสงค์ของธุรกรรม"},
        "options": ["급여/생활비", "저축/투자", "보험료", "공과금", "카드대금", "대출상환", "사업거래", "기타"],
        "options_en": ["Salary/Living", "Savings/Invest", "Insurance", "Public fee",
                       "Card payment", "Loan repay", "Business", "Other"],
        "keys": ["req_group_purpose_salary", "req_group_purpose_savings",
                 "req_group_purpose_insurance", "req_group_purpose_publicfee",
                 "req_group_purpose_creditcard", "req_group_purpose_loan",
                 "req_group_purpose_business", "req_group_purpose_other"],
    },
    "source": {
        "order": 2,
        "ask": {"Korean": "자금 출처를 선택해 주세요",
                "English": "Source of funds",
                "Chinese": "资金来源", "Japanese": "資金源",
                "Vietnamese": "Nguồn tiền", "Indonesian": "Sumber dana",
                "French": "Source des fonds", "Thai": "แหล่งที่มาของเงินทุน"},
        "options": ["근로소득", "퇴직소득", "사업소득", "부동산임대", "금융소득", "상속/증여", "일시재산양도", "기타"],
        "options_en": ["Labor", "Retirement", "Business", "Real estate lease",
                       "Financial", "Inheritance", "Temp asset", "Other"],
        "keys": ["req_group_source_labor", "req_group_source_retirement",
                 "req_group_source_business", "req_group_source_realestate_lease",
                 "req_group_source_financial", "req_group_source_inheritance",
                 "req_group_source_temporary", "req_group_source_other"],
    },
    "overseas": {
        "order": 3,
        "ask": {"Korean": "해외 납세 의무가 있으십니까? (미국 시민/영주권/타국 납세)",
                "English": "Are you a foreign taxpayer? (US citizen/resident/other)",
                "Chinese": "您是否有海外纳税义务?", "Japanese": "海外納税義務がありますか?",
                "Vietnamese": "Bạn có nghĩa vụ thuế nước ngoài không?",
                "Indonesian": "Apakah Anda wajib pajak asing?",
                "French": "Êtes-vous assujetti à l'impôt étranger ?", "Thai": "คุณมีภาระภาษีต่างประเทศหรือไม่"},
        "options": ["예 (Yes)", "아니오 (No)"],
        "options_en": ["Yes", "No"],
        "keys": ["req_group_overseas_yes", "req_group_overseas_no"],
    },
}

# ===== 텍스트→그룹 체크박스로 대체된 선택 그룹 =====
# (직업/우편물/통신사/연락처: 텍스트 슬롯 대신 그룹 체크박스 사용)
OPTIONAL_GROUPS = {
    "occupation": {
        "ask": {"Korean": "직업을 선택해 주세요", "English": "Occupation",
                "Chinese": "职业", "Japanese": "職業",
                "Vietnamese": "Nghề nghiệp", "Indonesian": "Pekerjaan",
                "French": "Profession", "Thai": "อาชีพ"},
        "options": ["급여소득자", "전문직", "사업자", "공무원", "연금생활자", "주부", "학생", "기타"],
        "options_en": ["Salaried", "Professional", "Business owner", "Public servant",
                       "Pensioner", "Homemaker", "Student", "Other"],
        "keys": ["opt_group_occ_salaried", "opt_group_occ_professional",
                 "opt_group_occ_business", "opt_group_occ_public",
                 "opt_group_occ_pensioner", "opt_group_occ_homemaker",
                 "opt_group_occ_student", "opt_group_occ_other"],
        # 직업 판단용: 주부(5)/학생(6)/연금(4) 인덱스는 직장 없음
        "no_workplace_idx": [4, 5, 6],
    },
    "mailing": {
        "ask": {"Korean": "우편물 수령처", "English": "Mail delivery",
                "Chinese": "邮寄目的地", "Japanese": "郵送先",
                "Vietnamese": "Nơi nhận thư", "Indonesian": "Tujuan surat",
                "French": "Destination du courrier", "Thai": "สถานที่รับไปรษณีย์"},
        "options": ["자택", "직장", "안받음"],
        "options_en": ["Home", "Office", "Don't Receive"],
        "keys": ["opt_group_mailing_to_home", "opt_group_mailing_to_office",
                 "opt_group_mailing_to_none"],
    },
    "carrier": {
        "ask": {"Korean": "휴대폰 통신사", "English": "Mobile carrier",
                "Chinese": "手机运营商", "Japanese": "携帯キャリア",
                "Vietnamese": "Nhà mạng", "Indonesian": "Operator seluler",
                "French": "Opérateur mobile", "Thai": "ผู้ให้บริการมือถือ"},
        "options": ["SKT", "LG U+", "KT", "기타"],
        "options_en": ["SKT", "LGU+", "KT", "Other"],
        "keys": ["opt_group_mobile_carrier_skt", "opt_group_mobile_carrier_lgu",
                 "opt_group_mobile_carrier_kt", "opt_group_mobile_carrier_other"],
    },
    "calling": {
        "ask": {"Korean": "전화 연락처(전화 수신처)를 선택해 주세요", "English": "Calling to",
                "Chinese": "电话联系处", "Japanese": "電話連絡先",
                "Vietnamese": "Nơi nhận cuộc gọi", "Indonesian": "Tujuan panggilan",
                "French": "Destination des appels", "Thai": "สถานที่รับสาย"},
        "options": ["자택", "직장", "휴대폰", "안받음"],
        "options_en": ["Home", "Office", "Mobile", "Don't Receive"],
        "keys": ["opt_group_calling_to_home", "opt_group_calling_to_office",
                 "opt_group_calling_to_mobile", "opt_group_calling_to_none"],
    },
}

# ===== 약관 동의 (전부 일괄 동의) =====
# 화면에 보여줄 약관 요약 (실제 서식 기반)
CONSENT_DISPLAY = {
    "Korean": [
        "상품설명서·약관·계약서에 대한 설명을 듣고 충분히 이해했으며, 해당 서류를 수령했습니다 (가입 상품).",
        "계약금액·한도·비과세 종합저축 및 재형저축·주택청약저축 상품의 중복 확인을 위해 타 금융기관에 본인의 금융정보 조회를 요청·동의합니다.",
        "본인의 대출·지급보증·신용카드 채무가 변제기에 도래하거나 기한이익을 상실하는 경우, 이 예금의 상계에 이의를 제기하지 않습니다.",
        "금융지주회사법 제48조의2에 따라 하나금융그룹 계열사 간 고객정보가 제공·이용될 수 있다는 설명을 들었으며, 고객정보 관리방침을 수령했음을 확인합니다.",
        "예금자보호법에 따른 보호 여부 및 보호 한도에 대해 설명을 듣고 이해했습니다 (주택청약저축은 예금자보호 대상이 아니며 국민주택기금으로 관리됨).",
        "금융실명법 제3조에 따라 불법재산 은닉·자금세탁·테러자금조달 등을 목적으로 한 차명거래가 금지되며, 위반 시 형사처벌(5년 이하 징역 또는 5천만원 이하 벌금)될 수 있다는 설명을 듣고 이해했습니다.",
        "통장·카드의 양도·대여는 전자금융거래법에 따라 손해배상 책임 또는 처벌 대상이 되며 거래 제한을 받을 수 있다는 설명을 들었습니다 (필수).",
        "본인이 미국 납세의무자 또는 그 외 국가의 납세의무자(해외거주자)에 해당하는지 여부 확인에 응답했습니다.",
    ],
    "English": [
        "I have heard and fully understood the explanation of the product guide, terms & conditions, and contract, and I have received those documents (for the enrolled product).",
        "I request and agree to an inquiry of my financial information at other banks to confirm the contract amount, limit, and any duplication of tax-free/asset-building/housing-subscription savings.",
        "I shall raise no objection to a set-off of this deposit if my loans, guarantees, or credit card debt owed to the bank reach the repayment deadline or lose the benefit of time.",
        "I have been explained that customer information may be shared among Hana Financial Group and its subsidiaries under Article 48-2 of the Financial Holding Companies Act, and I confirm receipt of the customer information policy.",
        "I have been explained and understand the deposit insurance coverage and its limit under the Depositor Protection Act (housing-subscription savings is not protected but managed as the National Housing Fund).",
        "I understand that transactions under a borrowed name to conceal illegal property, launder money, or finance terrorism are prohibited under Article 3 of the Real Name Financial Transactions Act, punishable by up to 5 years' imprisonment or a KRW 50 million fine.",
        "I have been explained that assigning or lending a passbook/card may lead to liability for damages or punishment under the Electronic Banking Transactions Act and restrictions on transactions (Required).",
        "I have responded to the confirmation of whether I am a U.S. taxpayer or a taxpayer/resident of another country (overseas resident).",
    ],
    "Vietnamese": [
        "Tôi đã nghe và hiểu rõ phần giải thích về bản hướng dẫn sản phẩm, điều khoản và hợp đồng, đồng thời đã nhận được các tài liệu đó (sản phẩm đăng ký).",
        "Tôi yêu cầu và đồng ý cho tra cứu thông tin tài chính của tôi tại các ngân hàng khác để xác nhận số tiền hợp đồng, hạn mức và trùng lặp các sản phẩm tiết kiệm miễn thuế/tích lũy tài sản/đăng ký nhà ở.",
        "Tôi sẽ không phản đối việc bù trừ khoản tiền gửi này nếu khoản vay, bảo lãnh hoặc nợ thẻ tín dụng của tôi với ngân hàng đến hạn trả nợ hoặc mất quyền lợi về thời hạn.",
        "Tôi đã được giải thích rằng thông tin khách hàng có thể được chia sẻ trong Tập đoàn Tài chính Hana theo Điều 48-2 Luật Công ty Tài chính, và xác nhận đã nhận chính sách thông tin khách hàng.",
        "Tôi đã được giải thích và hiểu về việc bảo vệ tiền gửi và hạn mức bảo vệ theo Luật Bảo vệ Người gửi tiền (tiết kiệm đăng ký nhà ở không được bảo vệ mà do nhà nước quản lý).",
        "Tôi hiểu rằng giao dịch dưới tên người khác nhằm che giấu tài sản bất hợp pháp, rửa tiền hoặc tài trợ khủng bố bị cấm theo Điều 3 Luật Giao dịch Tài chính Thực danh, có thể bị phạt tù đến 5 năm hoặc phạt tiền đến 50 triệu won.",
        "Tôi đã được giải thích rằng việc chuyển nhượng hoặc cho mượn sổ tiết kiệm/thẻ có thể dẫn đến trách nhiệm bồi thường hoặc bị xử phạt theo Luật Giao dịch Ngân hàng Điện tử và bị hạn chế giao dịch (Bắt buộc).",
        "Tôi đã trả lời xác nhận về việc tôi có phải là người nộp thuế Hoa Kỳ hay người nộp thuế/cư dân của quốc gia khác hay không (cư dân nước ngoài).",
    ],
    "Chinese": [
        "我已听取并充分理解关于产品说明书、条款和合同的说明，并已收到上述文件（所申请产品）。",
        "我请求并同意在其他金融机构查询本人金融信息，以确认合同金额、限额及免税/财产形成/住房认购储蓄产品的重复情况。",
        "如本人对贵行的贷款、担保或信用卡债务到达偿还期限或丧失期限利益，我对本存款的抵销不提出异议。",
        "我已获知根据《金融控股公司法》第48条之2，客户信息可在哈那金融集团及其子公司间共享，并确认已收到客户信息管理方针。",
        "我已获得关于《存款人保护法》下存款保险保障与否及保障限额的说明并理解（住房认购储蓄不受保护，由国家作为国民住房基金管理）。",
        "我理解根据《金融实名法》第3条，以隐匿非法财产、洗钱或资助恐怖主义为目的的借名交易被禁止，违者可处5年以下有期徒刑或5千万韩元以下罚款。",
        "我已获知转让或出借存折/卡可能依据《电子金融交易法》承担损害赔偿责任或受处罚，并可能受到交易限制（必填）。",
        "我已就本人是否为美国纳税义务人或其他国家纳税义务人（海外居住者）作出回应。",
    ],
    "Japanese": [
        "商品説明書・約款・契約書に関する説明を聞いて十分に理解し、当該書類を受領しました（加入商品）。",
        "契約金額・限度・非課税総合貯蓄・財形貯蓄・住宅請約貯蓄商品の重複確認のため、他の金融機関での本人の金融情報照会を要請・同意します。",
        "本人の融資・支払保証・クレジットカード債務が弁済期に達するか期限の利益を喪失する場合、この預金の相殺に異議を申し立てません。",
        "金融持株会社法第48条の2により、ハナ金融グループ系列会社間で顧客情報が提供・利用される旨の説明を受け、顧客情報管理方針を受領したことを確認します。",
        "預金者保護法による保護の有無および保護限度について説明を受け理解しました（住宅請約貯蓄は預金者保護の対象外で国民住宅基金として管理）。",
        "金融実名法第3条により、不法財産の隠匿・資金洗浄・テロ資金調達などを目的とした借名取引は禁止され、違反時は5年以下の懲役または5千万ウォン以下の罰金が科されうる旨の説明を受け理解しました。",
        "通帳・カードの譲渡・貸与は電子金融取引法により損害賠償責任または処罰の対象となり、取引制限を受けうる旨の説明を受けました（必須）。",
        "本人が米国納税義務者またはその他の国の納税義務者（海外居住者）に該当するか否かの確認に回答しました。",
    ],
    "Indonesian": [
        "Saya telah mendengar dan memahami sepenuhnya penjelasan tentang panduan produk, syarat & ketentuan, dan kontrak, serta telah menerima dokumen tersebut (produk yang didaftarkan).",
        "Saya meminta dan menyetujui pemeriksaan informasi keuangan saya di bank lain untuk mengonfirmasi jumlah kontrak, batas, dan duplikasi tabungan bebas pajak/pembentukan aset/langganan perumahan.",
        "Saya tidak akan keberatan atas penyelesaian simpanan ini jika pinjaman, jaminan, atau utang kartu kredit saya kepada bank mencapai batas waktu pembayaran atau kehilangan manfaat waktu.",
        "Saya telah dijelaskan bahwa informasi nasabah dapat dibagikan di Grup Keuangan Hana berdasarkan Pasal 48-2 UU Perusahaan Induk Keuangan, dan saya mengonfirmasi penerimaan kebijakan informasi nasabah.",
        "Saya telah dijelaskan dan memahami perlindungan asuransi simpanan dan batasnya berdasarkan UU Perlindungan Penyimpan (tabungan langganan perumahan tidak dilindungi tetapi dikelola sebagai Dana Perumahan Nasional).",
        "Saya memahami bahwa transaksi dengan nama pinjaman untuk menyembunyikan properti ilegal, pencucian uang, atau pendanaan terorisme dilarang berdasarkan Pasal 3 UU Transaksi Keuangan Nama Asli, dapat dihukum hingga 5 tahun penjara atau denda 50 juta won.",
        "Saya telah dijelaskan bahwa pengalihan atau peminjaman buku tabungan/kartu dapat menyebabkan tanggung jawab ganti rugi atau hukuman berdasarkan UU Transaksi Perbankan Elektronik dan pembatasan transaksi (Wajib).",
        "Saya telah menanggapi konfirmasi apakah saya wajib pajak AS atau wajib pajak/penduduk negara lain (penduduk luar negeri).",
    ],
    # ⚠️ 검수 필요(LEGAL REVIEW REQUIRED): 아래 French/Thai 약관은 기계 번역 초안입니다.
    # 은행 법무/현지어 검수 후 확정하세요. 미검수 시 "French"/"Thai" 키를 지워
    # 영어 약관(consent_display 폴백)으로 표시되게 할 수 있습니다.
    "French": [
        "J'ai entendu et pleinement compris les explications relatives au descriptif du produit, aux conditions générales et au contrat, et j'ai reçu ces documents (produit souscrit).",
        "Je demande et consens à la vérification de mes informations financières auprès d'autres établissements afin de confirmer le montant du contrat, les plafonds et les doublons de produits d'épargne défiscalisée/formation de patrimoine/souscription-logement.",
        "Je ne m'opposerai pas à la compensation de ce dépôt si mon prêt, ma garantie ou ma dette de carte de crédit envers la banque arrive à échéance ou perd le bénéfice du terme.",
        "Il m'a été expliqué que les informations clients peuvent être partagées au sein du Groupe financier Hana en vertu de l'article 48-2 de la loi sur les holdings financières, et je confirme avoir reçu la politique de gestion des informations clients.",
        "Il m'a été expliqué, et je comprends, la protection de l'assurance des dépôts et son plafond en vertu de la loi sur la protection des déposants (l'épargne souscription-logement n'est pas protégée mais gérée comme Fonds national du logement).",
        "Je comprends que les transactions sous un nom d'emprunt visant à dissimuler des biens illégaux, à blanchir de l'argent ou à financer le terrorisme sont interdites en vertu de l'article 3 de la loi sur les transactions financières sous nom réel, passibles de jusqu'à 5 ans d'emprisonnement ou 50 millions de wons d'amende.",
        "Il m'a été expliqué que la cession ou le prêt d'un livret/d'une carte peut entraîner une responsabilité en dommages-intérêts ou des sanctions en vertu de la loi sur les transactions financières électroniques, ainsi que des restrictions de transaction (Obligatoire).",
        "J'ai répondu à la confirmation de savoir si je suis un contribuable américain ou un contribuable/résident d'un autre pays (résident étranger).",
    ],
    "Thai": [
        "ข้าพเจ้าได้รับฟังและเข้าใจคำอธิบายเกี่ยวกับคู่มือผลิตภัณฑ์ ข้อกำหนดและสัญญาอย่างครบถ้วน และได้รับเอกสารดังกล่าวแล้ว (ผลิตภัณฑ์ที่สมัคร)",
        "ข้าพเจ้าขอและยินยอมให้ตรวจสอบข้อมูลทางการเงินของข้าพเจ้าที่สถาบันการเงินอื่น เพื่อยืนยันจำนวนเงินตามสัญญา วงเงิน และการซ้ำซ้อนของผลิตภัณฑ์ออมทรัพย์ปลอดภาษี/สร้างทรัพย์สิน/ออมเพื่อที่อยู่อาศัย",
        "ข้าพเจ้าจะไม่คัดค้านการหักกลบเงินฝากนี้ หากสินเชื่อ การค้ำประกัน หรือหนี้บัตรเครดิตของข้าพเจ้าต่อธนาคารถึงกำหนดชำระหรือสูญเสียสิทธิประโยชน์ด้านระยะเวลา",
        "ข้าพเจ้าได้รับคำอธิบายว่าข้อมูลลูกค้าอาจถูกแบ่งปันภายในกลุ่มการเงินฮานาตามมาตรา 48-2 ของกฎหมายบริษัทโฮลดิ้งทางการเงิน และยืนยันว่าได้รับนโยบายการจัดการข้อมูลลูกค้าแล้ว",
        "ข้าพเจ้าได้รับคำอธิบายและเข้าใจเกี่ยวกับการคุ้มครองประกันเงินฝากและวงเงินคุ้มครองตามกฎหมายคุ้มครองผู้ฝากเงิน (เงินออมเพื่อที่อยู่อาศัยไม่ได้รับการคุ้มครองแต่บริหารเป็นกองทุนที่อยู่อาศัยแห่งชาติ)",
        "ข้าพเจ้าเข้าใจว่าการทำธุรกรรมโดยใช้ชื่อผู้อื่นเพื่อปกปิดทรัพย์สินผิดกฎหมาย ฟอกเงิน หรือสนับสนุนการก่อการร้าย เป็นสิ่งต้องห้ามตามมาตรา 3 ของกฎหมายธุรกรรมการเงินชื่อจริง มีโทษจำคุกไม่เกิน 5 ปีหรือปรับไม่เกิน 50 ล้านวอน",
        "ข้าพเจ้าได้รับคำอธิบายว่าการโอนหรือให้ยืมสมุดบัญชี/บัตร อาจมีความรับผิดชดใช้ค่าเสียหายหรือถูกลงโทษตามกฎหมายธุรกรรมการเงินอิเล็กทรอนิกส์ และอาจถูกจำกัดการทำธุรกรรม (จำเป็น)",
        "ข้าพเจ้าได้ตอบยืนยันว่าข้าพเจ้าเป็นผู้เสียภาษีสหรัฐฯ หรือผู้เสียภาษี/ผู้พำนักของประเทศอื่นหรือไม่ (ผู้พำนักต่างประเทศ)",
    ],
}

# 동의 시 체크할 약관 키 (상품 1개 가입 -> ①번 줄 약관 + 공통 약관만)
# _2, _3 (②③번 상품 줄 약관)은 제외: 상품 2,3개째 가입할 때만 필요
ALL_AGREE_KEYS = [
    "req_agree_product_guide_1", "req_agree_terms_1", "req_agree_contract_1",
    "req_agree_financial_info_inquiry", "req_agree_set_off",
    "req_agree_customer_info_policy", "req_agree_depositor_protection",
    "req_agree_ban_borrowed_name", "req_agree_prohibition_assignment",
    "req_ebanking_legal_consent",
]


def consent_display(language: str) -> list[str]:
    return CONSENT_DISPLAY.get(language, CONSENT_DISPLAY["English"])


def group_question(group_def: dict, language: str) -> str:
    """그룹 선택 질문 (선택지는 choices 버튼으로 따로 보냄)."""
    return group_def["ask"].get(language, group_def["ask"]["English"])
