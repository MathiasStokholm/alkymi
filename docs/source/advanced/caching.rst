.. _caching:

Caching
=======

A key feature for avoiding unnecessary work is the ability to retain data between executions of your program. Whenever
a bound function has been evaluated by alkymi, the resulting outputs will be cached to disk (if enabled, see
:ref:`configuration`).

In order to enable this feature for arbitrary return values, alkymi uses a combination of JSON and files to describe the
outputs of a bound function. Each ``Recipe`` instance will save its outputs (and checksums) to an ``.alkymi_cache``
directory in the current working directory [#cache_dir]_.

By default, outputs are serialized into a JSON representation (see :ref:`serialization`). For instance, a list of
strings will be stored directly in the ``cache.json`` file inside the alkymi cache. However, it is often the case that
complex objects can't be serialized directly to JSON. To work around this, alkymi applies special handling whenever it
encounters a complex object (e.g. a ``numpy.ndarray``). Such complex objects are serialized to files inside alkymi's
cache, and then referenced in the JSON document using a simple string-token scheme [#tokens]_. This allows the matching
deserialization code to read the complex object back from the associated file.

By combining the file and JSON representations, alkymi is able to support nested and complex types, such as lists and
dictionaries with numpy arrays as keys. It should be noted that alkymi's cache is meant to be a private implementation,
and might change at some point in the future (e.g. to a database).

.. rubric:: Lazy Deserialization

When loading data from the cache, alkymi will initially only read the data stored in the JSON document. If a complex
value has been stored in a separate cache file, that file will only be read when the value is actually requested. This
means that checking the status of an alkymi pipeline can be done without loading expensive data (such as images) from
disk, relying only on checksums and alkymi's cache.

.. [#cache_dir] The location of the cache directory can be set using the AlkymiConfig singleton, see
   :ref:`configuration`.
.. [#tokens] This scheme is likely to change to something less brittle in the future.
