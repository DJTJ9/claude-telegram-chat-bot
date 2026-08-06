"""Gemeinsames Parsen von STATUS.md-Roadmap-Zeilen.

Eine Roadmap-Zeile sieht so aus:

    - [planned]   Feature-Name  # Priorität: Hoch #key:feature-name
      ^status     ^name         ^Kommentar-Zone

Die Kommentar-Zone beginnt erst bei mindestens ZWEI Leerzeichen vor einer `#`,
damit Namen mit Raute (`C#-Vorlagen`, `via # statt Position-Property`)
vollständig bleiben. Sie kommt verbatim samt führender Leerzeichen zurück,
damit Rewrites sie unverändert wieder anhängen können — dort steckt der
`#key:`-Anker, über den Playtest-Logs und Sync-Rows das Feature wiederfinden.

Diese Logik lag dreimal im Repo, zweimal davon falsch: wer den Rest der Zeile
roh als Namen nimmt, schickt "Feature  #key:foo" nach NocoDB/Notion, findet die
bestehende Row nie wieder und legt bei jedem Sync ein Duplikat an. Deshalb hier
an einer Stelle. Bewusst in `core/` statt per Import aus `$HUB_DIR` — ein
Cross-Repo-Import koppelte dieses Repo zur Importzeit an gesetztes HUB_DIR und
machte die Testsuite umgebungsabhängig.
"""
import re

COMMENT_RE = re.compile(r"\s{2,}#")
ROADMAP_RE = re.compile(r"^- \[(\w+)\]\s+(.+)$")

# `(none)` und ein leeres Feld heissen "nie gesetzt" — da darf ein Sync ein
# Feature eintragen. `(keine aktive Entwicklung)` ist dagegen eine AUSSAGE, die
# die finish-Phase bewusst schreibt: dieses Projekt hat gerade nichts Aktives.
NO_ACTIVE = "(keine aktive Entwicklung)"
UNSET_ACTIVE = ("(none)",)

# Reihenfolge der Feature-Stati. Höher gewinnt beim Zusammenführen zweier
# Quellen — ein Sync darf ein Feature nie zurückstufen.
STATUS_RANK = {"idea": 0, "discussed": 1, "planned": 2, "in_progress": 3, "done": 4}


def split_roadmap_line(line: str) -> tuple[str, str, str] | None:
    """(status, name, comment) einer Roadmap-Zeile, sonst None."""
    m = ROADMAP_RE.match(line)
    if not m:
        return None
    status, body = m.group(1), m.group(2)
    c = COMMENT_RE.search(body)
    if c:
        return status, body[:c.start()].strip(), body[c.start():]
    return status, body.strip(), ""
