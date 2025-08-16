import numpy as np
import pathlib
import sys
import os

sys.path.append(str(pathlib.Path(__file__).resolve().parents[2]))
os.environ["ASR_SKIP_MODEL_LOAD"] = "1"
from server import asr_server


def test_pop_window():
    dummy_model = type(
        "M", (), {"transcribe": lambda self, audio, **k: ([], None)}
    )()
    s = asr_server.ASRServer(model=dummy_model)
    s.append_pcm16((np.ones(asr_server.SR * 2, dtype=np.int16)).tobytes())
    win = s.pop_window(seconds=1.0, keep=0.5)
    assert win is not None
    assert len(win) == asr_server.SR
    assert len(s.buf) == int(asr_server.SR * 0.5)
