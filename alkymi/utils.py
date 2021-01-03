import subprocess
from .logging import log


def call(command: str) -> subprocess.CompletedProcess:
    """
    Utility command to run a system command and return the result (stdout and stderr will also be printed to the debug
    log)

    :param command: The command to execute, e.g. "echo 'test'"
    :return: The result of the execution as a subprocess.CompletedProcess instance
    """
    proc = subprocess.run(command, universal_newlines=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    log.debug(proc.stdout)
    log.debug(proc.stderr)
    proc.check_returncode()
    return proc
