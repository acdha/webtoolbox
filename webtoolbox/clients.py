# encoding: utf-8

from urlparse import urlparse, urlunparse, urldefrag

import logging
import re
import time

import lxml.html.html5parser

from tornado import httpclient


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

    http_client = None

    response_processors = list()

    log = None

    def __init__(self, log_name="Retriever", **kwargs):
        self.http_client = httpclient.AsyncHTTPClient(**kwargs)
        self.log = logging.getLogger(log_name)
        
    @property
    def completed(self):
        return self.processed == self.queued

    def run(self):
        self.log.info("Starting IOLoop with %d queued URLs", self.queued)

        start_time = time.time()
        self.http_client.io_loop.start()
        elapsed = time.time() - start_time

        self.log.info("Completed IOLoop after processing %d URLs in %0.2f seconds", self.processed, elapsed)

    def queue(self, url):
        """Queue up a list of URLs to retrieve"""

        self.http_client.fetch(url, self.response_handler)

        self.queued += 1

    def response_handler(self, response):
        self.processed += 1

        self.log.info("Retrieved %s (elapsed=%0.2f, status=%s)", response.request.url, response.request_time, response.code)

        for p in self.response_processors:
            try:
                p(response.request, response)
            except:
                self.log.exception("Aborting due to unhandled exception in processor %s", p)
                self.http_client.io_loop.stop()
                raise

        if self.processed == self.queued:
            self.http_client.io_loop.stop()


class Spider(Retriever):
    """
    Retriever-based Site Crawler
    
    Starts with an initial list of URLs and crawls them asynchronously,
    providing HTML pages to :attr:`html_processors` and
    :attr:`tree_processors` for additional functionality. See
    :ref:`check_site` for an example of this function being used to report
    HTML validation errors from pytidylib.
    """
    #: Logger used to report progress & errors
    log = None

    #: This will be automatically populated from the inital batch of URLs
    # passed to :meth:`run` and will be used to determine whether to follow
    # links or simply record them.
    allowed_hosts = set()

    #: All urls processed by this spider
    urls = set()

    #: URLs whose path matches this regular expression won't be followed:
    skip_link_re = re.compile("^$")

    #: If true, don't retrieve media files (i.e. <img>, <object>, <embed>, etc.)
    skip_media = False
    #: If true, don't process non-media components (i.e. stylesheets or CSS)
    skip_resources = False

    #: HTML processors will be called with unprocessed HTML as a UTF-8 string
    #  processors can return a string to *REPLACE* the provided HTML for all
    #  subsequent processors, including *ALL* tree processors
    html_processors = list()

    #: Tree processors will be called with the full lxml tree, which can be
    # modified to affect subsequent tree processors. Caution is advised!
    tree_processors = list()

    # Used to extract the charset for HTML responses:
    HTTP_CONTENT_TYPE_CHARSET_RE = re.compile("text/html;.*charset=(?P<charset>[^ ]+)", re.IGNORECASE)

    # Based on http://stackoverflow.com/questions/92438/stripping-non-printable-characters-from-a-string-in-python
    # 
    # We omit chars 9-13 (tab, newline, vertical tab, form feed, return) and
    # 32 (space) to avoid clogging our reports with warnings about common,
    # non-problematic codes
    CONTROL_CHAR_RE = re.compile('[%s]' % "".join(re.escape(unichr(c)) for c in range(0, 8) + range(14, 31) + range(127, 160)))

    def __init__(self, log_name="Spider", **kwargs):
        """Create a new Spider, optionally with a custom logging name"""
        super(Spider, self).__init__(**kwargs)

        self.log = logging.getLogger(log_name)

        self.response_processors.append(self.process_page)

    def run(self, urls):
        """
        Start the spider with the provided list of URLs
        
        Block until the spider has crawled the entire site
        """
        for url in urls:
            parsed_url = urlparse(url)

            # We add any hostname specified in the initial run to the list of hostnames we'll spider:
            self.allowed_hosts.add(parsed_url.netloc)

            self.queue(url)

        super(Spider, self).run()

    def queue(self, url):
        """Add a URL to the queue to be retrieved"""
        if not url in self.urls:
            super(Spider, self).queue(url)
            self.urls.add(url)

    def process_page(self, request, response):
        """
        Callback used to process a URL after it's been retrieved
        
        Rough sequence:
            #. Process errors and redirects
            #. Process non-HTML content
            #. Convert retrieved HTML to UTF-8
            #. Process HTML through the defined :attr:`html_processors`
            #. Create an ``lxml`` tree
            #. Convert all links to absolute URLs
            #. Queue any unseen URLs for retrieval
            #. Pass lxml tree to :attr:`tree_processors`
        
        """

        url = request.url

        if response.error:
            self.log.error("Unable to retrieve %s: %s", url, response.error)
            return

        if response.code in (301, 302):
            self.process_redirect(response.effective_url)
            return

        content_type = response.headers.get('Content-Type', None)

        if not content_type:
            self.log.warning("%s: no content type?", url)
            return

        if not content_type.startswith("text/html"):
            self.log.info("Done processing %s resource %s", content_type, url)
            # TODO: Log (url, code, time) for reporting
            return

        # Attempt to parse the content_type info:
        m = self.HTTP_CONTENT_TYPE_CHARSET_RE.match(content_type)

        if m:
            charset = m.group("charset")
        else:
            charset = "latin-1" # Sigh...

        self.log.info("%s: processing body as charset=%s", url, charset)

        html = unicode(response.body, charset)

        html, junk_count = self.CONTROL_CHAR_RE.subn(' ', html)
        if junk_count:
            self.log.warning("%s: stripped %d non-printable control characters", url, junk_count)

        for p in self.html_processors:
            try:
                html = p(url, html) or html
            except:
                logging.exception("HTML processor %s: unhandled exception", p)
                raise

        self.log.debug("%s: Parsing %d bytes of HTML", url, len(html))

        try:
            tree = lxml.html.html5parser.document_fromstring(html, guess_charset=False)
        except ValueError, e:
            self.log.warning("%s: aborting processing due to lxml parse error: %s", url, e)
            import code; code.interact(local=dict(locals().items() + globals().items()))
            return

        self.log.debug("%s: Processing links", url)

        tree.make_links_absolute(url, resolve_base_href=True)

        for element, attribute, link, pos in tree.iterlinks():
            link_p = urlparse(link)

            if link_p.netloc and not link_p.netloc in self.allowed_hosts:
                self.log.debug("Skipping external resource: %s", link)
                continue

            if self.skip_link_re.match(link_p.path):
                self.log.debug("Link matched skip_link_re - skipping %s", link)
                continue

            if not link_p.scheme.startswith("http"):
                self.log.debug("Skipping non-HTTP link: %s", link)
                continue

            # Reconstruct the URL to remove fragments and normalize alternate
            # forms which are equivalent. e.g. http://example.com/foo? and
            # http://example.com/foo are considered to be the same
            normalized_url = urldefrag(urlunparse(link_p))[0]

            if element.tag in ('a', 'frame', 'iframe'):
                self.report.pages.add(normalized_url)
                self.queue(normalized_url)
            if element.tag in ('img', 'object', 'embed'):
                self.report.media.add(link)
                if not self.skip_media:
                    self.queue(normalized_url)
            else:
                self.report.resources.add(link)
                if not self.skip_resources:
                    self.queue(normalized_url)

        for p in self.tree_processors:
            try:
                p(url, tree)
            except:
                logging.exception("Tree processor %s: unhandled exception", p)
                raise
