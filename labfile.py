#!/usr/bin/env python3
import importlib
import shutil
from pathlib import Path
from typing import List

import mypy.api
import pytest
from sphinx.application import Sphinx
from flake8.api import legacy as flake8
import coverage as Coverage

import alkymi as alk

# Glob all source and test files and make them available as recipe outputs
import alkymi.alkymi

source_files = alk.recipes.glob_files("source_files", Path("alkymi"), "*.py", recursive=True)
example_files = alk.recipes.glob_files("example_files", Path("examples"), "*.py", recursive=True)
test_files = alk.recipes.glob_files("test_files", Path("tests"), "test_*.py", recursive=True)

# Also run linting and type checking on this file itself
labfile = alk.recipes.file("get_labfile", Path("labfile.py"))


@alk.recipe(transient=True)
def test(test_files: List[Path]) -> None:
    """
    Run all alkymi unit tests

    :param test_files: The pytest files to execute
    """
    result = pytest.main(args=[str(file) for file in test_files])
    if result != pytest.ExitCode.OK:
        exit(1)


@alk.recipe(transient=True)
def coverage(test_files: List[Path]) -> None:
    """
    Run all alkymi unit tests while capturing test coverage data

    :param test_files: The pytest files to execute to generate test coverage data
    """

    # TODO(mathias): Find a way to actually reload all of alkymi here
    def reimport_alk() -> None:
        importlib.reload(alk)
        importlib.reload(alk.config)
        importlib.reload(alk.types)
        importlib.reload(alk.utils)
        importlib.reload(alk.lab)
        importlib.reload(alk.decorators)
        importlib.reload(alk.recipes)
        importlib.reload(alk.logging)
        importlib.reload(alk.version)
        importlib.reload(alk.alkymi)
        importlib.reload(alk.checksums)

    cov = Coverage.coverage(source=["alkymi"])
    cov.erase()
    cov.start()

    # alkymi was already imported to run this file, so to get proper coverage, we have to reimport it here
    reimport_alk()

    test(test_files)
    cov.stop()
    cov.xml_report()
    cov.report()


@alk.recipe(transient=True)
def lint(source_files: List[Path], example_files: List[Path], test_files: List[Path], labfile: Path) -> None:
    """
    Lint all alkymi source, example and test files using flake8

    :param source_files: The alkymi source files to type check
    :param example_files: The alkymi examples files to type check
    :param test_files: The alkymi unit test files to type check
    :param labfile: This file itself to type check
    """
    style_guide = flake8.get_style_guide(max_line_length=120, max_complexity=10, ignore=["E303"])
    all_files = source_files + example_files + test_files + [labfile]
    report = style_guide.check_files([str(file) for file in all_files])
    if report.get_statistics("E"):
        exit(1)
    print("Flake8 found no style violations in {} files".format(len(all_files)))


@alk.recipe(transient=True)
def type_check(source_files: List[Path], example_files: List[Path], test_files: List[Path], labfile: Path) -> None:
    """
    Type check all alkymi source, example and test files using mypy

    :param source_files: The alkymi source files to type check
    :param example_files: The alkymi examples files to type check
    :param test_files: The alkymi unit test files to type check
    :param labfile: This file itself to type check
    """
    all_files = source_files + example_files + test_files + [labfile]
    args = [str(file) for file in all_files]
    stdout, stderr, return_code = mypy.api.run(args)
    assert not stderr, stderr

    # Print the actual results of type checking
    print("Type checking report:")
    print(stdout)

    # If no violations were found, mypy will return 0 as the return code
    if return_code != 0:
        exit(return_code)


@alk.recipe()
def docs() -> None:
    """
    Build the documentation in docs/source using Sphinx and stores it in docs/build/index.html
    """
    doc_dir = Path("docs")
    source_dir = doc_dir / "source"
    build_dir = doc_dir / "build"
    sphinx = Sphinx(str(source_dir), confdir=str(source_dir), outdir=str(build_dir),
                    doctreedir=str(build_dir / "doctrees"), buildername="html")
    sphinx.build()


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

    alk.utils.call(["python3", "setup.py", "sdist", "bdist_wheel"])
    return dist_dir


@alk.recipe(transient=True)
def release_test(build: Path) -> None:
    """
    Uploads the built alkymi distributions to the pypi test server

    :param build: The build directory containing alkymi distributions to upload
    """
    alk.utils.call(["python3", "-m", "pip", "install", "--user", "twine==3.2.0"])
    alk.utils.call(["python3", "-m", "twine", "upload", "--repository", "testpypi", "{}/*".format(build)])


@alk.recipe(transient=True)
def release(build: Path) -> None:
    """
    Uploads the built alkymi distributions to the pypi production server

    :param build: The build directory containing alkymi distributions to upload
    """
    alk.utils.call(["python3", "-m", "pip", "install", "--user", "twine==3.2.0"])
    alk.utils.call(["python3", "-m", "twine", "upload", "{}/*".format(build)])


def main():
    lab = alk.Lab("alkymi")
    lab.add_recipes(test, coverage, lint, type_check, docs, build, release_test, release)
    lab.open()


if __name__ == "__main__":
    main()
