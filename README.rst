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
    
To use the `Tornado <http://tornadoweb.org>`_ based tools::

    pip install pycurl
    pip install -e git://github.com/facebook/tornado.git@master#egg=tornado

*Note:* Tornado uses `pycurl`, which currently does install correctly on a Mac using a
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

log_replay
----------



