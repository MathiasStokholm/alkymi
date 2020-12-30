#!/usr/bin/env python3
import shutil
from pathlib import Path

import pytest
from mypy import api

import alkymi as alk

glob_source_files = alk.recipes.glob_files(Path("alkymi"), "*.py")
glob_test_files = alk.recipes.glob_files(Path("tests"), "test_*.py")


@alk.recipe(ingredients=[glob_test_files], transient=True)
def test(test_files):
    result = pytest.main(args=[str(file) for file in test_files])
    if result != pytest.ExitCode.OK:
        raise Exception("Unit tests failed: {}".format(result))


@alk.recipe(ingredients=[glob_source_files], transient=True)
def type_check(source_files):
    args = [str(file) for file in source_files]
    result = api.run(args)
    if result[1]:
        raise Exception(result[1])

    print('Type checking report:')
    print(result[0])


@alk.recipe(transient=True)
def build() -> Path:
    # Clean output dir first
    dist_dir = Path("dist")
    if dist_dir.exists():
        shutil.rmtree(dist_dir)
    dist_dir.mkdir(exist_ok=False)

    alk.utils.call("python3 setup.py sdist bdist_wheel")
    return dist_dir


@alk.recipe(ingredients=[build], transient=True)
def release_test(build_dir) -> None:
    alk.utils.call("python3 -m twine upload --repository testpypi {}/*".format(build_dir))


@alk.recipe(ingredients=[build], transient=True)
def release(build_dir) -> None:
    alk.utils.call("python3 -m twine upload {}/*".format(build_dir))


def main():
    lab = alk.Lab("alkymi")
    lab.add_recipes(test, type_check, build, release_test, release)
    lab.open()


if __name__ == "__main__":
    main()
