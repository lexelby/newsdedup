#!/home/lex/.pyenv/shims/python
# -*- coding: utf-8 -*-
"""News dedup for Tiny Tiny RSS."""
#
# Copyright (C) 2015 Peter Reuterås

import traceback
import configparser
import argparse
import logging
import sys
import time
from collections import deque
from fuzzywuzzy import fuzz
from ttrss.client import TTRClient


last_seen_id = 0


def read_configuration(config_file):
    """Read configuration file."""
    config = configparser.RawConfigParser()
    config.read(config_file)
    if config.sections() == []:
        print("Can't find configuration file.")
        sys.exit(1)
    return config

def init_ttrss(config):
    """Init Tiny tiny RSS API."""
    hostname = config.get('ttrss', 'hostname')
    username = config.get('ttrss', 'username')
    password = config.get('ttrss', 'password')

    htusername = config.get('ttrss', 'htusername')
    htpassword = config.get('ttrss', 'htpassword')
    http_auth = ()
    if htusername or htpassword:
        http_auth = (htusername, htpassword)

    client = TTRClient(hostname, username, password, http_auth=http_auth)
    client.login()

    return client

def init_title_queue(config):
    """Init deque queue to store handled titles."""
    maxcount = int(config.get('newsdedup', 'maxcount'))
    return deque(maxlen=maxcount)

def init_ignore_list(config):
    """Read ignore list from config and store in array."""
    ignorestring = config.get('newsdedup', 'ignore')
    return ignorestring.split(',')

def init_include_list(config):
    """Read include list from config."""
    return config.get('newsdedup', 'include').split(',')

def learn_last_read(rss, queue, arguments, config):
    """Get maxcount of read RSS and add to queue."""
    maxlearn = int(config.get('newsdedup', 'maxcount'))
    feeds = rss.get_feeds()
    learned = 0
    seen = 0
    limit = 200 if maxlearn > 200 else maxlearn
    while learned < maxlearn:
        headlines = feeds[3].headlines(
            view_mode='all_articles',
            limit=limit, skip=seen)
        for article in headlines:
            seen += 1
            if not article.unread:
                queue.append(article.title)
                learned += 1
        if arguments.debug:
            print_time_message(arguments,
                               "Debug: Learned titles from " + str(learned) + " RSS articles.")
    if arguments.verbose:
        print_time_message(arguments, "Learned titles from " + str(learned) + " RSS articles.")
    return queue

def compare_to_queue(queue, head, ratio, arguments):
    """Compare current title to all in queue."""
    for item in queue:
        if fuzz.token_sort_ratio(item, head.title) > ratio:
            if arguments.verbose:
                print_time_message(arguments, "### Old title: " + item)
                print_time_message(arguments, "### New: " + head.feed_title + ": " + head.title)
                print_time_message(arguments, "### Ratio:" +
                                   str(fuzz.token_sort_ratio(item, head.title)))
            return fuzz.token_sort_ratio(item, head.title)
    return 0

def handle_known_news(rss, head):
    """Mark read and add star. Might change in the future."""
    #rss.update_article(head.id, 1, 0)
    rss.mark_read(head.id)

def print_time_message(arguments, message):
    """Print time and message."""
    try:
        if arguments.daemon:
            print(message)
        else:
            print(time.strftime("%Y-%m-%d %H:%M:%S:", time.gmtime()), message)
    except Exception as error: # pylint: disable=broad-except
        if arguments.debug:
            print("Debug: Error in print_time_message: ", str(error))

    sys.stdout.flush()

def check_filter(headline, ignore_list, include_list):
    if include_list and not any(term in headline.feed_title for term in include_list):
        return False

    if headline.feed_id in ignore_list:
        return False

    return True

def monitor_rss(rss, queue, ignore_list, include_list, arguments, config):
    """Main function to check new rss posts."""
    global last_seen_id

    ratio = int(config.get('newsdedup', 'ratio'))
    sleeptime = int(config.get('newsdedup', 'sleep'))
    headlines = []
    while True:
        feeds = rss.get_feeds(unread_only=True)

        headlines = []
        skip = 0

        while True:
            unread_headlines = feeds[1].headlines(since_id=last_seen_id, view_mode='unread', limit=200, skip=skip)
            skip += 200

            if not unread_headlines:
                break

            headlines += unread_headlines

        headlines.sort(key=lambda headline: headline.id)

        for head in headlines:
            if head.id <= last_seen_id:
                continue

            if arguments.verbose:
                print_time_message(arguments, "Considering %d: %s / %s " % (head.id, head.feed_title, head.title))
            if (not head.is_updated) and check_filter(head, ignore_list, include_list):
                if compare_to_queue(queue, head, ratio, arguments) > 0:
                    if arguments.dry_run:
                        print_time_message(arguments, "### Would mark as read: %s" % head.id)
                    else:
                        print_time_message(arguments, "### Marking as read: %s" % head.id)
                        handle_known_news(rss, head)
                elif arguments.debug:
                    print_time_message(arguments, "### Allowing: %s %s" % (head.id, head.title))
            queue.append(head.title)
            last_seen_id = head.id

        if arguments.debug:
            print_time_message(arguments, "Sleeping.")
        time.sleep(sleeptime)

def run(rss_api, title_queue, feed_ignore_list, feed_include_list, args, configuration):
    """Main loop."""
    while True:
        try:
            monitor_rss(rss_api, title_queue, feed_ignore_list, feed_include_list, args, configuration)
        except KeyboardInterrupt:
            sys.exit(1)
        except Exception as error: # pylint: disable=broad-except
            print_time_message(args, "Exception in monitor_rss.")
            if args.debug:
                print_time_message(args, "Debug: Message: " + str(error))

def main():
    """Main function to handle arguments."""
    parser = argparse.ArgumentParser(
        prog='newsdedup',
        description='''This programs dedups RSS articles handled by
            Tiny tiny RSS.''',
        epilog='''Program made by Peter Reuterås, @reuteras on Twitter.
            If you find a bug please let me know.''')
    parser.add_argument('configFile', metavar='newsdedup.cfg',
                        default='newsdedup.cfg', nargs='?',
                        help='Specify configuration file.')
    parser.add_argument('-d', '--debug', action="store_true",
                        help='Debug output (separate from verbose).')
    parser.add_argument('-D', '--daemon', action="store_true",
                        help='Run as daemon.')
    parser.add_argument('-q', '--quiet', action="store_true",
                        help='Quiet, i.e. catch SSL warnings.')
    parser.add_argument('-v', '--verbose', action="store_true",
                        help='Verbose output.')
    parser.add_argument('-n', '--dry-run', action="store_true",
                        help="Don't actually mark any articles as read")
    args = parser.parse_args()

    if args.quiet:
        logging.captureWarnings(True)
    configuration = read_configuration(args.configFile)
    rss_api = init_ttrss(configuration)
    title_queue = init_title_queue(configuration)
    feed_ignore_list = init_ignore_list(configuration)
    feed_include_list = init_include_list(configuration)
    learn_last_read(rss_api, title_queue, args, configuration)

    run(rss_api, title_queue, feed_ignore_list, feed_include_list, args, configuration)

if __name__ == '__main__':
    main()
