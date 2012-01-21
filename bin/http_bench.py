#!/usr/bin/env python
# encoding: utf-8
u"""
High-performance server-crushing tool

Usage:

http_bench.py url_or_file [url_or_file2 …]
"""

import logging
import optparse
import os
import random
import sys
import time

try:
    from requests import async, session
except ImportError:
    print >>sys.stderr, "Unable to import requests.async. Do you have requests and gevent installed?"
    raise

__version__ = "0.2"


class StatsProcessor(object):
    total = 0
    errors = 0
    good_urls = set()
    bad_urls = set()

    def __call__(self, response):
        self.total += 1

        if not response.ok:
            self.errors += 1
            self.bad_urls.add(response.request.url)
        else:
            self.good_urls.add(response.request.url)


def main(argv=None):
    cmdparser = optparse.OptionParser(__doc__.strip(), version="http_bench %s" % __version__)
    cmdparser.add_option("--verbosity", "-v", "--verbose", action="count",
                         help="Display more progress information")
    cmdparser.add_option("--save-bad-urls", type="string",
                         help="Save all URLs which returned errors to the provided filename")
    cmdparser.add_option("--save-good-urls", type="string",
                         help="Save all URLs which did not return errors to the provided filename")
    cmdparser.add_option("--max-requests", type="int", default=8,
                         help="Set the number of simultaneous requests")
    cmdparser.add_option("--repeat", type="int", default=1,
                         help="Retrieve the provided URLs n times")
    cmdparser.add_option("--random", action="store_true", default=False,
                         help="Randomize the URLs before processing")
    (options, args) = cmdparser.parse_args()

    if not args:
        cmdparser.error("You must provide at least one URL to retrieve!")

    if options.verbosity > 1:
        log_level = logging.DEBUG
    elif options.verbosity:
        log_level = logging.INFO
    else:
        log_level = logging.WARNING

    logging.basicConfig(format="%(asctime)s [%(levelname)s]: %(message)s",
                        level=log_level)

    stats = StatsProcessor()

    urls = list()

    for arg in args:
        # Is it a file?
        if os.path.exists(arg):
            urls.extend(l.strip() for l in file(sys.argv[1]))
        else:
            urls.append(arg)

    if options.repeat > 1:
        urls = urls * options.repeat

    if options.random:
        random.shuffle(urls)

    # Now that we're done changing it, we'll load the URL queue into the fetcher:
    start_time = time.time()

    with session(hooks={"response": stats}, config={"max_redirects": 1}) as s:
        async.map([async.get(u, session=s) for u in urls], size=options.max_requests)

    elapsed = time.time() - start_time

    print "Retrieved {total} URLs ({bad} errors) in {elapsed:0.2f} seconds ({rate:0.1f} req/s)".format(
        bad=stats.errors, elapsed=elapsed, rate=stats.total / elapsed, total=stats.total)

    if options.save_bad_urls:
        with open(options.save_bad_urls, "wb") as f:
            f.write("\n".join(stats.bad_urls))

    if options.save_good_urls:
        with open(options.save_good_urls, "w") as f:
            f.write("\n".join(stats.good_urls))

if __name__ == "__main__":
    sys.exit(main())
