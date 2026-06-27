import os, requests

NOTION_API = "https://api.notion.com/v1"
IDEENSAMMLUNG_DB_ID = "38b4bba29c55814f836ed9a05d3ec9a5"


def _headers():
    return {
        "Authorization": f"Bearer {os.environ['NOTION_TOKEN']}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json",
    }


def mark_done(page_id: str) -> bool:
    r = requests.patch(
        f"{NOTION_API}/pages/{page_id}",
        headers=_headers(),
        json={"properties": {"Status": {"status": {"name": "Done"}}}},
    )
    return r.status_code == 200


def reschedule(page_id: str, date_iso: str) -> bool:
    r = requests.patch(
        f"{NOTION_API}/pages/{page_id}",
        headers=_headers(),
        json={"properties": {"Datum": {"date": {"start": date_iso}}}},
    )
    return r.status_code == 200


def add_idea(text: str) -> bool:
    r = requests.post(
        f"{NOTION_API}/pages",
        headers=_headers(),
        json={
            "parent": {"database_id": IDEENSAMMLUNG_DB_ID},
            "properties": {"Name": {"title": [{"text": {"content": text[:2000]}}]}},
        },
    )
    return r.status_code == 200


def mark_sport_done(page_id: str) -> bool:
    r = requests.patch(
        f"{NOTION_API}/pages/{page_id}",
        headers=_headers(),
        json={"properties": {"Status": {"status": {"name": "Done"}}}},
    )
    return r.status_code == 200
