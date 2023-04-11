import subprocess
import sys
from typing import List, TextIO, Optional

from .logging import log


def call(args: List[str], echo_error_to_stream: Optional[TextIO] = sys.stderr,
         echo_output_to_stream: Optional[TextIO] = sys.stdout) -> subprocess.CompletedProcess:
    """
    Utility command to run a system command and return the result (stdout and stderr will also be printed to the debug
    log)

    :param args: The arguments representing the command to run, e.g. ["echo", "test"]
    :param echo_error_to_stream: A stream to which to echo the call's stderr on a non-zero exit code
    :param echo_output_to_stream: A stream to which to echo the call's stdout while the command is executing
    :return: The result of the execution as a subprocess.CompletedProcess instance
    """
    # If running through a Lab CLI, sys.stdout may have been redirected
    if echo_output_to_stream is not None and getattr(echo_output_to_stream, "name", None) == sys.stdout.name:
        echo_output_to_stream = sys.stdout

    # Buffer one line at a time if echoing live, otherwise just use the default
    buffer_size = 1 if echo_output_to_stream is not None else -1
    proc = subprocess.Popen(args, universal_newlines=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            bufsize=buffer_size)

    # Since we set these to PIPE, these should never be None
    assert proc.stdout is not None
    assert proc.stderr is not None

    stdout: str = ""
    if echo_output_to_stream is not None:
        # Print each line to the stream as it arrives
        while proc.poll() is None:
            line = proc.stdout.readline()
            echo_output_to_stream.write(line)
            stdout += line

        # Program has finished executing, check if any part of stdout still needs to be piped
        line = proc.stdout.readline()
        if line:
            echo_output_to_stream.write(line)
            stdout += line
    else:
        # Otherwise, simply wait for the command to finish and then grab stdout
        proc.wait()
        stdout = proc.stdout.read()

    stderr = proc.stderr.read()

    # Send to alkymi log
    log.debug(stdout)
    log.debug(stderr)

    # Always forward error messages to stderr if needed
    if echo_error_to_stream is not None and proc.returncode != 0:
        echo_error_to_stream.write(stderr)

    # Raise an error on failure
    if proc.returncode != 0:
        raise subprocess.CalledProcessError(proc.returncode, proc.args, stdout, stderr)
    return subprocess.CompletedProcess(proc.args, proc.returncode, stdout, stderr)
