import os, random, requests
from datetime import date, timedelta
from pathlib import Path
from core.state import load_registry

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
HABITS_TABLE_ID = os.environ.get("NOCODB_HABITS_TABLE_ID", "")
IDEENSAMMLUNG_TABLE_ID = os.environ.get("NOCODB_IDEENSAMMLUNG_TABLE_ID", "")
ARCHIV_TABLE_ID = os.environ.get("NOCODB_ARCHIV_TABLE_ID", "")
FOCUS_TABLE_ID = os.environ.get("NOCODB_FOCUS_TABLE_ID", "")


def _headers() -> dict:
    return {"xc-token": NOCODB_API_TOKEN, "Content-Type": "application/json"}


def _url(table_id: str, row_id: int | None = None) -> str:
    base = f"{NOCODB_API_URL}/api/v2/tables/{table_id}/records"
    return f"{base}/{row_id}" if row_id is not None else base


def mark_done(row_id: int, table_id: str | None = None) -> bool:
    r = requests.patch(_url(table_id or TASKS_TABLE_ID),
                       headers=_headers(), json=[{"Id": row_id, "Status": "Done"}])
    return r.status_code == 200


def reschedule(row_id: int, date_iso: str, table_id: str | None = None) -> bool:
    r = requests.patch(_url(table_id or TASKS_TABLE_ID),
                       headers=_headers(), json=[{"Id": row_id, "Datum": date_iso}])
    return r.status_code == 200


def add_idea(text: str) -> bool:
    r = requests.post(_url(IDEENSAMMLUNG_TABLE_ID),
                      headers=_headers(), json={"Name": text[:2000]})
    return r.status_code == 200


def mark_sport_done(row_id: int) -> bool:
    r = requests.patch(_url(SPORT_TABLE_ID),
                       headers=_headers(), json=[{"Id": row_id, "Status": "Done"}])
    return r.status_code == 200


def fetch_habits() -> list:
    r = requests.get(_url(HABITS_TABLE_ID), headers=_headers(),
                     params={"limit": 200})
    rows = r.json().get("list", []) if r.status_code == 200 else []
    return [{"id": str(row["Id"]), "name": row.get("Name", ""),
             "kategorie": row.get("Kategorie") or "", "zyklus": row.get("Zyklus") or "",
             "status": row.get("Status", "Not Started")}
            for row in rows]


def mark_habit_done(row_id: int) -> bool:
    r = requests.patch(_url(HABITS_TABLE_ID),
                       headers=_headers(), json=[{"Id": row_id, "Status": "Done"}])
    return r.status_code == 200


_ZYKLUS_WOCHENTAGE = {
    0: "montags", 1: "dienstags", 2: "mittwochs", 3: "donnerstags",
    4: "freitags", 5: "samstags", 6: "sonntags",
}


def _habit_due_today(zyklus: str, weekday: int) -> bool:
    z = (zyklus or "").strip().lower()
    if not z or z == "täglich":
        return True
    if z == "wochentags":
        return weekday < 5
    if z == "wochenends":
        return weekday >= 5
    if z == _ZYKLUS_WOCHENTAGE.get(weekday):
        return True
    if z in _ZYKLUS_WOCHENTAGE.values():
        return False
    # "alle N Tage" / Tag-im-Monat-Listen brauchen ein Anker-Datum, das die
    # Habits-Tabelle nicht hat -> als immer fällig behandeln.
    return True


def fetch_habits_due(date_iso: str) -> list:
    weekday = date.fromisoformat(date_iso).weekday()
    return [h for h in fetch_habits()
            if h["status"] != "Done" and _habit_due_today(h["zyklus"], weekday)]


_PRIO_ORDER: dict = {"Hoch": 0, "Mittel": 1, "Niedrig": 2}


def fetch_tasks_today(date_iso: str) -> dict:
    today_r = requests.get(_url(TASKS_TABLE_ID), headers=_headers(),
                           params={"where": f"(Datum,like,{date_iso}%)~and(Status,neq,Done)",
                                   "limit": 200})
    null_r = requests.get(_url(TASKS_TABLE_ID), headers=_headers(),
                          params={"where": "(Datum,is,null)~and(Status,neq,Done)",
                                  "limit": 200})
    today_rows = today_r.json().get("list", []) if today_r.status_code == 200 else []
    null_rows = null_r.json().get("list", []) if null_r.status_code == 200 else []

    appointments, tasks = [], []
    for row in today_rows:
        datum = row.get("Datum") or ""
        entry = {"name": row.get("Title", ""), "prio": row.get("Priorität") or "Niedrig",
                 "projekt": row.get("Bereich"), "id": str(row["Id"])}
        if "T" in datum:
            entry["time"] = datum.split("T")[1][:5]
            appointments.append(entry)
        else:
            tasks.append(entry)
    for row in null_rows:
        tasks.append({"name": row.get("Title", ""), "prio": row.get("Priorität") or "Niedrig",
                      "projekt": row.get("Bereich"), "id": str(row["Id"])})

    appointments.sort(key=lambda a: a.get("time", ""))
    tasks.sort(key=lambda t: _PRIO_ORDER.get(t["prio"], 1))
    return {"date": date_iso, "appointments": appointments, "tasks": tasks,
            "habits": fetch_habits_due(date_iso), "proj_tasks": []}


