import subprocess
from .logging import log


def call(command: str) -> subprocess.CompletedProcess:
    proc = subprocess.run(command, universal_newlines=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    log.debug(proc.stdout)
    log.debug(proc.stderr)
    proc.check_returncode()
    return proc
