.. program:: wk_bench
.. _wk_bench:

wk_bench
--------
:synopsis: Benchmark user-perceived page time for a list of URLs using a true WebKit browser

Mac OS X-specific tool which uses `PyObjC <http://pyobjc.sourceforge.net/>`_
to load pages in `WebKit <http://www.webkit.org>`_. Takes URLs on the
command-line or in a separate file and runs through them as quickly as
possible, measuring the time it takes from beginning the request until the
browser fires the ``didFinishLoadForFrame`` event, which includes things like
image loading, Flash, JavaScript, etc. for measuring user-perceptible
page-load performance.

.. cmdoption:: --help

   Display all available options and full help
