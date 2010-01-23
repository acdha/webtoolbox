import logging

from tornado import httpclient
from collections import deque


class Retriever(object):
    """
    Fast, asynchronous URL retriever
    
    Usage is simple:
        1. Create a Retriever, optionally providing a log_name for logging and
           any of the kwargs accepted by tornado.httpclient.AsyncHTTPClient

        2. Add request processor callbacks to retriever.response_processors.
           Each will be called with args=(request, response)

        3. Load one or more URLs using retriever.queue_urls (your response
           processors may add more as desired)

        4. Call retriever.run(), which will block until all URLs have been
           processed
    
    """

    # We use these to keep track of when we've finished processing all
    # outstanding requests as there's no actual way to get that using public
    # methods for AsyncHTTPClient or ioloop:
    queued = 0
    processed = 0

    queue = deque()

    http_client = None

    response_processors = list()

    log = None

    def __init__(self, log_name="Retriever", **kwargs):
        self.http_client = httpclient.AsyncHTTPClient(**kwargs)
        self.log = logging.getLogger(log_name)

    def run(self):
        self.log.info("Starting IOLoop with %d URLs", len(self.queue))
        self.http_client.io_loop.start()
        self.log.info("Completed IOLoop after %d URLs", len(self.queue))

    def queue_urls(self, urls):
        """Queue up a list of URLs to retrieve"""

        if not isinstance(urls, list):
            urls = [urls]

        for u in urls:
            self.http_client.fetch(u, self.response_handler)

        self.queued += len(urls)

    def response_handler(self, response):
        self.processed += 1
        
        self.log.info("Retrieved %s (elapsed=%0.2f, status=%s)", response.request.url, response.request_time, response.code)

        for p in self.response_processors:
            p(response.request, response)

        if self.processed == self.queued:
            if self.queue:
                self.log.critical("RESULTS ARE INCOMPLETE: processed == queued == %d but queue = %s", self.processed, self.queue)

            self.http_client.io_loop.stop()
