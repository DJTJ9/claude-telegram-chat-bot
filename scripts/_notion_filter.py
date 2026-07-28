import json
import sys

DB1 = "98507f42-8d36-493b-ae25-564cbf205ba9"  # Tagesorganizer
DB2 = "fad94811-608c-41ba-b728-d1338e21a01d"  # Backlog

def norm(u):
    return u.replace("-", "").lower()

DB1n = norm(DB1)
DB2n = norm(DB2)

def get_title(props, key="Name"):
    p = props.get(key)
    if not p:
        return None
    if p.get("type") == "title":
        return "".join(t.get("plain_text", "") for t in p.get("title", []))
    return None

def get_select(props, key):
    p = props.get(key)
    if not p or p.get("type") != "select":
        return None
    sel = p.get("select")
    return sel.get("name") if sel else None

def get_status(props, key):
    p = props.get(key)
    if not p:
        return None
    if p.get("type") == "status":
        st = p.get("status")
        return st.get("name") if st else None
    if p.get("type") == "select":
        st = p.get("select")
        return st.get("name") if st else None
    return None

def get_date(props, key):
    p = props.get(key)
    if not p or p.get("type") != "date":
        return None, None
    d = p.get("date")
    if not d:
        return None, None
    return d.get("start"), d.get("end")

def get_rich_text(props, key):
    p = props.get(key)
    if not p or p.get("type") != "rich_text":
        return ""
    return "".join(t.get("plain_text", "") for t in p.get("rich_text", []))

def process_file(path):
    with open(path) as f:
        data = json.load(f)
    results = data.get("results", [])
    matches1 = []
    matches2 = []
    for r in results:
        if r.get("object") != "page":
            continue
        parent = r.get("parent", {})
        if parent.get("type") != "database_id":
            continue
        dbid = norm(parent.get("database_id", ""))
        props = r.get("properties", {})
        status = get_status(props, "Status")
        if dbid == DB1n and status == "Done":
            datum_start, datum_end = get_date(props, "Datum")
            matches1.append({
                "id": r.get("id"),
                "name": get_title(props),
                "status": status,
                "prioritaet": get_select(props, "Priorität"),
                "datum_start": datum_start,
                "datum_end": datum_end,
                "bereich": get_select(props, "Bereich"),
                "notiz": get_rich_text(props, "Notiz"),
            })
        elif dbid == DB2n and status == "Erledigt":
            matches2.append({
                "id": r.get("id"),
                "name": get_title(props),
                "status": status,
                "prioritaet": get_select(props, "Priorität"),
                "bereich": get_select(props, "Bereich"),
                "notiz": get_rich_text(props, "Notiz"),
            })
    next_cursor = data.get("next_cursor")
    has_more = data.get("has_more")
    return matches1, matches2, next_cursor, has_more, len(results)

ACCUM_PATH = "/tmp/notion_accum_v2.json"

if __name__ == "__main__":
    path = sys.argv[1]
    m1, m2, cursor, has_more, n = process_file(path)

    try:
        with open(ACCUM_PATH) as f:
            accum = json.load(f)
    except FileNotFoundError:
        accum = {"tagesorganizer_done": [], "backlog_erledigt": [], "scanned": 0}

    existing1 = {t["id"] for t in accum["tagesorganizer_done"]}
    existing2 = {t["id"] for t in accum["backlog_erledigt"]}
    for m in m1:
        if m["id"] not in existing1:
            accum["tagesorganizer_done"].append(m)
            existing1.add(m["id"])
    for m in m2:
        if m["id"] not in existing2:
            accum["backlog_erledigt"].append(m)
            existing2.add(m["id"])

    accum["scanned"] = accum.get("scanned", 0) + n

    with open(ACCUM_PATH, "w") as f:
        json.dump(accum, f, ensure_ascii=False, indent=2)

    print(json.dumps({
        "count_results": n,
        "new_matches_db1": len(m1),
        "new_matches_db2": len(m2),
        "accum_total_db1": len(accum["tagesorganizer_done"]),
        "accum_total_db2": len(accum["backlog_erledigt"]),
        "total_scanned": accum["scanned"],
        "next_cursor": cursor,
        "has_more": has_more,
    }, ensure_ascii=False, indent=2))
