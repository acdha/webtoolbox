#!/usr/bin/env python
# encoding: utf-8
"""
Replays Apache or IIS log files against other servers

Usage:

%prog --server=mytestserver log1 [log2.gz log3.zip...]

Log files can be compressed with gzip or zip - they'll be silently
decompressed as needed.

BUG: Currently only one IIS log flavor is supported!
"""
import optparse
import logging
import sys
import os
import time
import re
import gzip
import zipfile
import urllib
import datetime
from collections import deque
from functools import partial

__version__ = "0.1"

class LogReplayer(object):
    total          = 0
    completed      = 0
    errors         = 0

    urls           = None
    good_urls      = deque()
    bad_urls       = deque()

    ioloop         = None

    start_time     = None

    _log_generator = None

    # FIXME: This is currently based on IIS log lines like this:
    # date time c-ip cs-username s-ip s-port cs-method cs-uri-stem cs-uri-query sc-status sc-bytes cs-bytes cs(User-Agent) cs(Referer)
    # This should be refactored into a module, include support for other
    # webservers and - ideally - autodetect the flavor and even validate the IIS
    # regexp against the embedded header IIS puts in its log files.

    LOG_RE = re.compile("""
        ^(?P<year>\d{4})\-(?P<month>\d{2})\-(?P<day>\d{2})\s+
        (?P<hour>\d{2})\:(?P<minute>\d{2})\:(?P<second>\d{2})\s+
        (?P<c_ip>\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\s+
        (?P<cs_username>.+?)\s+
        (?P<s_ip>\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\s+
        (?P<s_port>\d{1,3})\s+
        (?P<cs_method>.+?)\s+
        (?P<cs_uri_stem>.+?)\s+
        (?P<cs_uri_query>.+?)\s+
        (?P<sc_status>\d{1,3})\s+
        (?P<sc_bytes>\d+)\s+
        (?P<cs_bytes>\d+)\s+
        (?P<csUser_Agent>.+?)\s+
        (?P<csReferer>.+)
    """.strip(), re.IGNORECASE and re.VERBOSE)


    def __init__(self, server=None, time_factor=1, max_clients=10, max_connections=6):
        from tornado import ioloop, httpclient

        self.http_client = httpclient.AsyncHTTPClient(
            max_simultaneous_connections=max_connections,
            max_clients=max_clients,
        )

        self.ioloop = ioloop.IOLoop.instance()

        if not server.startswith("http://"):
            server = "http://%s" % server

        self.server = server
        self.time_factor = time_factor

    def get_log_generator(self):
        for filename in self.log_files:
            if filename.endswith(".gz"):
                f = gzip.open(filename)
            elif filename.endswith(".zip"):
                f = zipfile.ZipFile(filename, mode="r").open()
            else:
                f = file(f)

            # TODO: In conjunction with refactoring log reading, the time logic should move in the main code
            # Reset our virtual clock based on the first entry in the log file:
            current_time = None

            for l in f:
                m = self.LOG_RE.match(l)

                if not m:
                    logging.debug("Skipping noise line %s", l)
                    continue

                l_time = datetime.datetime(
                    int(m.group("year")),
                    int(m.group("month")),
                    int(m.group("day")),
                    int(m.group("hour")),
                    int(m.group("minute")),
                    int(m.group("second"))
                )

                if not current_time:
                    current_time = l_time

                delta_time = l_time - current_time
                # TODO: The max drift should be a command-line option:
                if delta_time.seconds >= 1:
                    logging.info("Sleeping until simulated time %s", l_time)
                    # … and we're throwing all of that nice asynchronous goodness away for a
                    # little while:
                    time.sleep(delta_time.seconds / self.time_factor)

                current_time = l_time

                url = m.group("cs_uri_stem")
                if m.group("cs_uri_query") != "-":
                    url += "?" + m.group("cs_uri_query")

                yield urllib.basejoin(self.server, url), int(m.group("sc_status"))

    def parse_next_line(self):
        if not self._log_generator:
            self._log_generator = self.get_log_generator()

        return self._log_generator.next()

    def load_next_url(self):

        try:
            url, status_code = self.parse_next_line()

            logging.debug("Queuing URL=%s, status=%s", url, status_code)

            self.total += 1

            self.http_client.fetch(url,
                partial(self.response_handler, status_code=status_code)
            )
        except StopIteration:
            self.elapsed = time.time() - self.start_time
            logging.debug("Processed all %d URLs; stopping ioloop", self.total)
            self.ioloop.stop()

    def run(self):
        self.start_time = time.time()

        self.load_next_url()
        self.ioloop.start()

    def response_handler(self, response, status_code):
        url = response.request.url

        if response.code != status_code:
            logging.warning("URL %s returned %s, not expected %s", url, response.code, status_code)
            self.errors += 1

        self.completed += 1

        self.load_next_url()

def main(argv=None):
    try:
        import tornado
    except ImportError, e:
        logging.critical("Couldn't import Tornado. Try installing it from tornadoweb.org.", e)
        sys.exit(99)

    cmdparser = optparse.OptionParser(__doc__.strip(), version="log_replay %s" % __version__)
    cmdparser.add_option("--verbosity", "-v", "--verbose", action="count", help="Display more progress information")
    cmdparser.add_option("--max-connections", type="int", default=8, help="Set the number of simultaneous connections")
    cmdparser.add_option("--max-clients", type="int", default=10, help="Set the number of simultaneous clients")
    cmdparser.add_option("--factor", type="int", default=1, help="Replay logs at this factor of realtime (default=%default)")
    cmdparser.add_option("--server", help="Set the server used for each URL")
    (options, args) = cmdparser.parse_args()

    if not args:
        cmdparser.error("You must provide at least one file containing the log lines to replay")

    if not options.server:
        cmdparser.error("You must set the server name to run against")

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

    replayer = LogReplayer(server=options.server, max_connections=options.max_connections, max_clients=options.max_clients, time_factor=options.factor)

    for arg in args:
        if not os.path.exists(arg):
            cmdparser.error("%s doesn't exist" % arg)

    replayer.log_files = args

    replayer.run()

    print "Replayed {total} URLs ({bad} errors) in {elapsed:0.2f} seconds ({rate:0.1f} req/s)".format(
        total=replayer.total,
        elapsed=replayer.elapsed,
        rate=replayer.total / replayer.elapsed,
        bad=replayer.errors
    )


if __name__ == "__main__":
    sys.exit(main())
