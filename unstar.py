#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Unstar RSS articles."""
#
# Copyright (C) 2015 Peter Reuterås

import argparse
import logging
import newsdedup
from types import IntType

def unstar_unread(rss_api, args):
    if isinstance(args.limit, IntType):
        limit = args.limit
    else:
        limit = args.limit[0]
    headlines = rss_api.get_headlines(feed_id=-1, limit=limit, view_mode='all_articles', show_excerpt=False)
    while headlines:
        for head in headlines:
            message = str(head.feed_title) + ": " + str(head.title) + ": " + str(head.link)
            print message
        remove = raw_input("Remove messages? (y/n): ")
        if remove == "y":
            for head in headlines:
                rss_api.update_article(head.id, 0, 0)
        headlines = rss_api.get_headlines(feed_id=-1, limit=limit, view_mode='all_articles', show_excerpt=False)

def main():
    """Main function to handle arguments."""
    parser = argparse.ArgumentParser(
        prog='unstar',
        description='''Unstar tool for newsdedup.''',
        epilog='''Program made by Peter Reuterås, @reuteras on Twitter.
            If you find a bug please let me know.''')
    parser.add_argument('configFile', metavar='newsdedup.cfg',
                        default='newsdedup.cfg', nargs='?',
                        help='Specify configuration file.')
    parser.add_argument('-q', '--quiet', action="store_true",
                        help='Quiet, i.e. catch SSL warnings.')
    parser.add_argument('-v', '--verbose', action="store_true",
                        help='Verbose output.')
    parser.add_argument('-l', '--limit', default=20, nargs=1, type=int,
                        help='Limit output to x (20 default).')
    args = parser.parse_args()

    if args.quiet:
        logging.captureWarnings(True)
    configuration = newsdedup.read_configuration(args.configFile)
    rss_api = newsdedup.init_ttrss(configuration)
    unstar_unread(rss_api, args)

if __name__ == '__main__':
    main()
