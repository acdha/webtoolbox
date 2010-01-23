Installation
============

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