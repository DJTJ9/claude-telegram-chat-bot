"""Konsolen-Ausgabe, die auf der Windows-Kiste nicht am Encoding stirbt.

Auf dem Server ist stdout UTF-8, unter Windows cp1252. Ein `print("✅ fertig")`
oder ein Feature-Name mit `→` wirft dort `UnicodeEncodeError` — und zwar NACH
der eigentlichen Arbeit, beim Melden des Erfolgs. Das Script beendet sich mit
Exit 1, obwohl alles geklappt hat; Aufrufer, die den Exit-Code auswerten
(Gates, Skill-Phasen), lesen das als echten Fehlschlag.

`errors="replace"` statt Umstellen auf UTF-8: die Zeichen werden zu `?`, wenn
die Konsole sie nicht kann, statt als Mojibake durchzurutschen. Umleitungen in
Dateien bleiben unberührt, deren Encoding hängt an der Umleitung selbst.
"""
import sys


def enable_safe_console() -> None:
    """Idempotent — mehrfacher Aufruf ist unschädlich."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(errors="replace")
            except (ValueError, OSError):
                # Stream schon geschlossen oder nicht rekonfigurierbar
                # (z.B. gemockt im Test) — dann eben ohne.
                pass
