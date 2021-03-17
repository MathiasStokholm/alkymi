#!/usr/bin/env python
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
