#!/usr/bin/python

import sys
import gevent

if 'threading' in sys.modules:
	        raise Exception('threading module loaded before patching!')

from gevent import monkey
from gevent.pool import Pool
monkey.patch_all()

# requests must be loaded after gevent because of threading module
import requests
from hashlib import md5
from bs4 import BeautifulSoup
from urlparse import urljoin

def main():
	base_url = 'http://azarius.local'
	pool = Pool(2)
	spawner = Spawner(pool, base_url)
	spawner.add(base_url)
	spawner.wait()

class Spawner():

	pool = None

	jobs = []

	base_url = None

	def __init__(self, pool, base_url):
		self.pool = pool
		self.base_url = base_url

	def add(self, item):
		def job(self, item):
			print 'start'
			handle = Handle(item, self.base_url)
			found = handle.process()
			for new in found:
				self.add(new)

		self.jobs.append(self.pool.spawn(job, self, item))

	def wait(self):
		gevent.joinall(self.jobs)

class Handle():

	base_url = None

	url = None

	method = 'get'

	fields = []

	_hash = None

	def __init__(self, url, base_url):
		self.url = url
		self.base_url = base_url

	def __hash__(self):
		if self._hash == None:
			#FIXME shorten self.url a bit
			s = ':'.join([self.method, self.url] + self.fields)
			m = md5()
			m.update(s)
			self._hash = m.hexdigest().__hash__()

		return self._hash


	def process(self):
		url = urljoin(self.base_url, self.url)
		print url
		r = requests.get(url)

		if (r.status_code != 200):
			return

		return self.content(r.text)

	def content(self, body):
		soup = BeautifulSoup(body)
		atags = soup.find_all('a')
		found = []

		for atag in atags:
			found.append(atag.get('href'))

		return found


if __name__ == '__main__':
	main()
