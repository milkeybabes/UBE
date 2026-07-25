from __future__ import annotations

import hashlib
from pathlib import Path


def sha256_file(path: str | Path, chunk_size: int = 1024 * 1024, progress_callback=None) -> str:
    p = Path(path)
    h = hashlib.sha256()
    total = 0
    try:
        total = int(p.stat().st_size)
    except Exception:
        total = 0
    done = 0
    report_every = max(int(chunk_size), 16 * 1024 * 1024)
    next_report = 0
    with p.open("rb") as f:
        while True:
            b = f.read(chunk_size)
            if not b:
                break
            h.update(b)
            done += len(b)
            if progress_callback is not None and (done >= next_report or (total and done >= total)):
                try:
                    progress_callback(done, total)
                except Exception:
                    pass
                next_report = done + report_every
    return h.hexdigest()
