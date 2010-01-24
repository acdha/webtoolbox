.. program:: tornado_bench
.. _tornado_bench:

tornado_bench
=============

:synopsis: Server crushing URL retriever

A command-line utility which accepts a list of URLs and retrieves them as
quickly as possible. Most of the functionality is provided by
:class:`webtoolbox.clients.Retriever`, which uses Tornado's non-blocking
``pycurl``-based HTTP client and delivers pretty high performance (thousands
of requests per second on my laptop).

.. cmdoption:: --help

   Display all available options and full help

.. cmdoption:: --random

   Randomize the list of URLs before processing

.. cmdoption:: --repeat=COUNT

   Repeat the entire list of URLs COUNT times
