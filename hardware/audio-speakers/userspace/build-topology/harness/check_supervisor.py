#!/usr/bin/env python3
"""Exercise candidate supervisor against fake ALSA; no PCM/device is opened."""

import importlib.machinery
import importlib.util
import signal
import tempfile
from pathlib import Path


HERE = Path(__file__).resolve().parent
SOURCE = HERE.parents[1] / "closed-loop/speaker-supervisor"
loader = importlib.machinery.SourceFileLoader("supervisor_candidate", str(SOURCE))
spec = importlib.util.spec_from_loader(loader.name, loader)
supervisor = importlib.util.module_from_spec(spec)
loader.exec_module(supervisor)


class Function:
    def __init__(self, call):
        self.call = call

    def __call__(self, *args):
        return self.call(*args)


class FakeAlsa:
    def __init__(self, states):
        self.states = iter(states)
        self.calls = []
        self.snd_pcm_open = Function(lambda *a: self.record("open", a, 0))
        self.snd_pcm_set_params = Function(lambda *a: self.record("params", a, 0))
        self.snd_pcm_prepare = Function(lambda *a: self.record("prepare", a, 0))
        self.snd_pcm_start = Function(lambda *a: self.record("start", a, 0))
        self.snd_pcm_state = Function(lambda *a: next(self.states))
        self.snd_pcm_avail_update = Function(lambda *a: 4)
        self.snd_pcm_readi = Function(lambda *a: self.record("read", a, a[-1]))
        self.snd_pcm_close = Function(lambda *a: self.record("close", a, 0))

    def record(self, name, args, result):
        self.calls.append((name, args))
        return result


def main():
    with tempfile.TemporaryDirectory(prefix="sp11-supervisor-") as tmp:
        info = Path(tmp) / "info"
        supervisor.Path = lambda _path: info
        info.write_text("id: MultiMedia5\nname: MultiMedia5 Capture\n")
        supervisor.verify_frontend("hw:0,4")
        info.write_text("id: MultiMedia2\nname: microphone\n")
        try:
            supervisor.verify_frontend("hw:0,4")
            raise AssertionError("wrong FE accepted")
        except RuntimeError:
            pass
        for name in ("default", "hw:0,4,0"):
            try:
                supervisor.verify_frontend(name)
                raise AssertionError("non-explicit FE accepted")
            except RuntimeError:
                pass
    print("PASS: MultiMedia5 identity required")
    supervisor.verify_frontend = lambda _device: None
    alsa = FakeAlsa([3, 3, 4])
    supervisor.ctypes.CDLL = lambda _name: alsa
    supervisor.signal.signal = lambda *_args: None
    supervisor.time.sleep = lambda _secs: None
    try:
        supervisor.run("hw:0,4")
        raise AssertionError("XRUN was not reported")
    except RuntimeError as exc:
        assert "lost RUNNING" in str(exc)
    calls = dict(alsa.calls)
    assert calls["open"][1:] == (b"hw:0,4", 1, 1)
    assert calls["params"][1:] == (2, 3, 2, 48000, 0, 500000)
    assert calls["read"][-1] == 4 and "close" in calls
    print("PASS: S16_LE/48 kHz/stereo requested, bytes discarded, XRUN exits and closes")
    callbacks = {}
    alsa = FakeAlsa([3, 3, 3])
    available = iter([4, 0])
    alsa.snd_pcm_avail_update = Function(lambda *_args: next(available))
    supervisor.ctypes.CDLL = lambda _name: alsa
    supervisor.signal.signal = lambda signum, fn: callbacks.update({signum: fn})
    supervisor.time.sleep = lambda _secs: callbacks[signal.SIGTERM](signal.SIGTERM, None)
    supervisor.run("hw:0,4")
    assert any(name == "close" for name, _ in alsa.calls)
    print("PASS: SIGTERM closes capture")


if __name__ == "__main__":
    main()
