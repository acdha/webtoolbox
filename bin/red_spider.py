#!/usr/bin/env python
# encoding: utf-8

"""
Spiders one or more URIs, analyzing linked pages and resources

Usage:

    %prog http://example.com

"""


from red import ResourceExpertDroid
from link_parse import HTMLLinkParser

import os
import sys
import optparse
import logging
import re
from urlparse import urlparse
from collections import defaultdict
from cgi import escape

try:
    import tidylib
except ImportError:
    pass


class HTMLAccumulator(object):
    content = u""
    http_enc = "latin-1"

    def feed(self, response, fragment):
        """Used as a body processor to collect the entire document for HTML validation"""
        http_enc = response.parsed_hdrs['content-type'][1].get('charset', self.http_enc)
        try:
            if not isinstance(fragment, unicode):
                fragment = unicode(fragment, http_enc, 'strict')
            self.content += fragment
        except UnicodeError, e:
            logging.warning("Couldn't decode fragment: %s" % e)

    def __str__(self):
        return self.content


class SpiderReport(object):
    """Represents information which applies to one or more URIs"""
    messages  = defaultdict(dict)
    pages     = None
    resources = None

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
        template = open(os.path.join(os.path.dirname(__file__), "..", "webtoolbox", "templates", "red_spider_template.html"))

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

        print >> output, """<h1>All Pages</h1><ul class="uri"><li>%s</li></ul>""" % "</li><li>".join(map(make_link, sorted(self.pages)))
        print >> output, """<h1>All Resources</h1><ul class="uri"><li>%s</li></ul>""" % "</li><li>".join(map(make_link, sorted(self.resources)))

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


class REDSpider(object):
    pages        = set()
    resources    = set()
    tidy_re      = re.compile("line (?P<line>\d+) column (?P<column>\d+) - (?P<level>\w+): (?P<message>.*)$", re.MULTILINE)
    skip_link_re = re.compile("^$") # URLs which match won't be spidered

    def __init__(self, uris, language="en", validate_html=False, skip_media=False, skip_resources=False):
        self.allowed_hosts  = [urlparse(u)[1] for u in uris]
        self.language       = language
        self.skip_media     = skip_media
        self.skip_resources = skip_resources
        self.uris           = uris
        self.validate_html  = validate_html

        self.report = SpiderReport()

    def run(self):
        for uri in self.uris:
            self.pages.add(uri)

            link_parser = HTMLLinkParser(uri, self.process_link)
            body_procs = [ link_parser.feed ]

            if self.validate_html:
                html_body = HTMLAccumulator()
                body_procs.append(html_body.feed)

            logging.debug("Processing page: %s", uri)

            red = ResourceExpertDroid(uri, status_cb=logging.debug, body_procs=body_procs)

            for m in red.messages:
                self.report_red_message(m, uri)

            # Avoid HTML validation for pages which didn't load correctly. RED normally
            # reports an error in this case so we'll leave the general server
            # failure message in the report but avoid further reporting

            if red.res_status in ("301", "302"):
                self.process_link(red.parsed_hdrs['location'], '<HTTP Redirect>', '')
                continue
            elif red.res_status == "200":
                # We only validate pages which loaded successfully:
                if red.res_complete and self.validate_html and red.parsed_hdrs['content-type'][0] == 'text/html':
                    self.report_tidy_messages(uri, html_body.content)

            errs = not red.res_complete or any([ m for m in red.messages if m.level in ['error', 'bad']])

            if errs:
                logging.warn("Found problems in: %s", uri)
            else:
                logging.info("Processed page: %s", uri)


        assert len(self.uris) <= len(self.pages)

        for uri in self.resources:
            red = ResourceExpertDroid(uri, status_cb=logging.info)

            for m in red.messages:
                self.report_red_message(m, uri)

        # Convenience copies for reporting:
        self.report.pages = self.pages
        self.report.resources = self.resources

    def report_tidy_messages(self, uri, html):
        (cleaned_html, warnings) = tidylib.tidy_document(html)

        for warn_match in self.tidy_re.finditer(warnings):
            sev = "error" if warn_match.group("level").lower() == "error" else "warning"
            self.report.add(severity=sev, category="HTML", title=warn_match.group("message"), uri=uri)

    def report_red_message(self, msg, uri):
        """Unpacks a message as returned in ResourceExpertDroid.messages"""

        title   = self.get_loc(msg.summary) % msg.vars
        details = self.get_loc(msg.text) % msg.vars

        if title.startswith("The resource last changed"):
            return

        self.report.add(uri=uri, category=msg.category, severity=msg.level, title=title, details=details)

    def get_loc(self, red_dict):
        """Return the preferred language version of a message returned by RED"""
        return red_dict.get(self.language, red_dict['en'])

    def process_link(self, link, tag, title):
        link_parts = urlparse(link)

        if link_parts.netloc and not link_parts.netloc in self.allowed_hosts:
            logging.debug("Skipping external resource: %s", link)
            return

        if self.skip_link_re.match(link):
            logging.debug("Link matched skip_link_re - skipping %s", link)
            return

        if not link_parts.scheme.startswith("http"):
            logging.debug("Skipping non-HTTP link: %s", link)
            return

        # <HTTP Redirect> is used when we encounter 301/302 redirects:
        if tag in ['a', 'frame', 'iframe', '<HTTP Redirect>']:
            if not link in self.pages:
                self.uris.append(link)
                self.pages.add(link)
        else:
            if tag in ['script', 'link'] and self.skip_resources:
                return

            if not self.skip_media:
                self.resources.add(link)


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
    root_logger.name = "red_spider"

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

    if options.validate_html and not "tidylib" in sys.modules:
        logging.warning("Couldn't import tidylib - HTML validation is disabled. Try installing from PyPI or http://countergram.com/software/pytidylib")
        options.validate_html = False


    rs = REDSpider(uris,
        validate_html=options.validate_html,
        skip_media=options.skip_media,
        skip_resources=options.skip_resources,
    )

    if options.skip_link_re:
        i = options.skip_link_re

        if not i[0] == "^":
            i = r"^.*%s" % i
            logging.warn("Corrected unanchored skip_link_re to: %s", i)

        rs.skip_link_re = re.compile(i, re.IGNORECASE)

    rs.run()

    rs.report.save(format=options.report_format, output=options.report_file)

    if options.page_list:
        save_uri_list(options.page_list, sorted(rs.pages))

    if options.resource_list:
        save_uri_list(options.resource_list, sorted(rs.resources))

if "__main__" == __name__:
    main()
