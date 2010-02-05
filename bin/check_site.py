#!/usr/bin/env python
# encoding: utf-8

"""
Spiders a site looking for problems

Usage:

    %prog http://example.com

Currently checks:
    1. HTML Validation
    2. Bad links (Internal)
    3. Bad links (External)

"""

from cgi import escape
from collections import defaultdict

import logging
import optparse
import os
import re
import sys
import time

from webtoolbox.clients import Spider

# Used to process the string report returned by tidylib:
TIDY_RE = re.compile("line (?P<line>\d+) column (?P<column>\d+) - (?P<level>\w+): (?P<message>.*)$", re.MULTILINE)

class SpiderReport(object):
    """Represents information which applies to one or more URLs"""

    #: Can be updated to pass variables into the template context:
    extra_context = {
        "title": "Spider Report"
    }

    messages  = defaultdict(dict)
    pages     = set()
    resources = set()
    media     = set()

    # Severity levels, used to simplify sorting:
    SEVERITY_LEVELS = {
        "info":     "Informational",
        "good":     "Good Practice",
        "bad":      "Bad Practice",
        "warning":  "Warning",
        "error":    "Error",
    }

    # Used to avoid problems with dict.keys() not being stable:
    REPORT_ORDER = ('error', 'warning', 'bad', 'good', 'info')

    def add(self, url=None, category=None, severity=None, title=None, details=None):
        if not severity in self.SEVERITY_LEVELS:
            raise ValueError("%s is not a valid severity level" % severity)

        # TODO: This is Perlish:
        tgt  = self.messages.setdefault(severity, {}).setdefault(category, {}).setdefault(title, {})

        if not tgt:
            tgt['urls'] = set()
            tgt['details'] = details

        tgt['urls'].add(url)

    def save(self, format="html", output=sys.stdout):
        if format == "html":
            self.generate_html(output)
        else:
            self.generate_text(output)

    def generate_html(self, output):
        from jinja2 import Environment, PackageLoader
        env = Environment(autoescape=True, loader=PackageLoader('webtoolbox', 'templates'))

        template = env.get_template("check_site_report.html")
        output.write(template.render(
            messages=self.messages,
            pages=self.pages,
            media=self.media,
            resources=self.resources,
            severity_levels=self.REPORT_ORDER,
            **self.extra_context
        ))

    def generate_text(self, output):
        print "%(title)s" % self.extra_context
        print "Retrieved %(urls_total)d URLs in %(elapsed_time)0.2f seconds with %(urls_error)d errors" % self.extra_context

        for level in self.REPORT_ORDER:
            if not level in self.messages:
                continue

            print >> output, "%s:" % self.SEVERITY_LEVELS[level]
            categories = self.messages[level]

            for category in sorted(categories.keys()):
                summaries = categories[category]
                print >> output, "\t%s:" % category

                for summary, data in summaries.items():
                    print >> output, "\t\t%s: %d pages" % (summary, len(data['urls']))
                    print >> output, "\t\t\t%s" % "\n\t\t\t".join(sorted(data['urls']))
                    print >> output

            print >> output


class QASpider(Spider):
    def __init__(self, validate_html=False, log_name="QASpider", **kwargs):
        super(QASpider, self).__init__(log_name=log_name, **kwargs)
        self.report = SpiderReport()

        if validate_html:
            self.html_processors.append(self.validate_html)

        self.tree_processors.append(self.tree_resource_accounting)
        self.header_processors.append(self.update_resource_report)

    def validate_html(self, url, body):
        import tidylib

        html, warnings = tidylib.tidy_document(body, {"char-encoding": "utf8"})

        for warn_match in TIDY_RE.finditer(warnings):
            sev = "error" if warn_match.group("level").lower() == "error" else "warning"
            self.report.add(severity=sev, category="HTML", title=warn_match.group("message"), url=url)

        return html

    def tree_resource_accounting(self, url, tree):
        """
        Some elements can be reliably predicted based on their tag names so
        we'll add them to our report before fetching them
        """

        for element, attribute, link, pos in tree.iterlinks():
            if element.tag in ('link', 'script'):
                self.report.resources.add(link)
            elif element.tag in ('img', 'embed', 'object', 'audio', 'video'):
                self.report.media.add(link)

    def update_resource_report(self, url, headers):
        """
        Since we can't tell whether the contents of a link point to a page or
        a media file we have to wait until we've retrieved it and use the
        content type
        """

        content_type = headers.get("Content-Type", None)

        if not content_type:
            return

        if content_type.startswith("text/html"):
            self.report.pages.add(url)
        else:
            self.report.media.add(url)


