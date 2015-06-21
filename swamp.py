#!/usr/bin/python

import sys
import argparse
import gevent

if 'threading' in sys.modules:
    raise Exception('threading module loaded before patching!')

from gevent import monkey
from gevent.queue import JoinableQueue
monkey.patch_all()

# requests must be loaded after gevent because of threading module
import requests
from hashlib import md5
from bs4 import BeautifulSoup
import urlparse
import urlnorm
import urllib
import collections

def main(args):
    print '-i- Checking', args.url
    url = args.url

    print '-i- Using %s workers' % args.workers
    q = JoinableQueue()

    pagehandler = SwampPageHandler()
    pagehandler.ignore_query = args.ignore_query

    if args.ignore_query:
        print '-i- Ignoring the following query params:', args.ignore_query

    worker = Worker(pagehandler, q, args.workers)

    # context in which new urls are relative to starting url
    context = URLContext(url, url)

    worker.add([context])

    try:
        worker.wait()
    except KeyboardInterrupt:
        print ' Abort.'
        return

class Worker():

    q = None

    found = None

    base_url = None

    processed = 0

    PageHandler = None

    def __init__(self, pagehandler, q, workers):
        self.found = set()
        self.q = q
        self.pagehandler = pagehandler

        # spawn workers
        for i in range(workers):
            gevent.spawn(self.worker)

    def worker(self):
        while True:
            job = self.q.get()
            try:
                self.add(self.pagehandler.process(job))
            finally:
                self.processed += 1
                self.q.task_done()

    def add(self, found):
        # remove urls we have found already
        found = set(found) - self.found

        # update already found urls with the newly found ones
        self.found |= found

        if self.processed % 20 == 0:
            print 'Found', len(self.found), 'Processed', self.processed, 'Queue', self.q.qsize()

        # put new urls in queue
        for new in found:
            self.q.put(new)

    def wait(self):
        self.q.join()

class SwampPageHandler():

    context = None

    method = 'get'

    fields = []

    ignore_query = []

    def process(self, context):
        self.context = context
        #url = urlparse.urljoin(self.context.referer, self.context.url)
        url = context.url

        try:
            r = requests.get(url)
        except Exception as e:
            print '-!- Error during request:', str(e)
            return []

        print r.status_code, url

        if r.status_code != 200:
            return []

        # only check return code of external urls, dont crawl them
        referer_parts = urlparse.urlsplit(self.context.referer)
        url_parts = urlparse.urlsplit(url)
        if self.context.referer != '' and referer_parts.netloc != url_parts.netloc:
            return []

        try:
            text = r.text
        except TypeError:
            # this does not seem to be text, skip
                return []

        return self.content(text, url)

    def content(self, body, referer):
        found = []

        try:
            soup = BeautifulSoup(body)
        except Exception:
            print '-!- Document could not be parsed!'
            return found

        atags = soup.find_all('a')

        for atag in atags:
            href = atag.get('href')

            if href == None:
                continue

            href = urlparse.urljoin(referer, href)
            found.append(URLContext(href, referer))

        return found

    def _normalize(self, url):
        # normalize
        urlhelper = URLHelper()
        url = urlhelper.normalize(url)

        # make url absolute
        self.url = urlparse.urljoin(referer, url)

    def _remove_ignored_params(self, url):
        url = urlparse.urlparse(url)
        query = urlparse.parse_qs(query)

        for param in self.ignore_query:
            try:
                del query[param]
            except Exception:
                pass

        query = urllib.urlencode(query)
        url = urlparse.urlunsplit((scheme, authority, path, query, fragment))
        return url


class URLContext():

    url = None

    referer = None

    method = 'get'

    _hash = None

    def __init__(self, url, referer):
        if url == None:
            raise Exception('Cannot url with type None')

        try:
            self.url = str(url)
        except Exception:
            print '-!- Could not convert url to string:', url

        self.referer = referer

    def __cmp__(self, other):
        return cmp(self.url, other.url)

    def __hash__(self):
        return self.url.__hash__()

class URLHelper():

    def normalize(self, url):
        # normalize url path
        (scheme, authority, path, parameters, query, fragment) = urlparse.urlparse(url)

        # sort query keys
        query = sorted(urlparse.parse_qs(query).items())
        query = collections.OrderedDict(query)

        # fix value lists
        for key, value in query.iteritems():
            query[key] = value[0]

        # assemble normalized url
        query = urllib.urlencode(query)
        url = urlparse.urlunsplit((scheme, authority, path, query, fragment))

        return url


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Swamp checks your website for errors.')
    parser.add_argument('url', help='The target url')
    parser.add_argument('--workers', dest='workers', default=5, type=int, metavar='amount', required=False, help='number of workers to process requests with.')
    parser.add_argument('--ignore-query', dest='ignore_query', action='append', metavar='param', required=False, help='query param to ignore')
    args = parser.parse_args()

    main(args)
