"""Sits between fastchess and one engine container.

fastchess waits up to 60 s, hard-coded, for an engine that ignores `quit` before killing
it: with a hung candidate every game would cost a minute. The shim forwards stdin to the
engine and, on `quit` or end of input, kills the container after a short grace period. It
also exits as soon as the engine does, so fastchess sees a crash at once.

Usage: engine_shim.py <container-name-prefix> docker run [options] image [command]
"""

import os
import subprocess
import sys
import threading


GRACE_S = 2.0


def main() -> None:
    prefix, docker_bin, run, *rest = sys.argv[1:]
    name = f"{prefix}-{os.urandom(4).hex()}"
    engine = subprocess.Popen([docker_bin, run, "--name", name, *rest], stdin=subprocess.PIPE)
    assert engine.stdin is not None

    def exit_with_engine() -> None:
        os._exit(engine.wait())

    threading.Thread(target=exit_with_engine, daemon=True).start()
    try:
        while line := sys.stdin.buffer.readline():
            engine.stdin.write(line)
            engine.stdin.flush()
            if line.strip() == b"quit":
                break
        engine.stdin.close()
    except BrokenPipeError:
        pass  # the engine is gone: the waiting thread reports how it ended
    try:
        engine.wait(GRACE_S)
    except subprocess.TimeoutExpired:
        subprocess.run([docker_bin, "kill", name], capture_output=True, check=False)
    os._exit(engine.wait())


if __name__ == "__main__":
    main()
