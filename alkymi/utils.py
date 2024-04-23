import asyncio
import subprocess
import sys
import threading
from typing import List, TextIO, Optional, TypeVar, Callable, IO, Any


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

    # Use shorthands - note that the full check is still used in some places below to satisfy mypy
    live_stdout = echo_output_to_stream is not None
    live_stderr = echo_error_to_stream is not None

    # Buffer one line at a time if echoing live, otherwise just use the default
    buffer_size = 1 if (live_stdout or live_stderr) else -1
    proc = subprocess.Popen(args, universal_newlines=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            bufsize=buffer_size)

    # Since we set these to PIPE, these should never be None
    assert proc.stdout is not None
    assert proc.stderr is not None

    # Variables that will hold the read stdout and stderr
    stdout: str = ""
    stderr: str = ""

    # If reading both stdout and stderr, use threads to avoid blocking
    if live_stdout and live_stderr:
        assert echo_output_to_stream is not None
        assert echo_error_to_stream is not None
        stdout_fut = run_on_thread(_tee_pipe, proc, proc.stdout, echo_output_to_stream)
        stderr_fut = run_on_thread(_tee_pipe, proc, proc.stderr, echo_error_to_stream)
        stdout = stdout_fut()
        stderr = stderr_fut()
    elif live_stdout:
        assert echo_output_to_stream is not None
        stdout = _tee_pipe(proc, proc.stdout, echo_output_to_stream)
    elif live_stderr:
        assert echo_error_to_stream is not None
        stderr = _tee_pipe(proc, proc.stderr, echo_error_to_stream)
    else:
        # Otherwise, simply wait for the command to finish and then grab stdout and/or stderr
        proc.wait()
        stdout = proc.stdout.read()
        stderr = proc.stderr.read()

    # Raise an error on failure
    if proc.returncode != 0:
        raise subprocess.CalledProcessError(proc.returncode, proc.args, stdout, stderr)
    return subprocess.CompletedProcess(proc.args, proc.returncode, stdout, stderr)


def _tee_pipe(proc: subprocess.Popen, input_stream: IO[str], output_stream: TextIO) -> str:
    """
    Reads the content of an input stream while the provided process is running, and echoes it to the provided output
    stream in real time, while also collecting everything read into a string that is returned once the process has
    finished executing and all output has been read

    :param proc: The process that produces the output
    :param input_stream: The stream to read from (should be `proc.stdout` or `proc.stderr`)
    :param output_stream: The stream to write output to
    :return: Everything that was read
    """
    content: str = ""

    # Program is executing, echo lines as they come in
    while proc.poll() is None:
        line = input_stream.readline()
        output_stream.write(line)
        content += line

    # Program has finished executing, check if any part of stdout or stderr still needs to be piped
    line = " "
    while line:
        line = input_stream.readline()
        output_stream.write(line)
        content += line

    return content


T = TypeVar('T')


def run_on_thread(func: Callable[..., T], *args: Any) -> Callable[[], T]:
    """
    Execute a function on a new thread and return a function that can be used to wait for the result - exceptions will
    be propagated by re-raising once the result is waited for

    :param func: The function to run on the new thread
    :param args: The arguments to pass to the function
    :return: A function (future) that can be called to block and return the value of the function call
    """

    # Mutable object used to store result
    result: List[T] = []
    ex: List[Exception] = []

    def _call_and_set_result():
        nonlocal result, ex
        try:
            result.append(func(*args))
        except Exception as e:
            ex.append(e)

    t = threading.Thread(target=_call_and_set_result)
    t.start()

    def get_result() -> T:
        # Wait for thread to finish executing
        t.join()

        # Check if an exception occurred, and reraise
        if len(ex) != 0:
            raise ex[0]

        # Ensure that result has been set, and return it
        assert len(result) == 1, "Function call should have stored return value in result variable"
        return result[0]

    return get_result


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
