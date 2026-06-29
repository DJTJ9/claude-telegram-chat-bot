import os, requests
from datetime import date
from pathlib import Path

_env = Path(__file__).parent.parent / ".env"
if _env.exists():
    for _line in _env.read_text(encoding="utf-8").splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _, _v = _line.partition("=")
            os.environ.setdefault(_k.strip(), _v.strip())

NOCODB_API_URL = os.environ.get("NOCODB_API_URL", "http://localhost:8090")
NOCODB_API_TOKEN = os.environ.get("NOCODB_API_TOKEN", "")

TASKS_TABLE_ID = os.environ.get("NOCODB_TASKS_TABLE_ID", "")
SPORT_TABLE_ID = os.environ.get("NOCODB_SPORT_TABLE_ID", "")
BACKLOG_TABLE_ID = os.environ.get("NOCODB_BACKLOG_TABLE_ID", "")
IDEENSAMMLUNG_TABLE_ID = os.environ.get("NOCODB_IDEENSAMMLUNG_TABLE_ID", "")
ARCHIV_TABLE_ID = os.environ.get("NOCODB_ARCHIV_TABLE_ID", "")


def _headers() -> dict:
    return {"xc-token": NOCODB_API_TOKEN, "Content-Type": "application/json"}


def _url(table_id: str, row_id: int | None = None) -> str:
    base = f"{NOCODB_API_URL}/api/v2/tables/{table_id}/records"
    return f"{base}/{row_id}" if row_id is not None else base


def mark_done(row_id: int, table_id: str | None = None) -> bool:
    r = requests.patch(_url(table_id or TASKS_TABLE_ID, row_id),
                       headers=_headers(), json={"Status": "Done"})
    return r.status_code == 200


def reschedule(row_id: int, date_iso: str, table_id: str | None = None) -> bool:
    r = requests.patch(_url(table_id or TASKS_TABLE_ID, row_id),
                       headers=_headers(), json={"Datum": date_iso})
    return r.status_code == 200


def add_idea(text: str) -> bool:
    r = requests.post(_url(IDEENSAMMLUNG_TABLE_ID),
                      headers=_headers(), json={"Name": text[:2000]})
    return r.status_code == 200


def mark_sport_done(row_id: int) -> bool:
    r = requests.patch(_url(SPORT_TABLE_ID, row_id),
                       headers=_headers(), json={"Status": "Done"})
    return r.status_code == 200


def archive_backlog_item(row_id: int) -> bool:
    """Copy backlog row to Archiv table, then delete original."""
    r = requests.get(_url(BACKLOG_TABLE_ID, row_id), headers=_headers())
    if r.status_code != 200:
        return False
    row = r.json()

    archiv_payload = {
        "Name": row.get("Name", ""),
        "Archiviert am": date.today().isoformat(),
    }
    for field in ("Priorität", "Bereich", "Notiz", "Status"):
        if row.get(field):
            archiv_payload[field] = row[field]

    r2 = requests.post(_url(ARCHIV_TABLE_ID), headers=_headers(), json=archiv_payload)
    if r2.status_code != 200:
        return False

    r3 = requests.delete(_url(BACKLOG_TABLE_ID, row_id), headers=_headers())
    return r3.status_code == 200
