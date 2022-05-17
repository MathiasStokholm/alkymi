#!/usr/bin/env python
import io
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
    assert str(alk.Status.NotEvaluatedYet) in status_msg
    assert str(alk.Status.Ok) not in status_msg

    # Use open to brew one of the recipes and check that status has changed
    stream.seek(0)
    lab.open(["brew", another_string.name])

    # Note that verbose is a global argument before the actual lab command
    lab.open(["--verbose", "status"], stream=stream)
    stream.seek(0)
    status_msg = stream.read()
    assert str(alk.Status.Ok) in status_msg


def test_lab_arg() -> None:
    """
    Test providing an argument to a recipe through a lab's command line interface
    """
    AlkymiConfig.get().cache = False

    arg = alk.arg(42, name="an_arg")
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