def save_url_list(fn, data):
    f = open(fn, "w")
    f.write("\n".join(data))
    f.write("\n")
    f.close()


def configure_logging(options):
    # One of our imports must be initializing because logging.basicConfig() does
    # nothing if called in main(). We'll reset logging and configure it correctly:

    root_logger = logging.getLogger()

    for handler in root_logger.root.handlers:
        root_logger.removeHandler(handler)
        handler.close()

    root_logger.setLevel(logging.DEBUG)
    root_logger.name = "main"

    if options.verbosity > 1:
        log_level = logging.DEBUG
    elif options.verbosity > 0:
        log_level = logging.INFO
    else:
        log_level = logging.WARN

    std_formatter = logging.Formatter("[%(name)s] [%(levelname)s]: %(message)s")

    console_log = logging.StreamHandler(sys.stderr)
    console_log.setLevel(log_level)
    console_log.setFormatter(std_formatter)
    root_logger.addHandler(console_log)

    if options.log_file:
        log_file = logging.FileHandler(options.log_file)
        log_file.setLevel(log_level)
        log_file.setFormatter(std_formatter)
        root_logger.addHandler(log_file)


def main():
    parser = optparse.OptionParser(__doc__.strip())

    parser.add_option("--max-connections", type="int", default="2", help="Set the number of simultaneous connections to the remote server(s)")
    parser.add_option("--format", dest="report_format", default="text", help='Generate the report as HTML or text')
    parser.add_option("-o", "--report", "--output", dest="report_file", default=sys.stdout, help='Save report to a file instead of stdout')
    parser.add_option("--validate-html", action="store_true", default=False, help="Validate HTML using tidylib")
    parser.add_option("--skip-media", action="store_true", default=False, help="Skip media files: <img>, <object>, etc.")
    parser.add_option("--skip-resources", action="store_true", default=False, help="Skip resources: <script>, <link>")
    parser.add_option("--skip-link-re", type="string", help="Skip links whose URL matches the specified regular expression")
    parser.add_option("--save-page-list", dest="page_list", help='Save a list of URLs for HTML pages in the specified file')
    parser.add_option("--save-resource-list", dest="resource_list", help='Save a list of URLs for pages resources in the specified file')
    parser.add_option("--language", default="en", help="Report using a different language than '%default'")
    parser.add_option("-l", "--log", dest="log_file", help='Specify a location other than stderr', default=None)
    parser.add_option("-v", "--verbosity", action="count", default=0, help="Log level")

    (options, urls) = parser.parse_args()

    configure_logging(options)

    if not urls:
        parser.error("You must provide at least one URL to start spidering")

    if options.report_format == "html":
        try:
            import jinja2
        except ImportError:
            logging.critical("You requested an HTML report but Jinja2 could not be imported. Try `pip install jinja2`")
            sys.exit(42)

    if not isinstance(options.report_file, file):
        options.report_file = file(options.report_file, "w")

    if options.validate_html:
        try:
            import tidylib
        except ImportError:
            logging.critical("Couldn't import tidylib: %s")
            logging.critical("Cannot perform HTML validation. Try `pip install pytidylib` or see http://countergram.com/software/pytidylib")
            sys.exit(42)

    spider = QASpider(validate_html=options.validate_html, max_simultaneous_connections=options.max_connections)
    spider.skip_media     = options.skip_media
    spider.skip_resources = options.skip_resources

    if options.skip_link_re:
        i = options.skip_link_re

        if not i[0] == "^":
            i = r"^.*%s" % i
            logging.warn("Corrected unanchored skip_link_re to: %s", i)

        spider.skip_link_re = re.compile(i, re.IGNORECASE)

    start = time.time()
    spider.run(urls)
    end = time.time()

    if not spider.completed:
        logging.warn("Aborting due to incomplete results!")
        sys.exit(1)

    spider.report.extra_context.update(
        title="Site Report for %s" % ", ".join(spider.allowed_hosts),
        start_time=start,
        end_time=end,
        elapsed_time=end - start,
        urls_total=spider.processed,
        urls_error=spider.errors,
    )

    spider.report.save(format=options.report_format, output=options.report_file)

    if options.page_list:
        save_url_list(options.page_list, sorted(spider.pages))

    if options.resource_list:
        save_url_list(options.resource_list, sorted(spider.resources))

if "__main__" == __name__:
    main()