def fetch_abend_data(date_iso: str) -> dict:
    r = requests.get(_url(TASKS_TABLE_ID), headers=_headers(),
                     params={"where": f"(Datum,like,{date_iso}%)", "limit": 200})
    rows = r.json().get("list", []) if r.status_code == 200 else []
    done = [{"name": row.get("Title", ""), "projekt": row.get("Bereich")}
            for row in rows if row.get("Status") == "Done"]
    open_tasks = [{"name": row.get("Title", ""), "prio": row.get("Priorität") or "Niedrig",
                   "projekt": row.get("Bereich"), "id": str(row["Id"])}
                  for row in rows if row.get("Status") != "Done"]
    open_tasks.sort(key=lambda t: _PRIO_ORDER.get(t["prio"], 1))

    projekt_bilanz = []
    focus_slug = get_focus_project()
    if focus_slug:
        proj = next((p for p in load_registry() if p["slug"] == focus_slug), None)
        if proj and proj.get("nocodb_table_id"):
            bilanz = fetch_project_bilanz(proj["nocodb_table_id"])
            projekt_bilanz = [{"name": proj.get("name", focus_slug), **bilanz}]

    return {"date": date_iso, "done": done, "open": open_tasks,
            "missed_habits": fetch_habits_due(date_iso), "projekt_bilanz": projekt_bilanz}


def fetch_sport_challenges() -> list:
    r = requests.get(_url(SPORT_TABLE_ID), headers=_headers(),
                     params={"where": "(Status,eq,Not started)", "limit": 200})
    rows = r.json().get("list", []) if r.status_code == 200 else []
    by_cat: dict = {}
    for row in rows:
        kat = row.get("Kategorie") or "Sport"
        by_cat.setdefault(kat, []).append(
            {"name": row.get("Title", ""), "id": str(row["Id"]), "kategorie": kat})
    return [random.choice(challenges) for challenges in by_cat.values() if challenges]


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


def create_task(title: str, datum: str, prio: str = "Niedrig") -> bool:
    r = requests.post(_url(TASKS_TABLE_ID), headers=_headers(),
                      json={"Title": title, "Datum": datum, "Priorität": prio,
                            "Status": "Not started"})
    return r.status_code in (200, 201)


def promote_backlog_item(row_id: int, datum: str) -> bool:
    r = requests.get(_url(BACKLOG_TABLE_ID, row_id), headers=_headers())
    if r.status_code != 200:
        return False
    row = r.json()
    name = row.get("Name", "")
    prio = row.get("Priorität") or "Niedrig"
    if not create_task(name, datum, prio):
        return False
    return archive_backlog_item(row_id)


def fetch_backlog_items() -> list:
    r = requests.get(_url(BACKLOG_TABLE_ID), headers=_headers(),
                     params={"where": "(Status,eq,Offen)", "limit": 200})
    rows = r.json().get("list", []) if r.status_code == 200 else []
    items = [{"id": str(row["Id"]), "name": row.get("Name", ""),
              "prio": row.get("Priorität") or "Niedrig"}
             for row in rows]
    items.sort(key=lambda x: _PRIO_ORDER.get(x["prio"], 1))
    return items


def create_backlog_item(name: str, prio: str = "Niedrig", bereich: str = "Privat") -> bool:
    r = requests.post(_url(BACKLOG_TABLE_ID), headers=_headers(),
                      json={"Name": name, "Priorität": prio, "Bereich": bereich,
                            "Status": "Offen"})
    return r.status_code in (200, 201)


def fetch_tasks_month(year: int, month: int) -> dict:
    prefix = f"{year:04d}-{month:02d}"
    r = requests.get(_url(TASKS_TABLE_ID), headers=_headers(),
                     params={"where": f"(Datum,like,{prefix}%)", "limit": 500})
    rows = r.json().get("list", []) if r.status_code == 200 else []
    termine, tasks_done, tasks_total = [], 0, 0
    for row in rows:
        datum = row.get("Datum") or ""
        if "T" in datum:
            termine.append({"name": row.get("Title", ""), "datum": datum,
                            "time": datum.split("T")[1][:5],
                            "prio": row.get("Priorität") or "Niedrig",
                            "id": str(row["Id"])})
        else:
            tasks_total += 1
            if row.get("Status") == "Done":
                tasks_done += 1
    termine.sort(key=lambda a: a["datum"])
    return {"termine": termine, "tasks_done": tasks_done, "tasks_total": tasks_total}


