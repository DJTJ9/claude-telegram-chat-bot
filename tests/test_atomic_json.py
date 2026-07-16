import json
import multiprocessing as mp
from pathlib import Path

from core.atomic_json import atomic_update, atomic_write


def _bump(path):
    # Increment counter under lock; a small sleep widens the RMW race window.
    import time
    def m(d):
        d["n"] = d.get("n", 0) + 1
        time.sleep(0.001)
    atomic_update(path, m)


def test_parallel_writers_no_lost_update(tmp_path):
    p = tmp_path / "settings.json"
    atomic_write(p, {"n": 0})
    procs = [mp.Process(target=_bump, args=(str(p),)) for _ in range(20)]
    for pr in procs:
        pr.start()
    for pr in procs:
        pr.join()
    assert json.loads(p.read_text())["n"] == 20


def test_pending_dev_exactly_once(tmp_path):
    p = tmp_path / "settings.json"
    atomic_write(p, {"pending_dev": {"a": {"command": "/dev implement"}}})

    def consume(box):
        def m(d):
            pd = d.get("pending_dev")
            if isinstance(pd, dict) and "a" in pd:
                box["entry"] = pd.pop("a")
                if not pd:
                    d.pop("pending_dev", None)
        atomic_update(p, m)

    first, second = {"entry": None}, {"entry": None}
    consume(first)
    consume(second)
    assert first["entry"] == {"command": "/dev implement"}
    assert second["entry"] is None
    assert "pending_dev" not in json.loads(p.read_text())


def _spin_writer(path, stop_after):
    for i in range(stop_after):
        atomic_write(path, {"payload": "x" * 5000, "i": i})


def test_reader_never_sees_partial_json(tmp_path):
    p = tmp_path / "settings.json"
    atomic_write(p, {"payload": "x" * 5000, "i": -1})
    w = mp.Process(target=_spin_writer, args=(str(p), 300))
    w.start()
    errors = 0
    for _ in range(2000):
        try:
            json.loads(p.read_text())
        except json.JSONDecodeError:
            errors += 1
    w.join()
    assert errors == 0


def test_mutate_returning_new_dict(tmp_path):
    p = tmp_path / "s.json"
    atomic_write(p, {"a": 1})
    out = atomic_update(p, lambda d: {**d, "b": 2})
    assert out == {"a": 1, "b": 2}
    assert json.loads(p.read_text()) == {"a": 1, "b": 2}


def test_corrupt_file_falls_back_to_default(tmp_path):
    p = tmp_path / "s.json"
    p.write_text("{ broken")
    out = atomic_update(p, lambda d: d, default={"seed": 1})
    assert out == {"seed": 1}
