"""
Copyright 2012 John Wiseman <jjwiseman@gmail.com>

This is code for a Google appengine app that generates improved Ning
activity feeds.
"""

__author__ = 'John Wiseman <jjwiseman@gmail.com>'

import logging
import sys
sys.path.insert(0, 'beautifulsoup4-4.0.5-py2.7.egg')


import activity_feed
import feedparser

import bs4
from google.appengine.api import memcache
from google.appengine.api import taskqueue
from google.appengine.api import urlfetch
from google.appengine.ext import db
from google.appengine.ext import deferred
from google.appengine.ext import webapp
from google.appengine.ext.webapp import template
from google.appengine.ext.webapp.util import run_wsgi_app


class Feed(db.Model):
  feed_url = db.StringProperty(required=True)
  last_fetched_time = db.DateTimeProperty(auto_now=True)
  improved_content = db.TextProperty()


class MainPage(webapp.RequestHandler):
  def get(self):
    feeds = Feed.all()
    template_values = {'feeds': feeds}
    self.response.headers['Content-Type'] = 'text/html'
    self.response.out.write(template.render(
      'index.tmpl',
      template.Context(template_values)))


class AdminPage(webapp.RequestHandler):
  def get(self):
    template_values = {}
    self.response.headers['Content-Type'] = 'text/html'
    self.response.out.write(template.render(
      'admin.tmpl',
      template.Context(template_values)))

  def post(self):
    improve_feeds()
    template_values = {'message': '<p>Feed update is in progress!</p>'}
    self.response.headers['Content-Type'] = 'text/html'
    self.response.out.write(template.render(
      'admin.tmpl',
      template.Context(template_values)))


class CronHandler(webapp.RequestHandler):
  def get(self):
    improve_feeds()

  def post(self):
    improve_feeds()


class FeedHandler(webapp.RequestHandler):
  def get(self, url):
    logging.info('Handling request for feed %s', url)
    cached_feed = memcache.get(url)
    if cached_feed:
      logging.info('memcache hit for %s', url)
      self.response.headers['Content-Type'] = 'text/xml'
      self.response.out.write(cached_feed)
      return

    feed_info = get_feed_info(url)
    if feed_info:
      # We know about this feed.  Now we check whether we've improved
      # its content yet.
      if feed_info.improved_content:
        # Return the improved content we have.
        memcache.add(url, feed_info.improved_content)
        logging.info('Returning cached content for feed %s', url)
        self.response.headers['Content-Type'] = 'text/xml'
        self.response.out.write(feed_info.improved_content)
      else:
        # We don't have any improved content yet, so send a temporary
        # redirect to the original feed.
        self.redirect(url, permanent=False)
    else:
      # We don't know about this feed yet.  Create an info record for
      # it and then send a temporary redirect to the original.
      logging.info('This is a new feed; Adding %s', url)
      feed_info = Feed(key_name=url, feed_url=url)
      feed_info.put()
      self.redirect(url, permanent=False)


def get_feed_info(url):
  logging.info('Looking up feed %s', url)
  feed_key = db.Key.from_path('Feed', url)
  feed_info = db.get(feed_key)
  logging.info('Got %s', feed_info)
  return feed_info


def improve_feed(feed_url):
  feed_info = get_feed_info(feed_url)
  url = feed_info.feed_url
  logging.info('Fetching external feed %s', url)
  feed_response = urlfetch.fetch(url)
  logging.info('Response code = %s', feed_response.status_code)
  if feed_response.status_code == 200:
    feed = feedparser.parse(feed_response.content)
    improved_feed_str = activity_feed.process_feed(
      feed, output_format='rss2.0', feed_id=url,
      url_fetcher=GaeAsyncUrlFetcher())
    feed_info.improved_content = improved_feed_str
    logging.info('Storing improved feed for %s', url)
    db.put_async(feed_info)
    logging.info('Deleting %s from memcache', feed_url)
    memcache.delete(feed_url)
  else:
    logging.info('Skipping improvement of feed %s', feed_url)


def improve_feeds():
  logging.info('Kicking off feed improvement tasks')
  for feed_info in Feed.all():
    feed_url = feed_info.feed_url
    logging.info('Adding task for feed %s', feed_url)
    deferred.defer(improve_feed, feed_url)


class GaeAsyncUrlFetcher(object):
  """Asynchronous URL fetcher that uses Google App Engine's support
  for async URL fetching instead of python threads.
  """
  def __init__(self):
    pass

  def fetch_urls(self, requests):
    logging.info('Async fetch of %s URLs requested.', len(requests))
    # We may be asked to fetch the same URL multiple times, with
    # different callbacks each time.  For example, to improve two
    # items that are replies to the same blog post we would be asked
    # to fetch the URL to the post twice, with two callbacks to
    # improve the two comments.  We build a 1:many map in
    # url_callbacks that maps from unique URLs to all callbacks from
    # that URL.
    url_callbacks = {}
    for request in requests:
      url = request.url
      callbacks = url_callbacks.get(url, [])
      url_callbacks[url] = callbacks + [request.callback]
    logging.info(
      'Async fetch of %s unique URLs requested.', len(url_callbacks))

    # Create an async RPC for each URL.
    logging.info('Beginning async fetch of %s URLs', len(url_callbacks))
    timer = activity_feed.Timer()
    rpcs = []
    for url in url_callbacks:
      rpc = urlfetch.create_rpc(deadline=60)
      callback = make_multi_callback(rpc, url, url_callbacks[url])
      rpc.callback = callback
      urlfetch.make_fetch_call(rpc, url)
      rpcs.append(rpc)

    # Wait for requests to complete.
    logging.info('Waiting for async fetch of %s URLs', len(rpcs))
    for rpc in rpcs:
      rpc.wait()
    logging.info('Finished async request of %s urls in %s secs',
                 len(rpcs), timer.elapsed())


def make_multi_callback(rpc, url, callbacks):
  def do_callbacks():
    result = rpc.get_result()
    if result.status_code == 200:
      soup = bs4.BeautifulSoup(result.content, from_encoding='utf-8')
      for callback in callbacks:
        callback(url, soup)
    else:
      logging.info('Got status code %s for url %s', result.status_code, url)
  return do_callbacks


application = webapp.WSGIApplication(
  [('/', MainPage),
   ('/admin', AdminPage),
   ('/feed/(.*)', FeedHandler),
   ('/tasks/improve_feeds', CronHandler)],
  debug=True)


def main():
  run_wsgi_app(application)

if __name__ == "__main__":
  main()
