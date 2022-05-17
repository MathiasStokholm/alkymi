.. _checksums:

Checksums
=========

alkymi uses checksums to determine whether nodes in the pipeline are up-to-date. Checksumming is implemented for
arbitrary types by using a recursive MD5 (or xxhash) checksum that takes nested types into account (see
:ref:`Checksums API reference <checksums_api>`).


.. rubric:: Functions

The checksum scheme is also used to compute checksums for bound functions - this allows alkymi to check whether a bound
function has been changed in-between evaluations, resulting in the need for a re-evaluation of the recipe associated
with that particular bound function (and subsequent recipes that depend on it). When computing a function checksum,
alkymi takes the following into account:

* The bytecode of the function.
* Constants in the function body - these can be list comprehensions etc. The checksum for these will be computed
  recursively.
* Other functions and closures referenced by the function - these will be checksummed recursively.

This means that changing the contents of a function (or variables/functions referenced by a function), will result in
the checksum changing - alkymi will pick this up and mark the associated recipe as dirty (see :ref:`execution`).

Finally, note that **globals are ignored** in the checksumming process. Changing a global referenced by a bound function
will not result in the function being marked dirty.


.. _checksums_external_files:

.. rubric:: External Files

To interface with the filesystem outside of alkymi's internal cache, alkymi uses the
`pathlib.Path <https://docs.python.org/3/library/pathlib.html#pathlib.Path>`_ type. Because external files live outside
of the alkymi cache, alkymi can't know for sure if they've been changed by other processes in between evaluations. Thus,
the hashing scheme for ``Path`` instances will compute checksums for the binary contents of the file that a ``Path``
points to (if one such exists).

For external directories pointed to by ``Path`` instances, alkymi will simply treat the
``Path`` as a string - this means that alkymi won't pick up changes to files in a directory automatically, unless the
files are referenced explicitly (either by returning ``Path`` objects from a recipe, or using one of the built-in recipe
generators (see :ref:`built_in_recipes`) to bring the files into the alkymi pipeline.


.. rubric:: Custom Classes

For user-defined classes, alkymi currently uses a fallback to pickling and computing a checksum based on the resulting
binary representation.
