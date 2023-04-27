alkymi ⚗️
==================================

Alkymi is a pure Python (3.7+) library for describing and executing tasks and pipelines with built-in caching and
conditional evaluation based on checksums.

Alkymi is easy to install, simple to use, and has no dependencies outside of Python's standard library. The code is
cross-platform, and allows you to write your pipelines once and deploy to multiple operating systems (tested on Linux,
Windows and Mac).

Check out the :ref:`installation` page for how to install alkymi, and the :ref:`quick_start` guide for how to write your
first alkymi pipeline.

The project is hosted on `Github <https://github.com/MathiasStokholm/alkymi>`_.

.. rubric:: Features

* Easily define complex data pipelines as decorated Python functions
  * This allows you to run linting, type checking, etc. on your data pipelines
* Return values are automatically cached to disk, regardless of type
* Efficiently checks if pipeline is up-to-date
  * Checks if external files have changed, bound functions have changed or if pipeline dependencies have changed
* No domain specific language (DSL) or CLI tool, just regular Python
  * Supports caching and conditional evaluation in Jupyter Notebooks
* Cross-platform - works on Linux, Windows and Mac
* Expose recipes as a command-line interface (CLI) using alkymi's :ref:`lab` type (see :ref:`command_line_interface`)

.. toctree::
    :caption: Getting Started
    :name: getting_started
    :hidden:
    :maxdepth: 1

    getting_started/installation.rst
    getting_started/quick_start.rst


.. toctree::
    :caption: Examples
    :name: examples
    :hidden:
    :maxdepth: 1

    examples/mnist.rst
    examples/command_line.rst
    examples/notebook.rst


.. toctree::
    :caption: Advanced
    :name: advanced
    :hidden:
    :maxdepth: 1

    advanced/execution.rst
    advanced/sequences.rst
    advanced/caching.rst
    advanced/checksums.rst
    advanced/configuration.rst
    advanced/built_in_recipes.rst


.. toctree::
    :caption: API Reference
    :name: api_reference
    :hidden:
    :maxdepth: 1

    api/index.rst


.. toctree::
    :caption: Project Info
    :name: project-info
    :hidden:
    :maxdepth: 1

    project_info/history
    project_info/license
