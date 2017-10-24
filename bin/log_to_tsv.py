#!/usr/bin/env python3
# encoding: utf-8
"""
Convert various webserver log formats to tab-separated values with output control
"""

import argparse
import logging
import sys
import os
import re
import gzip
import zipfile
import datetime
from collections import namedtuple
from urllib.parse import urljoin


__version__ = "1.0"


MONTH_NAMES = {
    'Jan': 1,
    'Feb': 2,
    'Mar': 3,
    'Apr': 4,
    'May': 5,
    'Jun': 6,
    'Jul': 7,
    'Aug': 8,
    'Sep': 9,
    'Oct': 10,
    'Nov': 11,
    'Dec': 12
}

LogEntry = namedtuple('LogEntry', ['timestamp', 'method', 'status', 'path', 'query_string', 'user_agent'])


def core_log_iterator(LOG_RE, log_filename):
    if log_filename.endswith(".gz"):
        f = gzip.open(log_filename, mode='rt')
    elif log_filename.endswith(".zip"):
        f = zipfile.ZipFile(log_filename, mode='r').open()
    else:
        f = open(log_filename, mode='r')

    try:
        for line_number, line in enumerate(f):
            m = LOG_RE.match(line)

            if not m:
                logging.debug("Skipping noise line %d: %s", line_number, line.strip())
                continue

            groups = m.groupdict()

            if 'month_name' in groups:
                month = MONTH_NAMES[groups['month_name']]
            else:
                month = int(groups["month"])

            l_time = datetime.datetime(int(groups["year"]), month, int(groups["day"]),
                                       int(groups["hour"]), int(groups["minute"]), int(groups["second"]))

            path = groups["request_path"]

            if "uri_query" in groups:
                qs = groups["uri_query"]
            elif '?' in path:
                path, qs = path.split('?', 1)
            else:
                qs = ''

            yield LogEntry(
                timestamp=l_time.timestamp(), method=groups['method'], status=int(groups["status_code"]),
                path=path, query_string=qs, user_agent=groups['user_agent']
            )
    finally:
        f.close()


def iis_log_iterator(log_filename):
    # FIXME: This is currently based on IIS log lines like this:
    # date time c-ip cs-username s-ip s-port cs-method cs-uri-stem cs-uri-query sc-status sc-bytes cs-bytes cs(User-Agent) cs(referer)
    # This should be refactored into a module, include support for other
    # webservers and - ideally - autodetect the flavor and even validate the IIS
    # regexp against the embedded header IIS puts in its log files.

    IIS_LOG_RE = re.compile(r"""
        ^(?P<year>\d{4})\-(?P<month>\d{2})\-(?P<day>\d{2})\s+
        (?P<hour>\d{2})\:(?P<minute>\d{2})\:(?P<second>\d{2})\s+
        (?P<client_ip>\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\s+
        (?P<username>.+?)\s+
        (?P<server_ip>\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\s+
        (?P<server_port>\d{1,3})\s+
        (?P<method>.+?)\s+
        (?P<request_path>.+?)\s+
        (?P<uri_query>.+?)\s+
        (?P<status_code>\d{1,3})\s+
        (?P<response_bytes>\d+)\s+
        (?P<cs_bytes>\d+)\s+
        (?P<user_agent>.+?)\s+
        (?P<csreferer>.+)
    """.strip(), re.IGNORECASE and re.VERBOSE)

    yield from core_log_iterator(IIS_LOG_RE, log_filename)


def apache_log_iterator(log_filename):
    APACHE_LOG_RE = re.compile(r"""
        ^
        (?P<c_virtualhost>([^:]+:\d+|))\s
        (?P<client_ip>[^ ]+)\s
        (?P<username>[^ ]+?)\s
        ([^ ]+)\s+
        \[(?P<day>\d{2})/(?P<month_name>[^/]+)/(?P<year>\d{4})\:(?P<hour>\d{2})\:(?P<minute>\d{2})\:(?P<second>\d{2}) (?P<tz_offset>[^]]+)\]\s
        "(?P<method>[^ ]+)\s
        (?P<request_path>[^ ]+)\s
        (?P<protocol>[^"]+)"\s
        (?P<status_code>\d{1,3})\s+
        (?P<response_bytes>\d+)\s*
        "(?P<referer>.*?)"\s*
        "(?P<user_agent>.*?)"
    """.strip(), re.IGNORECASE and re.VERBOSE)

    yield from core_log_iterator(APACHE_LOG_RE, log_filename)


def get_log_entries(filenames, flavor):
    if flavor == 'iis':
        log_iterator = iis_log_iterator
    else:
        log_iterator = apache_log_iterator

    for filename in filenames:
        yield from log_iterator


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


def main(argv=None):
    parser = argparse.ArgumentParser(__doc__.strip())
    parser.add_argument('--verbosity', '--verbose', '-v', default=0, action='count')
    parser.add_argument('--log-format', default="apache", choices=("apache", "iis"))

    parser.add_argument('--no-headers', default=False, help='Do not include a header row')

    # TODO: add less-common fields:
    output_options = parser.add_argument_group('Output Options')
    for i in LogEntry._fields:
        output_options.add_argument('--%s' % i.replace('_', '-'), action='store_true', default=False)

    output_options.add_argument(
        '--base-url', type=str,
        help='Create a URL field by joining the specified base URL with the logged path and querystring')

    parser.add_argument('log_files', metavar='LOG_FILE', nargs='+')
    args = parser.parse_args()

    if not args:
        parser.error("You must provide at least one log file")

    configure_logging(args.verbosity)

    if args.log_format == 'iis':
        log_iterator = iis_log_iterator
    else:
        log_iterator = apache_log_iterator

    expected_fields = [i for i in LogEntry._fields if getattr(args, i)]

    if args.base_url:
        expected_fields.append('URL')

        # TODO: validate this
        base_url = args.base_url
    else:
        base_url = None

    if not args.no_headers:
        print(*expected_fields, sep='\t')

    for arg in args.log_files:
        if not os.path.exists(arg):
            parser.error("%s doesn't exist" % arg)
        else:
            for log_entry in log_iterator(arg):
                fields = [getattr(log_entry, i) for i in expected_fields if i != 'URL']
                if base_url:
                    fields.append(urljoin(base_url, '%s?%s' % (log_entry.path, log_entry.query_string)))
                print(*fields, sep='\t')


if __name__ == "__main__":
    sys.exit(main())
