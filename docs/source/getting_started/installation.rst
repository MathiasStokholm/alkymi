.. _installation:

Installation
============

Install via pip - note that alkymi has no dependencies and works on Linux, Windows and Mac:

.. code-block:: bash

    pip install --user alkymi


Or clone and install directly from source:

.. code-block:: bash

    git clone https://github.com/MathiasStokholm/alkymi.git
    cd alkymi
    pip install --user .

Or install using pip and github:

.. code-block:: bash

    pip install --user git+https://github.com/MathiasStokholm/alkymi.git

If you intend to work with large files outside of alkymi's cache, consider also depending on xxhash to speed up
checksumming of large files:

.. code-block:: bash

    pip install --user alkymi[xxhash]
