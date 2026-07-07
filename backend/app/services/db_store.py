"""
서식 완성 정보 저장 (SQLite)
- 데모용: 서식이 완성되면 필수 정보(이름·생년월일·전화번호 등)를 DB에 저장.
- 파일 하나(applications.db)로 동작. 설정 불필요.
- "저장됨"을 데모에서 보여주기 위한 용도.

저장 항목 (필수 정보만):
  계좌개설: 이름, 생년월일, 전화번호, 직업, 상품명
  외화송금: 송금인명, 송금액, 통화, 수취인명
"""
from __future__ import annotations

import os
import sqlite3
from datetime import datetime
from pathlib import Path

# DB 저장 위치:
#  1순위: 환경변수 BANKY_DB_PATH (코랩에서 /content/applications.db 등으로 지정)
#  2순위: 코드 폴더 밖의 안정적 위치 (zip 다시 풀어도 안 날아가게)
# 코드 폴더(app/data) 안에 두면 zip 재배포 시 덮어써져서 데이터가 사라짐.
def _default_db_path() -> str:
    env = os.environ.get("BANKY_DB_PATH")
    if env:
        return env
    # 코랩이면 /content, 아니면 홈 디렉터리 (코드 폴더 밖)
    if os.path.isdir("/content"):
        return "/content/applications.db"
    return str(Path.home() / "banky_applications.db")


DB_PATH = _default_db_path()


def _connect(db_path: str):
    """DB 연결. 폴더 없으면 생성."""
    parent = Path(db_path).parent
    parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(db_path)


def init_db(db_path: str = None):
    """테이블 생성 (없으면)."""
    db_path = db_path or DB_PATH
    conn = _connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scenario TEXT,
            name TEXT,
            birth_date TEXT,
            phone TEXT,
            extra TEXT,
            created_at TEXT
        )
    """)
    conn.commit()
    conn.close()


def save_application(scenario: str, form_state: dict,
                     db_path: str = None) -> dict:
    """완성된 서식의 필수 정보를 저장.
    반환: {saved: True, id: N, summary: {...}} 또는 {saved: False, error: ...}
    """
    db_path = db_path or DB_PATH
    try:
        init_db(db_path)

        # 시나리오별 필수 정보 추출 (프론트 필드명 기준)
        if scenario == "account_opening":
            name = form_state.get("customer_name")
            birth = form_state.get("birth_date")
            phone = form_state.get("mobile_phone")
            extra = {
                "occupation": form_state.get("occupation"),
                "product_name": form_state.get("product_name"),
            }
        elif scenario == "remittance":
            name = form_state.get("sender_name_eng")
            birth = None
            phone = form_state.get("sender_phone")
            extra = {
                "amount": form_state.get("remittance_amount"),
                "currency": form_state.get("remittance_currency"),
                "beneficiary": form_state.get("beneficiary_name"),
            }
        else:
            name = birth = phone = None
            extra = {}

        import json
        conn = _connect(db_path)
        cur = conn.execute(
            "INSERT INTO applications (scenario, name, birth_date, phone, extra, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (scenario, name, birth, phone, json.dumps(extra, ensure_ascii=False),
             datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        )
        conn.commit()
        new_id = cur.lastrowid
        conn.close()

        return {
            "saved": True,
            "id": new_id,
            "db_path": db_path,
            "summary": {"scenario": scenario, "name": name,
                        "birth_date": birth, "phone": phone, **extra},
        }
    except Exception as e:
        # 저장 실패 시 원인을 명확히 반환 (디버깅용)
        return {"saved": False, "error": str(e), "db_path": db_path}


def list_applications(db_path: str = None, limit: int = 50) -> list[dict]:
    """저장된 신청 목록 조회 (데모에서 '쌓인 것' 보여주기용)."""
    db_path = db_path or DB_PATH
    init_db(db_path)
    import json
    conn = _connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM applications ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    result = []
    for r in rows:
        d = dict(r)
        try:
            d["extra"] = json.loads(d["extra"]) if d["extra"] else {}
        except Exception:
            d["extra"] = {}
        result.append(d)
    return result


def count_applications(db_path: str = None) -> int:
    db_path = db_path or DB_PATH
    init_db(db_path)
    conn = _connect(db_path)
    n = conn.execute("SELECT COUNT(*) FROM applications").fetchone()[0]
    conn.close()
    return n
