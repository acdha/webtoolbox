.. program:: check_site
.. _check_site:

check_site
==========
:synopsis: Site validation spider

A site validator which uses :class:`webtoolbox.clients.Spider` to process an entire
site and checking for bad links, 404s, and optionally HTML validation. It
generates either text or HTML reports and can be used to generate lists of
site URLs for use with load-testing tools like :ref:`http_bench` or
:ref:`wk_bench`.

.. cmdoption:: --help

   Display all available options and full help

.. cmdoption:: -v
.. cmdoption:: --verbosity

    Increase the amount of information displayed or logged

.. cmdoption:: --validate-html

   Process all HTML using `HTML Tidy <http://tidy.sourceforge.net>`_ and
   report any validation errors

.. cmdoption::  --format=REPORT_FORMAT

    Generate the report as HTML or text

.. cmdoption:: --report=REPORT_FILE

    Save report to a file instead of stdout

.. cmdoption::    --skip-media

    Skip media files: <img>, <object>, etc.

.. cmdoption::    --skip-resources

    Skip resources: <script>, <link>

.. cmdoption::    --skip-link-re=SKIP_LINK_RE

    Skip links whose URL matches the specified regular
    expression

.. cmdoption::    --save-page-list=PAGE_LIST

    Save a list of URLs for HTML pages in the specified
    file for use with a tool like :ref:`http_bench` or :ref:`wk_bench`

.. cmdoption::    --save-resource-list=RESOURCE_LIST

    Save a list of URLs for pages resources in the
    specified file

.. cmdoption:: --log=LOG_FILE

    Specify a location other than stderr

.. cmdoption:: --simultaneous-connections=2

    Adjust the number of simultaneous connections which will be opened to the
    server
