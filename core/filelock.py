"""Plattformübergreifender exklusiver Dateilock.

`fcntl` gibt es nur auf POSIX — ein `import fcntl` auf Modulebene macht jedes
Script, das ihn zieht, auf der Windows-Kiste unbenutzbar (ModuleNotFoundError
schon beim Import, also auch für Aufrufe, die gar keinen Lock brauchen).
Hier liegt die Fallunterscheidung an EINER Stelle:

- POSIX:   `fcntl.flock` (LOCK_EX) — advisory, pro Open-File-Description.
- Windows: `msvcrt.locking` auf ein Byte — mandatory, pro Datei-Handle.

Beide Pfade greifen nicht-blockierend an und wiederholen, damit die Semantik
auf beiden Plattformen identisch ist: nach `timeout` Sekunden ohne Erfolg
fliegt ein `TimeoutError`, statt still ewig zu warten.
"""
import os
import sys
import time
from contextlib import contextmanager
from pathlib import Path

_WINDOWS = os.name == "nt"

if _WINDOWS:
    import msvcrt
else:
    import fcntl

DEFAULT_TIMEOUT = 60.0
_RETRY_INTERVAL = 0.05


def _try_acquire(fh) -> bool:
    """Einmaliger, nicht-blockierender Versuch. True = Lock gehört uns."""
    try:
        if _WINDOWS:
            fh.seek(0)
            msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        return True
    except OSError:
        # POSIX: BlockingIOError. Windows: OSError(EDEADLOCK/EACCES).
        # Beide sind Unterklassen von OSError — "jemand anderes hält ihn".
        return False


def _release(fh) -> None:
    try:
        if _WINDOWS:
            fh.seek(0)
            msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
    except OSError:
        # Beim Schließen des Handles gibt das OS den Lock ohnehin frei; ein
        # Fehler hier darf den eigentlichen Vorgang nicht nachträglich kippen.
        pass


@contextmanager
def exclusive_lock(path, timeout: float = DEFAULT_TIMEOUT):
    """Exklusiver Lock auf `path` (eigene Lock-Datei, nicht die Nutzdatei)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # "a+" statt "w": Truncate scheitert unter Windows an einer Datei, die ein
    # anderer Prozess gerade gelockt hält — der Lock wäre dann nicht mal
    # anforderbar. Anhängen öffnet auch eine gelockte Datei.
    with open(path, "a+") as fh:
        deadline = time.monotonic() + timeout
        while not _try_acquire(fh):
            if time.monotonic() >= deadline:
                raise TimeoutError(
                    f"Lock {path} nach {timeout:.0f}s nicht bekommen — "
                    f"hängt ein anderer Prozess?")
            time.sleep(_RETRY_INTERVAL)
        try:
            yield fh
        finally:
            _release(fh)
