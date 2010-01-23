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

import os
import sys
import optparse
import logging
import re
from collections import defaultdict
from cgi import escape

from webtoolbox.clients import Spider

# Used to process the string report returned by tidylib:
TIDY_RE = re.compile("line (?P<line>\d+) column (?P<column>\d+) - (?P<level>\w+): (?P<message>.*)$", re.MULTILINE)

class SpiderReport(object):
    """Represents information which applies to one or more URIs"""
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

    def __init__(self, severity=None, title="", details=""):
        self.severity = severity
        self.title    = title
        self.details  = details

    def add(self, uri=None, category=None, severity=None, title=None, details=None):
        if not severity in self.SEVERITY_LEVELS:
            raise ValueError("%s is not a valid severity level" % severity)

        # TODO: This is Perlish:
        tgt  = self.messages.setdefault(severity, {}).setdefault(category, {}).setdefault(title, {})

        if not tgt:
            tgt['uris'] = set()
            tgt['details'] = details

        tgt['uris'].add(uri)

    def save(self, format="html", output=sys.stdout):
        if format == "html":
            self.generate_html(output)
        else:
            self.generate_text(output)

    def generate_html(self, output):
        def make_link(url):
            url = escape(url)
            # TODO: Save page titles for pretty links?
            title = url if len(url) < 70 else escape(url[0:70]) + "&hellip;"

            return """<a href="%s">%s</a>""" % (url, title)

        # TODO: Switch to a templating system - but which one?
        template = open(os.path.join(os.path.dirname(__file__), "..", "lib", "red_spider_template.html"))

        for line in template:
            if "GENERATED_CONTENT" in line:
                break
            output.write(line)

        for level in self.REPORT_ORDER:
            if not level in self.messages: continue

            print >> output, """<h1 id="%s">%s</h1>""" % (level, self.SEVERITY_LEVELS[level])
            categories = self.messages[level]

            for category in sorted(categories.keys()):
                summaries = categories[category]
                print >> output, """<h2 class="%s">%s</h2>""" % (category, category)

                print >> output, """
                    <table class="%s">
                        <thead>
                            <tr>
                                <th>Message</th>
                                <th>Pages</th>
                            </tr>
                        </thead>
                        <tbody>
                """ % " ".join(map(escape, [level, category]))

                for summary, data in sorted(summaries.items(), key=lambda i: (i[0].lower(), i[1])):
                    print >> output, """
                        <tr>
                            <td>%s</td>
                            <td> <ul class="uri"><li>%s</li></ul> </td>
                        </tr>
                    """ % (escape(summary), "</li><li>".join(map(make_link, sorted(data['uris']))))

                print >> output, """</tbody></table>"""

        print >> output, """<h1>All Pages</h1><ul class="uri page"><li>%s</li></ul>""" % "</li><li>".join(map(make_link, sorted(self.pages)))
        print >> output, """<h1>All Resources</h1><ul class="uri resource"><li>%s</li></ul>""" % "</li><li>".join(map(make_link, sorted(self.resources)))
        print >> output, """<h1>All Media</h1><ul class="uri media"><li>%s</li></ul>""" % "</li><li>".join(map(make_link, sorted(self.media)))

        output.writelines(template)

    def generate_text(self, output):
        for level in self.REPORT_ORDER:
            if not level in self.messages:
                continue

            print >> output, "%s:" % self.SEVERITY_LEVELS[level]
            categories = self.messages[level]

            for category in sorted(categories.keys()):
                summaries = categories[category]
                print >> output, "\t%s:" % category

                for summary, data in summaries.items():
                    print >> output, "\t\t%s: %d pages" % (summary, len(data['uris']))
                    print >> output, "\t\t\t%s" % "\n\t\t\t".join(sorted(data['uris']))
                    print >> output

            print >> output


class QASpider(Spider):
    def __init__(self, validate_html=False, log_name="QASpider", **kwargs):
        super(QASpider, self).__init__(log_name=log_name, **kwargs)
        self.report = SpiderReport()
        
        if validate_html:
            self.html_processors.append(self.validate_html)

    def validate_html(self, url, body):
        import tidylib

        html, warnings = tidylib.tidy_document(body, {"char-encoding": "utf8"})

        for warn_match in TIDY_RE.finditer(warnings):
            sev = "error" if warn_match.group("level").lower() == "error" else "warning"
            self.report.add(severity=sev, category="HTML", title=warn_match.group("message"), uri=url)

        return html


def save_uri_list(fn, data):
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

    (options, uris) = parser.parse_args()

    configure_logging(options)

    if not uris:
        parser.error("You must provide at least one URL to start spidering")

    if not isinstance(options.report_file, file):
        options.report_file = file(options.report_file, "w")

    if options.validate_html:
        try:
            import tidylib
        except ImportError:
            logging.critical("Couldn't import tidylib: %s")
            logging.critical("Cannot perform HTML validation. Try `pip install pytidylib` or see http://countergram.com/software/pytidylib")
            sys.exit(42)

    rs = QASpider(validate_html=options.validate_html)
    rs.skip_media     = options.skip_media
    rs.skip_resources = options.skip_resources

    if options.skip_link_re:
        i = options.skip_link_re

        if not i[0] == "^":
            i = r"^.*%s" % i
            logging.warn("Corrected unanchored skip_link_re to: %s", i)

        rs.skip_link_re = re.compile(i, re.IGNORECASE)

    rs.run(uris)

    if not rs.completed:
        logging.warn("Aborting due to incomplete results!")
        sys.exit(1)

    rs.report.save(format=options.report_format, output=options.report_file)

    if options.page_list:
        save_uri_list(options.page_list, sorted(rs.pages))

    if options.resource_list:
        save_uri_list(options.resource_list, sorted(rs.resources))

if "__main__" == __name__:
    main()
