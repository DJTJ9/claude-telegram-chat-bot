import os, datetime, requests

NOTION_API = "https://api.notion.com/v1"
IDEENSAMMLUNG_DB_ID = "38b4bba29c55814f836ed9a05d3ec9a5"
ARCHIV_DB_ID = "38b4bba29c558102b9aecb790594aff6"


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


def archive_backlog_item(page_id: str) -> bool:
    """Copy backlog page to Archiv DB, then archive original. Direct REST, no Claude."""
    r = requests.get(f"{NOTION_API}/pages/{page_id}", headers=_headers())
    if r.status_code != 200:
        return False
    props = r.json().get("properties", {})

    def _title(p):
        items = p.get("title", [])
        return items[0]["text"]["content"] if items else ""

    def _select(p):
        s = p.get("select")
        return s["name"] if s else None

    def _text(p):
        items = p.get("rich_text", [])
        return items[0]["text"]["content"] if items else None

    name      = _title(props.get("Name", {}))
    priorität = _select(props.get("Priorität", {}))
    bereich   = _select(props.get("Bereich", {}))
    notiz     = _text(props.get("Notiz", {}))
    today     = datetime.date.today().isoformat()

    archiv_props: dict = {
        "Name":          {"title": [{"text": {"content": name}}]},
        "Archiviert am": {"date": {"start": today}},
    }
    if priorität:
        archiv_props["Priorität"] = {"select": {"name": priorität}}
    if bereich:
        archiv_props["Bereich"] = {"select": {"name": bereich}}
    if notiz:
        archiv_props["Notiz"] = {"rich_text": [{"text": {"content": notiz}}]}

    r2 = requests.post(
        f"{NOTION_API}/pages",
        headers=_headers(),
        json={"parent": {"database_id": ARCHIV_DB_ID}, "properties": archiv_props},
    )
    if r2.status_code != 200:
        return False

    r3 = requests.patch(
        f"{NOTION_API}/pages/{page_id}",
        headers=_headers(),
        json={"archived": True},
    )
    return r3.status_code == 200
