.. _command_line_interface:

Command Line Interface
======================

In some scenarios, you may need to automate multiple tasks, and writing a Python script script for each might be a bit
tedious - a common example of this is a Makefile that has rules for "style" (style checking), "install" (fetch
dependencies), etc. In this case, you can use alkymi's :ref:`lab` functionality:

.. code-block:: python

    from pathlib import Path
    import alkymi as alk
    import pytest

    # 'glob_files()' is a built-in recipe generator that globs and returns a list of files
    test_files = alk.recipes.glob_files(Path("tests"), "test_*.py", recursive=True)

    @alk.recipe()
    def test(test_files: List[Path]) -> None:
        # Convert Path objects to str
        result = pytest.main(args=[str(file) for file in test_files])
        if result != pytest.ExitCode.OK:
            raise Exception("Unit tests failed: {}".format(result))

    lab = alk.Lab("tests")
    lab.add_recipes(test)
    lab.open()


The above code will cause the script to present the user with a command-line interface (CLI) with the following options:

* ``status``: Prints detailed status of all recipes contained in the lab (cached, needs reevaluation etc.)
* ``brew``: Runs one or more recipes with the provided names (in the above, running ``python labfile.py brew test``
  would run the unit tests)

alkymi uses a *labfile* (``labfile.py`` in the root of the repo) to automate tasks such as linting using flake8, static
type checking using mypy, running unit tests using pytest, as well as creating and uploading distributions to PyPI. Note
that ``labfile.py`` is also subject to static type checking and linting, just like every other Python file.

alkymi's :ref:`lab` functionality also allows for providing arguments to alkymi's evaluation system using alkymi's built
in arg recipe (see :ref:`built_in_recipes`):

.. code-block:: python

    import alkymi as alk

    name = alk.arg("John", name="name")

    @alk.recipe()
    def print_name(name: str) -> None:
        print(name)

    lab = alk.Lab("name printer")
    lab.add_recipes(print_name)
    lab.register_arg(name)
    lab.open()


The above code now allows the user to set the name and run the recipe from the CLI:

.. code-block:: shell

    python name_printer.py brew print_name --name "Robert"
