#!/usr/bin/env python3
import shutil
from pathlib import Path

import mypy.api
import pytest

import alkymi as alk

# Glob all source and test files and make them available as recipe outputs
glob_source_files = alk.recipes.glob_files(Path("alkymi"), "*.py")
glob_test_files = alk.recipes.glob_files(Path("tests"), "test_*.py")


@alk.recipe(ingredients=[glob_test_files], transient=True)
def test(test_files) -> None:
    """
    Run all alkymi unit tests

    :param test_files: The pytest files to execute
    """
    result = pytest.main(args=[str(file) for file in test_files])
    if result != pytest.ExitCode.OK:
        raise Exception("Unit tests failed: {}".format(result))


@alk.recipe(ingredients=[glob_source_files], transient=True)
def type_check(source_files) -> None:
    """
    Type check all alkymi source files using mypy

    :param source_files: The alkymi source files to type check
    """
    args = [str(file) for file in source_files]
    stdout, stderr, return_code = mypy.api.run(args)
    if stderr:
        raise RuntimeError(stderr)

    # Print the actual results of type checking
    print("Type checking report:")
    print(stdout)

    # If no violations were found, mypy will return 0 as the return code
    if return_code != 0:
        raise RuntimeError("mypy returned exit code: {}".format(return_code))


@alk.recipe(transient=True)
def build() -> Path:
    """
    Builds the distributions (source + wheel) for alkymi

    :return: The directory holding the outputs
    """
    # Clean output dir first
    dist_dir = Path("dist")
    if dist_dir.exists():
        shutil.rmtree(dist_dir)
    dist_dir.mkdir(exist_ok=False)

    alk.utils.call("python3 setup.py sdist bdist_wheel")
    return dist_dir


@alk.recipe(ingredients=[build], transient=True)
def release_test(build_dir) -> None:
    """
    Uploads the built alkymi distributions to the pypi test server

    :param build_dir: The build directory containing alkymi distributions to upload
    """
    alk.utils.call("python3 -m twine upload --repository testpypi {}/*".format(build_dir))


@alk.recipe(ingredients=[build], transient=True)
def release(build_dir) -> None:
    """
    Uploads the built alkymi distributions to the pypi production server

    :param build_dir: The build directory containing alkymi distributions to upload
    """
    alk.utils.call("python3 -m twine upload {}/*".format(build_dir))


def main():
    lab = alk.Lab("alkymi")
    lab.add_recipes(test, type_check, build, release_test, release)
    lab.open()


if __name__ == "__main__":
    main()
