#!/usr/bin/env python

import os
import glob
from setuptools import setup, find_packages
from setuptools.dist import Distribution

setup(name='WebToolbox',
    version="0.1",
    description='Framework and tools for working with web servers',
    author='Chris Adams',
    author_email='chris@improbable.org',
    url='http://acdha.github.com/webtoolbox/',
    license='BSD License',
    platforms=['OS Independent'],
    classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Topic :: Internet :: WWW/HTTP :: Dynamic Content',
        'Topic :: Software Development',
        'Topic :: Software Development :: Libraries :: Application Frameworks',
    ],
    requires=[
        'lxml',
        'pycurl (>=7.16.4)',
        'tornado',
        'html5lib',
        'chardet'
    ],
    packages=['webtoolbox'],
    include_package_data=True,
    zip_safe=False,
    scripts = glob.glob('bin/*.py'),
)

