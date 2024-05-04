#!/usr/bin/env python
import io
import time
from typing import List

import pytest

import alkymi as alk
from alkymi import AlkymiConfig


def test_empty_lab() -> None:
    """
    Test the empty lab state and error handling before recipes are added
    """
    AlkymiConfig.get().cache = False

    lab_name = "empty lab"
    lab = alk.Lab(lab_name)
    assert lab.name == lab_name

    # Initially, a lab should have no recipes
    assert len(lab.recipes) == 0

    # Calling brew before adding recipes should result in a failure
    with pytest.raises(ValueError):
        lab.brew("non_existent_recipe")

    @alk.recipe()
    def test_recipe() -> str:
        return "42"

    # Calling brew using a recipe that hasn't been added to the lab should also fail
    with pytest.raises(ValueError):
        lab.brew(test_recipe)

    # Trying to open an empty lab should result in an error
    with pytest.raises(RuntimeError):
        lab.open()


def test_lab_brew() -> None:
    """
    Test adding recipes to a lab and calling brew to run the recipes by reference or name
    """
    AlkymiConfig.get().cache = False

    @alk.recipe()
    def a_string() -> str:
        return "42"

    lab = alk.Lab("example lab")
    lab.add_recipe(a_string)
    assert lab.brew(a_string) == "42"
    assert lab.brew("a_string") == "42"

    @alk.recipe()
    def another_string() -> str:
        return "4242"

    lab.add_recipes(another_string, another_string)
    assert lab.brew(another_string) == "4242"


def test_lab_open() -> None:
    """
    Test interfacing with the lab using the command line interface (by providing string arguments)
    """
    AlkymiConfig.get().cache = False

    @alk.recipe()
    def a_string() -> str:
        return "42"

    @alk.recipe()
    def another_string() -> str:
        return "4242"

    lab = alk.Lab("example lab")
    lab.add_recipes(a_string, another_string)
    assert a_string in lab.recipes
    assert another_string in lab.recipes
    assert len(lab.recipes) == 2

    stream = io.StringIO()
    lab.open(["status"], stream=stream)

    # Check important parts of content that was printed
    stream.seek(0)
    status_msg = stream.read()
    assert lab.name in status_msg
    assert a_string.name in status_msg
    assert another_string.name in status_msg
    assert str(alk.Status.NotEvaluatedYet).replace("Status.", "") in status_msg
    assert str(alk.Status.Ok).replace("Status.", "") not in status_msg

    # Use open to brew one of the recipes and check that status has changed
    stream.seek(0)
    lab.open(["brew", another_string.name])

    # Note that verbose is a global argument before the actual lab command
    lab.open(["--verbose", "status"], stream=stream)
    stream.seek(0)
    status_msg = stream.read()
    assert str(alk.Status.Ok).replace("Status.", "") in status_msg


@pytest.mark.parametrize("arg_name", ("an_arg", "an-arg"))
def test_lab_arg(arg_name: str) -> None:
    """
    Test providing an argument to a recipe through a lab's command line interface
    """
    AlkymiConfig.get().cache = False

    arg = alk.arg(42, name=arg_name)
    output = 0

    @alk.recipe()
    def arg_squared(arg: int) -> int:
        nonlocal output
        output = arg ** 2  # NOQA: Intentionally setting outside state
        return output

    lab = alk.Lab("arg lab")
    lab.add_recipe(arg_squared)
    lab.register_arg(arg)

    assert lab.brew(arg_squared) == 42 ** 2
    assert output == 42 ** 2

    new_value = 9
    lab.open(["brew", arg_squared.name, "--{}={}".format(arg.name, new_value)])
    assert output == new_value ** 2
    assert arg.brew() == new_value


def test_lab_arg_string_list() -> None:
    """
    Test providing a list of strings as an argument to a recipe through a lab's command line interface
    """
    AlkymiConfig.get().cache = False

    arg = alk.arg(["initial"], name="arguments")
    output = ""

    @alk.recipe()
    def arg_joined(arg: List[str]) -> str:
        nonlocal output
        output = "".join(arg)  # NOQA: Intentionally setting outside state
        return output

    lab = alk.Lab("arg lab")
    lab.add_recipe(arg_joined)
    lab.register_arg(arg)

    assert lab.brew(arg_joined) == "initial"
    assert output == "initial"

    lab.open(["brew", arg_joined.name, "--{}".format(arg.name), "first", "second", "third"])
    assert output == "firstsecondthird"


def test_lab_keyboard_interrupt(capsys: pytest.CaptureFixture) -> None:
    """
    Test that a Lab will correctly handle user interruption through a keyboard interrupt (CTRL-C)
    """

    # Create a lab containing a single recipe that will raise a KeyboardInterrupt (simulating user input)
    @alk.recipe()
    def interrupt() -> None:
        raise KeyboardInterrupt()

    lab = alk.Lab("interrupt lab")
    lab.add_recipe(interrupt)

    # Brew the interrupt recipe through the lab - this should result in an attempted system exit with error code 1
    with pytest.raises(SystemExit) as exc_info:
        lab.brew(interrupt)
    assert exc_info.value.code == 1

    # Check that the appropriate traceback was printed to stderr
    assert "Interrupted by user" in capsys.readouterr().out


def test_lab_omits_alkymi_internals_in_traceback(capsys: pytest.CaptureFixture) -> None:
    """
    Test that a Lab will remove alkymi internal lines from the traceback upon an exception in user code (recipe)
    """

    # Create a lab containing a single recipe that will raise on execution
    expected_error_message = f"Failure @ {time.time()}"

    @alk.recipe()
    def fail() -> None:
        raise RuntimeError(expected_error_message)

    lab = alk.Lab("failure lab")
    lab.add_recipe(fail)

    # Brew the failing recipe through the lab - this should result in an attempted system exit with error code 2
    with pytest.raises(SystemExit) as exc_info:
        lab.brew(fail)
    assert exc_info.value.code == 2

    # Check that the appropriate traceback was printed to stderr
    printed_error = capsys.readouterr().err

    # The traceback should contain the following:
    assert 'lab.brew(fail)' in printed_error  # The lab invocation that led to the failure
    assert '<alkymi internals omitted...>' in printed_error  # A statement that alkymi internals were omitted
    assert 'in fail' in printed_error  # The recipe (function) that failed
    assert 'RuntimeError(expected_error_message)' in printed_error  # The line that failed
    assert f"RuntimeError: {expected_error_message}" in printed_error  # The actual error message

    # The traceback should not contain the following:
    assert 'alkymi/core.py' not in printed_error  # Any line related to the internal execution engine of alkymi
