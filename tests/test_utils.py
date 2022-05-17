#!/usr/bin/env python
import io
import subprocess

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
