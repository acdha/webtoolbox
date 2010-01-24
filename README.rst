Prequisites
===========

This project assumes the use of pip, virtualenv and `virtualenvwrapper
<http://www.doughellmann.com/projects/virtualenvwrapper/>`_. If you don't
already have them::

    easy_install pip
    pip install virtualenv virtualenvwrapper
    . virtualenvwrapper_bashrc
    mkdir ~/.virtualenvs

Once they're setup you'll want to create a virtualenv::

    mkvirtualenv webtoolbox
    add2virtualenv /path/to/webtoolbox

Now you're ready to install our prerequisites::

    pip install -r requirements.pip

*Note:* Tornado uses ``pycurl``, which may or may not install correctly on a
Mac using a simple ``pip install pycurl``. If you encounter problems follow the
instructions in the Tornado documentation.

To use the `redbot <http://mnot.github.com/redbot/>`_-based tools. This is
complicated by the fact that redbot hasn't been turned into an importable
module yet::

    pip install -e git://github.com/mnot/nbhttp.git@master#egg=nbhttp
    git clone http://github.com/mnot/redbot
    add2virtualenv redbot/src

The Tools
=========

check_site
----------

A site validator which uses ``webclient.clients.Spider`` to process an entire
site and checking for bad links, 404s, and optionally HTML validation. It
generates either text or HTML reports and can be used to generate lists of
site URLs for use with load-testing tools like ``tornado_bench`` or
``wk_bench``.

Run ``check_site.py --help`` to see the available options

red_spider
----------

`Mark Nottingham <http://mnot.net/>`_ released `redbot`_ - a modern replacement
for the classic `cacheability <http://www.mnot.net/cacheability/>`_ tester.
I've been using it at work to audit website performance before releases since
proper HTTP caching makes an enormous difference in perceived site
performance.

redbot is a focused tool and provides a great deal of detail about at most one
page and, optionally, its resources. I wanted to expand the scope to testing
an entire site and performing content validation and created `red_spider.py`
which allows you to perform all of those checks by spidering an entire site,
receiving a nice HTML report and, optionally, also validating page contents as
well.

Run ``red_spider.py --help`` to see the available options. Key features
include the ability to skip media and save lists of URLs for use with tools
like ``wk_bench`` or ``tornado_bench``.

log_replay
----------

If you need to replace webserver log files at something approximating
realtime, ``log_replay`` is your friend. It uses Tornado's non-blocking HTTP
client to fetch all of the URLs but will sleep any time it's too far ahead
of the simulated virtual time.

Run ``log_replay.py --help`` to see the available options

tornado_bench
-------------

Also uses Tornado's non-blocking HTTP client, this program simply takes a big
list of URLs and simply retrieves them as quickly as possible.

Run ``tornado_bench.py --help`` to see the available options

wk_bench
--------

Mac OS X-specific tool which uses PyObjC to load pages in WebKit. Takes URLs
on the command-line or in a separate file and runs through them as quickly as
possible, measuring the time it takes from beginning the request until the
browser fires the ``didFinishLoadForFrame`` event, which includes things like
image loading, Flash, JavaScript, etc. for measuring user-perceptible
page-load performance.

Run ``wk_bench.py --help`` to see the available options