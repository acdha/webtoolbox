# encoding: utf-8
"""
HTTP clients designed for easy tool building
"""


from urlparse import urlparse, urlunparse, urldefrag
from collections import defaultdict, deque

import logging
import re
import time
import sys

try:
    import ipdb as pdb
except ImportError:
    import pdb

from requests import async, session
import chardet
import lxml.html


#: Light-weight class used for reporting purposes
class URLStatus(object):
    code = None
    time = None

    #: Referrers list will be populated as we encounter them:
    referrers = set()
    #: Link list will be populated during the link walk stage:
    links = set()


class Spider(object):
    """
    Retriever-based Spider

    Starts with an initial list of URLs and crawls them asynchronously,
    providing results to :attr:`header_processors`, :attr:`html_processors` and
    :attr:`tree_processors` which implement additional functionality.

    :ref:`check_site` demonstrates the HTML processor feature to report HTML
    validation errors from pytidylib.
    """
    #: Logger used to report progress & errors
    log = None

    #: Queue containing requests which have not yet been processed:
    request_queue = deque()
    response_processors = list()

    #: This will be automatically populated from the inital batch of URLs
    # passed to :meth:`run` and will be used to determine whether to follow
    # links or simply record them.
    allowed_hosts = set()

    #: This is the default time in seconds which we'll wait to receive a response:
    default_request_timeout = 15

    #: This flag controls whether we'll follow redirects to pages which are
    # not in allowed_hosts. It defaults to off to avoid hammering third-party
    # servers but you might want to check them for reporting purposes:
    follow_offsite_redirects = False

    #: All urls processed by this spider as a URL-keyed list of :class:URLStatus elements
    site_structure = defaultdict(URLStatus)
    url_history = set()

    #: URLs whose path matches this regular expression won't be followed:
    skip_link_re = re.compile("^$")

    #: If true, don't retrieve media files (i.e. <img>, <object>, <embed>, etc.)
    skip_media = False
    #: If true, don't process non-media components (i.e. stylesheets or CSS)
    skip_resources = False

    #: Header processors will be called with (URL, HTTP Headers)
    header_processors = list()

    #: HTML processors will be called with unprocessed HTML as a UTF-8 string
    #  processors can return a string to *REPLACE* the provided HTML for all
    #  subsequent processors, including *ALL* tree processors
    html_processors = list()

    #: Tree processors will be called with the full lxml tree, which can be
    # modified to affect subsequent tree processors. Caution is advised!
    tree_processors = list()

    # Used to extract the charset for HTML responses:
    HTTP_CONTENT_TYPE_CHARSET_RE = re.compile("text/html;.*charset=(?P<charset>[^ ]+)", re.IGNORECASE)
    # Used to sniff for XML preambles:
    XML_CHARSET_PREAMBLE_RE = re.compile('^<\?xml[^>]+encoding="(?P<charset>[^"]+)"', re.IGNORECASE)

    # Based on http://stackoverflow.com/questions/92438/stripping-non-printable-characters-from-a-string-in-python
    #
    # We omit chars 9-13 (tab, newline, vertical tab, form feed, return) and
    # 32 (space) to avoid clogging our reports with warnings about common,
    # non-problematic codes
    CONTROL_CHAR_RE = re.compile('[%s]' % "".join(re.escape(unichr(c)) for c in range(0, 8) + range(14, 31) + range(127, 160)))

    redirect_map = {}

    def __init__(self, log_name="Spider", debug=False,
                 default_request_timeout=15,
                 max_simultaneous_connections=6, **kwargs):
        """Create a new Spider, optionally with a custom logging name"""
        super(Spider, self).__init__(**kwargs)

        self.log = logging.getLogger(log_name)
        self.debug = debug

        self.queued = 0
        self.processed = 0
        self.errors = 0

        self.default_request_timeout = default_request_timeout
        self.max_simultaneous_connections = max_simultaneous_connections

        self.session = session(headers={"User-Agent": "https://github.com/acdha/webtoolbox"},
                               config={'keep_alive': True, 'decode_unicode': False},
                               hooks={'pre_request': self.process_request,
                                      'response': self.process_response},
                               timeout=self.default_request_timeout)

        self.response_processors.append(self.process_full_response)

    @property
    def completed(self):
        print self.processed, self.queued
        return self.processed == self.queued

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

        while self.queued > self.processed:
            async.map(self.request_queue,
                      size=self.max_simultaneous_connections)

    def queue(self, url, **kwargs):
        """Add a URL to the queue to be retrieved"""

        if url in self.url_history:
            return

        self.url_history.add(url)

        req = async.get(url, session=self.session,
                        timeout=kwargs.pop("timeout", self.default_request_timeout),
                        **kwargs)

        self.request_queue.append(req)

        self.queued += 1

    def guess_charset(self, response):
        """
        Does the ugly business of attempting to figure out how to decode the
        response to a unicode string
        """
        url = response.url

        # Look for a specific pre-amble:
        xml_sniff = self.XML_CHARSET_PREAMBLE_RE.match(response.content)

        if xml_sniff:
            charset = xml_sniff.group("charset")
            self.log.debug("%s: processing body as document-specified charset=%s", url, charset)
            return charset

        # Attempt to parse the content_type info:
        m = self.HTTP_CONTENT_TYPE_CHARSET_RE.match(response.headers["Content-Type"])

        if m:
            charset = m.group("charset")
            self.log.debug("%s: processing body as header-specified charset=%s", url, charset)
            return charset

        # TODO: Should this be reported as a warning re:poor server config?
        # Looks like we'll do it the slow way:
        det = chardet.detect(response.content)
        self.log.info("%s: processing body as detected charset=%s (confidence=%0.1f)", url, det['encoding'], det['confidence'])
        return det['encoding']

    def process_request(self, request):
        request.start_time = time.time()

    def process_response(self, response):
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

        self.processed += 1

        request = response.request
        response.elapsed_time = time.time() - request.start_time

        self.log.info("Retrieved %s (elapsed=%0.2f, status=%s)", request.url,
                      response.elapsed_time, response.status_code)

        if not response.ok:
            self.errors += 1

            # TODO: Replace this by passing extra= to logging & formatting appropriately
            if "Referer" in response.request.headers:
                self.log.error("Unable to retrieve %s (referer=%s) HTTP %d:  %s", request.url,
                               response.request.headers['Referer'], response.status_code, response.error)
            else:
                self.log.error("Unable to retrieve %s HTTP %d: %s", request.url,
                               response.status_code, response.error)
        else:
            for p in self.response_processors:
                try:
                    p(request, response)
                except Exception as exc:
                    tb = sys.exc_info()[2]
                    self.log.error("Error processing response from %s: %s", request.url, exc, exc_info=True)

                    if self.debug:
                        pdb.post_mortem(tb)

    def process_full_response(self, request, response):
        url = response.url

        # These will be used for new requests based on this page's links:
        new_req_headers = {
            "Referer": url
        }

        # If follow_redirects=False, our effective_url won't be automatically updated:
        if response.status_code in (301, 302):
            url = response.headers['Location']
            self.redirect_map[request.url] = url

            assert not url in self.redirect_map or self.redirect_map[url] != request.url, "Circular redirect: %s %s" % (url, self.redirect_map[url])

        parsed_url = urlparse(url)

        self.site_structure[url].status_code = response.status_code
        self.site_structure[url].time = response.elapsed_time

        if not parsed_url.scheme == "http":
            self.log.error("Skipping %s: can't handle non HTTP URLs", url)
            return

        if url != request.url:
            if not parsed_url.netloc or parsed_url.netloc in self.allowed_hosts:
                self.queue(url, headers=new_req_headers)
            elif self.follow_offsite_redirects:
                self.queue(url, headers=new_req_headers)
            else:
                self.log.info("Not following external redirect from %s to %s", request.url, url)
            return

        assert url == request.url

        content_length = int(response.headers.get('Content-Length', -1))

        # TODO: In theory these should be identical but things like gzip
        # transfer encoding are non-trivial to handle with the information we
        # have visible at this point. We'll look for incomplete responses and
        # hope that requests does the right thing and raise an error if we get
        # partial/bogus encoding.
        if content_length > -1 and len(response.content) < content_length:
            self.log.warning("%s: possible partial content: Content-Length = %d, body length = %d",
                             url, content_length, len(response.content))

        content_type = response.headers.get('Content-Type', None)

        if not content_type:
            self.log.warning("%s: no Content-Type‽", url)
            return

        if not content_type.startswith("text/html"):
            # TODO: Add media processors or simply a generic response processor?
            self.log.info("Done processing %s resource %s", content_type, url)
            return

        for p in self.header_processors:
            try:
                p(url, response.headers)
            except:
                self.log.exception("Header processor %s: unhandled exception", p)
                raise

        charset = self.guess_charset(response) or "latin-1"

        if isinstance(response.content, unicode):
            html = response.content
        else:
            try:
                html = unicode(response.content, charset)
            except UnicodeDecodeError, e:
                self.log.error("%s: skipping page - unable to decode body as %s: %s", url, charset, e)
                return

        html, junk_count = self.CONTROL_CHAR_RE.subn(' ', html)
        if junk_count:
            self.log.warning("%s: stripped %d non-printable control characters", url, junk_count)

        for p in self.html_processors:
            try:
                html = p(url, html) or html
            except:
                self.log.exception("HTML processor %s: unhandled exception", p)
                raise

        self.log.debug("%s: Parsing %d bytes of HTML", url, len(html))

        try:
            tree = lxml.html.document_fromstring(html)
        except ValueError, e:
            self.log.warning("%s: aborting processing due to lxml parse error: %s", url, e)
            return

        self.log.debug("%s: Processing links", url)

        tree.make_links_absolute(url, resolve_base_href=True)

        for element, attribute, link, pos in tree.iterlinks():
            link_p = urlparse(link)

            # Reconstruct the URL to remove fragments and normalize alternate
            # forms which are equivalent. e.g. http://example.com/foo? and
            # http://example.com/foo are considered to be the same

            # Avoid wasting time reprocessing anchors, which are a browser-level behaviour:
            normalized_url = urldefrag(urlunparse((
             link_p.scheme, link_p.netloc, link_p.path, link_p.params, link_p.query, ""
            )))[0]

            self.site_structure[url].links.add(normalized_url)

            if link_p.netloc and not link_p.netloc in self.allowed_hosts:
                self.log.debug("Skipping external resource: %s", link)
                continue

            self.site_structure[normalized_url].referrers.add(url)

            if self.skip_link_re.match(link_p.path):
                self.log.debug("Link matched skip_link_re - skipping %s", link)
                continue

            if not link_p.scheme.startswith("http"):
                self.log.debug("Skipping non-HTTP link: %s", link)
                continue

            if element.tag in ('a', 'frame', 'iframe'):
                self.queue(normalized_url, headers=new_req_headers)
            elif element.tag in ('link', 'script'):
                if not self.skip_resources:
                    self.queue(normalized_url, headers=new_req_headers)
            else:
                if not self.skip_media:
                    self.queue(normalized_url, headers=new_req_headers)

        for p in self.tree_processors:
            try:
                p(url, tree)
            except:
                self.log.exception("Tree processor %s: unhandled exception", p)
                raise
