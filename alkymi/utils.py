import asyncio
import fcntl
import os
import subprocess
import sys
import threading
import time
from typing import List, TextIO, Optional, TypeVar, Callable


def call(args: List[str], echo_error_to_stream: Optional[TextIO] = sys.stderr,
         echo_output_to_stream: Optional[TextIO] = sys.stdout) -> subprocess.CompletedProcess:
    """
    Utility command to run a system command and return the result

    :param args: The arguments representing the command to run, e.g. ["echo", "test"]
    :param echo_error_to_stream: A stream to which to echo the call's stderr while the command is executing
    :param echo_output_to_stream: A stream to which to echo the call's stdout while the command is executing
    :return: The result of the execution as a subprocess.CompletedProcess instance
    """
    # If running through a Lab CLI, sys.stdout may have been redirected
    if echo_output_to_stream is not None and getattr(echo_output_to_stream, "name", None) == sys.stdout.name:
        echo_output_to_stream = sys.stdout

    # If running through a Lab CLI, sys.stderr may have been redirected
    if echo_error_to_stream is not None and getattr(echo_error_to_stream, "name", None) == sys.stderr.name:
        echo_error_to_stream = sys.stderr

    live_stdout = echo_output_to_stream is not None
    live_stderr = echo_error_to_stream is not None

    # Buffer one line at a time if echoing live, otherwise just use the default
    buffer_size = 1 if (live_stdout or live_stderr) else -1
    proc = subprocess.Popen(args, universal_newlines=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            bufsize=buffer_size)

    # If running either stdout or stderr live, set the streams to non-blocking mode to ensure that we don't block
    # when trying to read from either of them
    if live_stdout:
        fl = fcntl.fcntl(proc.stdout, fcntl.F_GETFL)
        fcntl.fcntl(proc.stdout, fcntl.F_SETFL, fl | os.O_NONBLOCK)
    if live_stderr:
        fl = fcntl.fcntl(proc.stderr, fcntl.F_GETFL)
        fcntl.fcntl(proc.stderr, fcntl.F_SETFL, fl | os.O_NONBLOCK)

    # Since we set these to PIPE, these should never be None
    assert proc.stdout is not None
    assert proc.stderr is not None

    stdout: str = ""
    stderr: str = ""
    if live_stdout or live_stderr:
        # Print each line to the stream as it arrives
        while proc.poll() is None:
            if live_stdout:
                line = proc.stdout.readline()
                echo_output_to_stream.write(line)
                stdout += line
            if live_stderr:
                line = proc.stderr.readline()
                echo_error_to_stream.write(line)
                stderr += line

            # Sleep for a tiny bit to ensure that the non-blocking calls don't eat a ton of CPU
            time.sleep(0.001)

        # Program has finished executing, check if any part of stdout or stderr still needs to be piped
        if live_stdout:
            while line := proc.stdout.readline():
                echo_output_to_stream.write(line)
                stdout += line
        if live_stderr:
            while line := proc.stderr.readline():
                echo_error_to_stream.write(line)
                stderr += line
    else:
        # Otherwise, simply wait for the command to finish and then grab stdout and/or stderr
        proc.wait()

    # If not running live, read everything in one go
    if not live_stdout:
        stdout = proc.stdout.read()
    if not live_stderr:
        stderr = proc.stderr.read()

    # Raise an error on failure
    if proc.returncode != 0:
        raise subprocess.CalledProcessError(proc.returncode, proc.args, stdout, stderr)
    return subprocess.CompletedProcess(proc.args, proc.returncode, stdout, stderr)


T = TypeVar('T')


def run_on_thread(func: Callable[..., T]) -> T:
    """
    Execute a function on a new thread and return the result - exceptions will be propagated by re-raising
    :param func: The function to run on the new thread
    :return: The result of the function call
    """

    # Mutable object used to store result
    result: List[T] = []
    ex = []

    def _call_and_set_result():
        nonlocal result
        try:
            result.append(func())
        except Exception as e:
            ex.append(e)

    t = threading.Thread(target=_call_and_set_result)
    t.start()
    t.join()

    # Check if an exception occurred, and reraise
    if len(ex) != 0:
        raise ex[0]

    # Ensure that result has been set, and return it
    assert len(result) == 1, "Function call should have stored return value in result variable"
    return result[0]


def check_current_thread_has_running_event_loop():
    """
    Check if the calling thread has an associated running event loop
    :return: True if the calling thread has a running event loop associated with it
    """
    try:
        asyncio.get_running_loop()
        return True
    except RuntimeError:
        return False
