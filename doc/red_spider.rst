.. program:: red_spider
.. _red_spider:

red_spider
==========

:synopis: Site validation spider based on ``redbot``

`Mark Nottingham <http://mnot.net/>`_ released `redbot <http://mnot.github.com/redbot/>`_ 
- a modern replacement for the classic `cacheability <http://www.mnot.net/cacheability/>`_ 
tester. I've been using it at work to audit website performance before
releases since proper HTTP caching makes an enormous difference in perceived
site performance.

redbot is a focused tool and provides a great deal of detail about at most one
page and, optionally, its resources. I wanted to expand the scope to testing
an entire site and performing content validation and created :program:`red_spider.py`
which allows you to perform all of those checks by spidering an entire site,
receiving a nice HTML report and, optionally, also validating page contents as
well.

.. cmdoption:: --help

    Display all available options and full help

.. cmdoption::  --format=REPORT_FORMAT

    Generate the report as HTML or text

.. cmdoption:: --report=REPORT_FILE

    Save report to a file instead of stdout

.. cmdoption::    --validate-html       

    Validate HTML using tidylib

.. cmdoption::    --skip-media          

    Skip media files: <img>, <object>, etc.

.. cmdoption::    --skip-resources      

    Skip resources: <script>, <link>

.. cmdoption::    --skip-link-re=SKIP_LINK_RE

    Skip links whose URL matches the specified regular
    expression

.. cmdoption::    --save-page-list=PAGE_LIST

    Save a list of URLs for HTML pages in the specified
    file

.. cmdoption::    --save-resource-list=RESOURCE_LIST

    Save a list of URLs for pages resources in the
    specified file

.. cmdoption:: --log=LOG_FILE

    Specify a location other than stderr

.. cmdoption:: -v
.. cmdoption:: --verbosity       

Increase the amount of information displayed or logged
