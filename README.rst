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

To use the `Tornado <http://tornadoweb.org>`_ based tools::

    pip install pycurl
    pip install tornado

*Note:* Tornado uses `pycurl`, which should install correctly on a Mac using a
simple `pip install pycurl`. If you encounter problems follow the instructions
in the Tornado documentation to install pycurl 7.16.2.1 instead.

To use the `redbot <http://mnot.github.com/redbot/>`_-based tools. This is
complicated by the fact that redbot hasn't been turned into an importable
module yet::

    pip install -e git://github.com/mnot/nbhttp.git@master#egg=nbhttp
    git clone http://github.com/mnot/redbot
    add2virtualenv redbot/src

The Tools
=========

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

Run `red_spider.py --help` to see the available options. Key features include
the ability to skip media and save lists of URLs for use with tools like
`wk-bench` or `tornado-bench`.

log_replay
----------

If you need to replace webserver log files at something approximating
realtime, `log_replay` is your friend. It uses Tornado's non-blocking HTTP
client (based on pycurl - at some point it would be good to refactor down to
just that) to fetch all of the URLs but will sleep any time it's too far ahead
of the simulated virtual time.

Run `log_replay.py --help` to see the available options

tornado-bench
-------------

Also uses Tornado's non-blocking HTTP client, this program simply takes a big
list of URLs and simply retrieves them as quickly as possible.

Run `tornado-bench.py --help` to see the available options

wk-bench
--------

Mac OS X-specific tool which uses PyObjC to load pages in WebKit. Takes URLs
on the command-line or in a separate file and runs through them as quickly as
possible, measuring the time it takes from beginning the request until the
browser fires the `didFinishLoadForFrame` event, which includes things like
image loading, Flash, JavaScript, etc. for measuring user-perceptible
page-load performance.

Run `wk-bench.py --help` to see the available options