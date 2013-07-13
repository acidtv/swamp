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
	spawner = Spawner(q, args.workers)

	# context in which new urls are relative to starting url
	context = URLContext(url, url)

	spawner.add([context])

	try:
		spawner.wait()
	except KeyboardInterrupt:
		print ' Abort.'
		return

class Spawner():

	q = None

	found = None

	jobs = []

	base_url = None

	def __init__(self, q, workers):
		self.found = set()
		self.q = q

		# spawn workers
		for i in range(workers):
			gevent.spawn(self.worker)

	def worker(self):
		while True:
			job = self.q.get()
			try:
				self.add(Handle(job).process())
			finally:
				self.q.task_done()

	def add(self, found):
		# remove urls we have found already
		found = set(found) - self.found

		# update already found urls with the newly found ones
		self.found |= found

		# put new urls in queue
		for new in found:
			self.q.put(new)

	def wait(self):
		self.q.join()

class Handle():

	context = None

	method = 'get'

	fields = []

	def __init__(self, context):
		self.context = context

	def process(self):
		url = urlparse.urljoin(self.context.referer, self.context.url)

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

			new = URLContext(href, referer)
			found.append(new)

		return found

class URLContext():

	url = None

	referer = None

	method = 'get'

	_hash = None

	def __init__(self, url, referer):
		if url == None:
			raise Exception('Cannot url with type None')

		try:
			url = str(url)
		except Exception:
			print '-!- Could not convert url to string:', url

		# normalize
		urlhelper = URLHelper()
		url = urlhelper.normalize(url)

		# make url absolute
		self.url = urlparse.urljoin(referer, url)

		self.referer = referer

	def __cmp__(self, other):
		return self.__hash__() - other.__hash__()

	def __hash__(self):
		return self.url.__hash__()

class URLHelper():

	def normalize(self, url):
		# normalize url path
		url = urlparse.urlparse(url)
		(scheme, authority, path, parameters, query, fragment) = urlnorm.norm(url)

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
	parser.add_argument('--workers', dest='workers', default=5, type=int, metavar='amount', required=False, help='Number of workers to process requests with.')
	args = parser.parse_args()

	main(args)
