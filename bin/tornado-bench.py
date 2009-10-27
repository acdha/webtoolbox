#!/usr/bin/env python
# encoding: utf-8
"""
High-performance server-crushing tool

Usage:

tornado-bench.py 
"""
import optparse
import logging
import sys
import os
import time
from collections import deque

__version__ = "0.1"

class URLFetcher(object):    
    total     = 0
    completed = 0
    errors    = 0
    
    good_urls = deque()
    bad_urls  = deque()

    ioloop    = None

    def __init__(self, max_clients=10, max_connections=6):
        from tornado import ioloop, httpclient

        self.http_client = httpclient.AsyncHTTPClient(
            max_simultaneous_connections=max_connections,
            max_clients=max_clients,
        )
        
        self.ioloop = ioloop.IOLoop.instance()
        
    def run(self):
        self.ioloop.start()

    def load(self, urls):
        """Queue up a list of URLs to retrieve"""
        if not isinstance(urls, list):
            urls = list(urls)

        self.total += len(urls)
        for u in urls:
            self.http_client.fetch(u, self.response_handler)

    def response_handler(self, response):
        url = response.request.url
        
        if response.error:
            logging.info("Unable to retrieve %s: %s", url, response.error)
            self.bad_urls.append(url)
        else:
            self.good_urls.append(url)
    
        self.completed += 1
    
        if self.completed >= self.total:
            logging.info("Finished")
            self.ioloop.stop()

def main(argv=None):
    try:
        import tornado
    except ImportError, e:
        logging.critical("Couldn't import Tornado: %s", e)
        sys.exit(99)

    cmdparser = optparse.OptionParser(__doc__.strip(), version="tornado-bench %s" % __version__)
    cmdparser.add_option("--verbosity", "-v", "--verbose", action="count", help="Display more progress information")
    cmdparser.add_option("--save-bad-urls", type="string", help="Save all URLs which returned errors to the provided filename")
    cmdparser.add_option("--save-good-urls", type="string", help="Save all URLs which did not return errors to the provided filename")
    cmdparser.add_option("--max-connections", type="int", default=8, help="Set the number of simultaneous connections")
    cmdparser.add_option("--max-clients", type="int", default=10, help="Set the number of simultaneous clients")
    (options, args) = cmdparser.parse_args()

    if not args:
        cmdparser.error("You must provide at least one URL to retrieve!")

    if options.verbosity > 1:
        log_level = logging.DEBUG
    elif options.verbosity:
        log_level = logging.INFO
    else:
        log_level = logging.WARNING

    logging.basicConfig(
        format = "%(asctime)s [%(levelname)s]: %(message)s",
        level  = log_level
    )
    
    fetcher = URLFetcher(max_connections=options.max_connections, max_clients=options.max_clients)

    for arg in args:
        # Is it a file?
        if os.path.exists(arg):
            fetcher.load([l.strip() for l in file(sys.argv[1])])
        else:
            # TODO: Validate URLs before adding them
            fetcher.load(arg)

    start_time = time.time()
    fetcher.run()
    elapsed = time.time() - start_time
    
    print "Retrieved {total} URLs ({bad} errors) in {elapsed:0.2f} seconds ({rate:0.1f} req/s)".format(
        total=fetcher.total, 
        elapsed=elapsed, 
        rate=fetcher.total / elapsed,
        bad=len(fetcher.bad_urls)
    )
    
    if options.save_bad_urls:
        open(options.save_bad_urls, "w").write("\n".join(fetcher.bad_urls))

    if options.save_good_urls:
        open(options.save_good_urls, "w").write("\n".join(fetcher.good_urls))


if __name__ == "__main__":
    sys.exit(main())