def fetch_project_features(table_id: str, limit: int = 5) -> list:
    if not table_id:
        return []
    r = requests.get(_url(table_id), headers=_headers(), params={"limit": 200})
    rows = r.json().get("list", []) if r.status_code == 200 else []
    features = [row.get("Name", "") for row in rows if row.get("Status") != "done"]
    return features[:limit]


def fetch_project_bilanz(table_id: str) -> dict:
    if not table_id:
        return {"done": 0, "open": 0}
    r = requests.get(_url(table_id), headers=_headers(), params={"limit": 200})
    rows = r.json().get("list", []) if r.status_code == 200 else []
    done = sum(1 for row in rows if row.get("Status") == "done")
    open_count = sum(1 for row in rows if row.get("Status") != "done")
    return {"done": done, "open": open_count}


def instantiate_recurring_tasks(date_iso: str) -> list:
    weekday = date.fromisoformat(date_iso).weekday()
    r = requests.get(_url(TASKS_TABLE_ID), headers=_headers(), params={"limit": 200})
    rows = r.json().get("list", []) if r.status_code == 200 else []
    templates = [row for row in rows if row.get("Zyklus")]
    existing_today = {row.get("Title", "") for row in rows
                       if (row.get("Datum") or "").startswith(date_iso) and row.get("Status") != "Done"}
    created = []
    for tpl in templates:
        name = tpl.get("Title", "")
        if name in existing_today:
            continue
        if not _habit_due_today(tpl.get("Zyklus", ""), weekday):
            continue
        prio = tpl.get("Priorität") or "Niedrig"
        if create_task(name, date_iso, prio):
            created.append(name)
    return created


def set_focus_project(slug: str) -> bool:
    r = requests.get(_url(FOCUS_TABLE_ID), headers=_headers(), params={"limit": 1})
    rows = r.json().get("list", []) if r.status_code == 200 else []
    payload = {"Slug": slug, "Updated": date.today().isoformat()}
    if rows:
        r2 = requests.patch(_url(FOCUS_TABLE_ID), headers=_headers(),
                            json=[{**payload, "Id": rows[0]["Id"]}])
        return r2.status_code == 200
    r2 = requests.post(_url(FOCUS_TABLE_ID), headers=_headers(), json=payload)
    return r2.status_code in (200, 201)


def get_focus_project() -> str | None:
    r = requests.get(_url(FOCUS_TABLE_ID), headers=_headers(), params={"limit": 1})
    rows = r.json().get("list", []) if r.status_code == 200 else []
    return rows[0].get("Slug") if rows else None


def fetch_woche_data(date_iso: str) -> dict:
    start = date.fromisoformat(date_iso)
    end = start + timedelta(days=6)
    end_iso = end.isoformat()

    r = requests.get(_url(TASKS_TABLE_ID), headers=_headers(),
                     params={"where": "(Status,neq,Done)", "limit": 500})
    rows = r.json().get("list", []) if r.status_code == 200 else []

    appointments, tasks = [], []
    for row in rows:
        datum = row.get("Datum") or ""
        d_only = datum[:10]
        if not d_only or not (date_iso <= d_only <= end_iso):
            continue
        entry = {"name": row.get("Title", ""), "prio": row.get("Priorität") or "Niedrig",
                  "datum": d_only, "id": str(row["Id"])}
        if "T" in datum:
            entry["time"] = datum.split("T")[1][:5]
            appointments.append(entry)
        else:
            tasks.append(entry)
    appointments.sort(key=lambda a: (a["datum"], a.get("time", "")))
    tasks.sort(key=lambda t: _PRIO_ORDER.get(t["prio"], 1))

    habits = fetch_habits()
    seen_habit_ids: set = set()
    due_habits = []
    for offset in range(7):
        weekday = (start + timedelta(days=offset)).weekday()
        for h in habits:
            if h["id"] in seen_habit_ids or h["status"] == "Done":
                continue
            if _habit_due_today(h["zyklus"], weekday):
                due_habits.append(h)
                seen_habit_ids.add(h["id"])

    backlog = [b for b in fetch_backlog_items() if b["prio"] == "Hoch"]
    termin_days = sorted({a["datum"] for a in appointments})

    return {"start": date_iso, "end": end_iso,
            "appointments": appointments, "tasks": tasks,
            "habits": due_habits, "backlog": backlog,
            "termin_days": termin_days}
