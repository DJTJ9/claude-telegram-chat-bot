#!/usr/bin/env python3
"""Migrate entries from old Tagesorganizer DB to new Tasks DB."""
import os, sys
from pathlib import Path

PROJECT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_DIR))

env_file = PROJECT_DIR / ".env"
if env_file.exists():
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())

from core.claude import run_claude

OLD_DB = "c9d2abbe-5607-44c2-bbf4-9aa673e0c4a0"
NEW_DB = "38b4bba29c5581a7bd94cef1b0cc6c58"

PROMPT = f"""Migriere alle Eintraege von der alten Datenbank (data_source_id: {OLD_DB}) in die neue Tasks-Datenbank (data_source_id: {NEW_DB}).

Vorgehen:
1. Lese ALLE Eintraege aus der alten DB (kein Filter).
2. Lese ALLE Eintraege aus der neuen DB.
3. Fuer jeden Eintrag der alten DB:
   a. Pruefe ob in der neuen DB bereits ein Eintrag mit identischem Name UND identischem Datum existiert.
   b. Falls ja: ueberspringe.
   c. Falls nein: erstelle identischen Eintrag in der neuen DB mit allen Properties:
      - Name (title)
      - Status
      - Prioritaet
      - Datum
      - Bereich
      - Notiz
      - Zyklus (falls vorhanden)
4. Antworte NUR mit: "N Eintraege migriert." (N = Anzahl neu erstellter Eintraege)"""

if __name__ == "__main__":
    result = run_claude(PROMPT, automated=True)
    print(result)
