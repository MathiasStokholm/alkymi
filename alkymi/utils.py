import subprocess
import sys
from typing import List, TextIO, Optional

from .logging import log


def call(args: List[str], echo_error_to_stream: Optional[TextIO] = sys.stderr) -> subprocess.CompletedProcess:
    """
    Utility command to run a system command and return the result (stdout and stderr will also be printed to the debug
    log)

    :param args: The arguments representing the command to run, e.g. ["echo", "test"]
    :param echo_error_to_stream: A stream to which to echo the call's stderr on a non-zero exit code
    :return: The result of the execution as a subprocess.CompletedProcess instance
    """
    proc = subprocess.run(args, universal_newlines=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    log.debug(proc.stdout)
    log.debug(proc.stderr)
    # Always forward error messages to stderr if needed
    if echo_error_to_stream is not None and proc.returncode:
        echo_error_to_stream.write(proc.stderr)
    proc.check_returncode()
    return proc
