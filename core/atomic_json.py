import json
import os
import tempfile
from pathlib import Path

from .filelock import exclusive_lock


def atomic_write(path, data):
    """Write JSON atomically: temp file in the same dir + fsync + os.replace.
    A reader always sees the complete old or new file, never a partial write."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=path.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass
        raise


def atomic_update(path, mutate, default=None):
    """Exclusive lock (on a sidecar) around read+mutate+write, so parallel
    read-modify-write cannot lose updates. `mutate` may return a new object or
    mutate the passed dict in place and return None. Returns the written data."""
    path = Path(path)
    seed = {} if default is None else default
    with exclusive_lock(str(path) + ".lock"):
        data = dict(seed)
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, ValueError):
                data = dict(seed)
        new = mutate(data)
        if new is None:
            new = data
        atomic_write(path, new)
        return new
