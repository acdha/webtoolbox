#!/usr/bin/env python
# encoding: utf-8
"""Download many URLs in parallel"""

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import logging
import os
import re
import sys
import urllib
from multiprocessing.pool import ThreadPool
from warnings import warn

import requests

if sys.version_info < (2, 7, 9):
    print('This script requires Python >= 2.7.9 for the PEP-466 SSL improvements', file=sys.stderr)
    sys.exit(123)

DEFAULT_CHUNK_SIZE = 1024 * 1024


def retrieve_file(url, filename, chunk_size=DEFAULT_CHUNK_SIZE, remove_on_error=True):
    """Save the contents of a URL to the provided filename"""

    logging.debug('Retrieving %s to %s', url, filename)

    resp = requests.get(url, stream=True)
    resp.raise_for_status()

    if filename is None:
        filename = '/dev/null'

    try:
        with open(filename, 'wb') as f:
            for chunk in resp.iter_content(chunk_size=chunk_size):
                f.write(chunk)

    except Exception as exc:
        logging.error('Error while retrieving %s to %s: %s', url, filename, exc, exc_info=True)

        if remove_on_error:
            os.unlink(filename)

        raise

    resp.close()

    return resp.status_code, resp.elapsed.total_seconds(), url, filename


def safe_retrieve_file(args):
    # Trivial wrapper to add logging around downloads and deal with the Pool API
    # not supporting multiple arguments:

    url, filename = args

    try:
        return retrieve_file(url, filename)
    except Exception as exc:
        logging.error('Unable to retrieve %s: %s', url, exc)


def fetch_urls(url_iterator, download_root=None, concurrency=2, chunk_size=DEFAULT_CHUNK_SIZE):
    pool = ThreadPool(processes=concurrency)

    if download_root is not None:
        iterable = ((i, os.path.join(download_root, j)) for i, j in url_iterator)
    else:
        iterable = ((i, None) for i, j in url_iterator)

    for i in pool.imap_unordered(safe_retrieve_file, iterable):
        if not i:
            continue

        status_code, elapsed_time, url, local_filename = i

        logging.info('HTTP %d (%0.2fs) %s', status_code, elapsed_time, url)

    pool.close()
    pool.join()


def configure_logging(verbosity=0):
    if verbosity > 1:
        desired_level = logging.DEBUG
    elif verbosity > 0:
        desired_level = logging.INFO
    else:
        desired_level = logging.WARNING

    try:
        import coloredlogs
        coloredlogs.install(level=desired_level, reconfigure=True)
        return
    except ImportError:
        pass

    if verbosity:
        stdout_handler = logging.StreamHandler(stream=sys.stdout)
        stdout_handler.setLevel(desired_level)
        logging.getLogger().addHandler(stdout_handler)
    else:
        logging.basicConfig(level=logging.WARNING, stream=sys.stderr)


def stdin_url_iterator():
    LOG_LINE_RE = re.compile(r'^(?P<URL>\S+)\s*(?P<FILENAME>|\S+)\s*$')
    for line in sys.stdin:
        m = LOG_LINE_RE.match(line)
        if not m:
            warn('Received malformed line: %s' % line)
            continue
        else:
            url, filename = m.groups()

            if not filename:
                filename = urllib.quote(url)

            yield url, filename


if __name__ == '__main__':
    from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter

    parser = ArgumentParser(description=__doc__.strip(),
                            formatter_class=ArgumentDefaultsHelpFormatter)

    parser.add_argument('--verbose', '-v', action='count', default=0)

    parser.add_argument('--download-root',
                        help='Local filesystem path to files under')

    dl_opts = parser.add_argument_group('Downloader Configuration')

    dl_opts.add_argument('--chunk-size', type=int, default=DEFAULT_CHUNK_SIZE,
                         help='Set chunk size for HTTP downloads')

    dl_opts.add_argument('--concurrency', type=int, default=8,
                         help='Number of concurrent requests')

    args = parser.parse_args()

    if args.download_root and not os.path.isdir(args.download_root):
        parser.error('Invalid storage location: %s' % args.download_root)

    configure_logging(args.verbose)

    fetch_urls(stdin_url_iterator(), args.download_root,
               chunk_size=args.chunk_size, concurrency=args.concurrency)
