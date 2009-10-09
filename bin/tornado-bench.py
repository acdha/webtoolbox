#!/usr/bin/env python
# encoding: utf-8
"""
tornado_bench.py

High-performance server-crushing tool
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

    def __init__(self):
        from tornado import ioloop, httpclient

        self.http_client = httpclient.AsyncHTTPClient(max_simultaneous_connections=6)
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
    cmdparser.add_option("--verbosity", "-v", "--verbose", default=0, type="int", action="count", help="Display more progress information")
    cmdparser.add_option("--save-bad-urls", type="string", help="Save all URLs which returned errors to the provided filename")
    cmdparser.add_option("--save-good-urls", type="string", help="Save all URLs which did not return errors to the provided filename")
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
    
    fetcher = URLFetcher()

    for arg in args:
        # Is it a file?
        if os.path.exists(arg):
            fetcher.load([l.strip() for l in file(sys.argv[1])])
        else:
            # TODO: Validate URLs before adding them
            fetcher.load(arg)

    start_time = time.clock()
    fetcher.run()
    end_time = time.clock()
    
    logging.info("Retrieved %d URLs in %s seconds (%d errors)", 
        fetcher.total, 
        end_time - start_time, 
        len(fetcher.bad_urls)
    )
    
    if options.save_bad_urls:
        open(options.save_bad_urls, "w").write("\n".join(fetcher.bad_urls))

    if options.save_good_urls:
        open(options.save_good_urls, "w").write("\n".join(fetcher.good_urls))


if __name__ == "__main__":
    sys.exit(main())
