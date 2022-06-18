#!/usr/bin/env python
import io
import subprocess
import threading
import time

import pytest

import alkymi.utils


def test_call():
    """
    Test that the utils.call() function behaves correctly on all operating systems
    """
    input_string = "hello alkymi!"
    result = alkymi.utils.call(["python3", "-c", "print('{}')".format(input_string)])
    assert result.returncode == 0
    assert result.stderr == ""
    assert result.stdout == input_string + "\n"


def test_call_error():
    """
    Test that the utils.call() function correctly prints error information to the provided stream and raises an error
    on failure
    """
    error_str = "A long and complicated error description"
    stream = io.StringIO()
    with pytest.raises(subprocess.CalledProcessError):
        alkymi.utils.call(["python3", "-c", "raise RuntimeError('{}')".format(error_str)], echo_error_to_stream=stream)
    stream.seek(0)
    assert error_str in stream.read()


def test_call_updates():
    """
    Test that the utils.call() function can correctly return stdout line-by-line while a command is executing (to enable
    live output).
    """
    num_outputs = 5

    stream = io.StringIO()
    times = []
    process_stream = True

    # Use a thread to monitor the stream continuously while the command is being executed
    def _monitor_thread():
        last_output = ""
        while process_stream:
            output = stream.getvalue()

            # If output hasn't changed, keep trying
            if not output or output == last_output:
                time.sleep(0.001)
                continue

            # Store the last output and the timestamp
            last_output = output
            times.append(time.time())

    stream_monitor = threading.Thread(target=_monitor_thread)
    stream_monitor.start()

    # Script to execute - simply prints a number of numbers, each on a separate line followed by a sleep
    program = """
import time

for i in range({}):
    print(i)
    time.sleep(0.01)
    """.format(num_outputs)

    alkymi.utils.call(["python3", "-c", program], echo_output_to_stream=stream)

    # Stop reader thread
    process_stream = False
    stream_monitor.join()

    # We expect to have an output per iteration of the called program
    assert len(times) == num_outputs

    # Each output should have been generated at a different time than the previous one
    for i in range(len(times) - 1):
        assert times[i] < times[i + 1]
