"""
Copyright 2012 John Wiseman <jjwiseman@gmail.com>

Creates a usable version of the diydrones.com activity feed (and maybe
other Ning activity feeds).
"""

__author__ = 'John Wiseman <jjwiseman@gmail.com>'

import argparse
import jinja2
import logging
import re
import StringIO
import sys
import threading
import time
import urllib2

import bs4

import feedparser


class Error(Exception):
  pass


LOGGING_LEVELS = {
  'DEBUG': logging.DEBUG,
  'INFO': logging.INFO,
  'WARNING': logging.WARNING,
  'ERROR': logging.ERROR,
  'CRITICAL': logging.CRITICAL
  }


def get_logging_level_by_name(name):
  return LOGGING_LEVELS[name]


def improve_feed(feed):
  logging.info('Improving feed')
  requests = []
  for item in feed['items']:
    try:
      request = improve_item(item)
      if request:
        requests.append(request)
    except Error, e:
      logging.error('Skipping item %s (%s) due to error %s',
                    item['id'], item['title'], e)
  manager = AsyncURLFetchManager()
  manager.fetch_urls(requests)
  logging.info('Done improving feed')


def improve_item(item):
  item_type = ItemType.find_matching_item_type(item)
  if item_type:
    logging.info('------ Improving item of type %s title=%s',
                 item_type.name, item['title'])
    return item_type.improve(item)
  else:
    logging.warn('------ Skipping unknown feed item %s (%s)',
                 item['id'], item['title'])
    return None


class ItemType(object):
  ITEM_TYPES = []

  @classmethod
  def def_item_type(cls, name=None, title_re=None, link_re=None,
                    improver=None):
    item_type = ItemType(name=name, title_re=title_re, link_re=link_re,
                         improver=improver)
    cls.ITEM_TYPES.append(item_type)

  @classmethod
  def find_matching_item_type(cls, item):
    soup = bs4.BeautifulSoup(item['summary'])
    for item_type in cls.ITEM_TYPES:
      if item_type.is_item_of_this_type(item, soup):
        return item_type
    return None

  def __init__(self, name=None, title_re=None, link_re=None, improver=None):
    self.name = name
    self.title_re = re.compile(title_re)
    self.link_re = re.compile(link_re)
    self.improver = improver

  def is_item_of_this_type(self, item, soup):
    if self.title_re.search(item['title']):
      for anchor in soup.find_all('a'):
        if self.link_re.search(unicode(anchor)):
          return True
    return False

  def improve(self, item):
    return self.improver(self, item)


# --------------------
# Blog comments
# --------------------

def improve_blog_comment(unused_item_type, item):
  needed_url = item['link']

  def callback(url, html):
    logging.info('Blog comment callback for %s', url)
    comment_body = extract_blog_comment(url, html)
    if not comment_body:
      logging.error('Skipping improvement of item, could not find comment.')
    else:
      logging.info('Adding comment body to item')
      summary = item['summary']
      summary += '\n'
      summary += comment_body
      item['summary'] = summary

  return Request(url=needed_url, callback=callback)


ItemType.def_item_type(
  name='BLOG COMMENT',
  title_re=r'commented on.+blog post',
  link_re=r'http://diydrones.com/xn/detail/([0-9]+):BlogPost:([0-9]+)',
  improver=improve_blog_comment)


def extract_blog_comment(url, soup):
  idstr = blog_comment_id_from_url(url)
  logging.info('Looking for comment %s from url %s', idstr, url)
  tag = soup.find(_id=idstr)
  if tag:
    logging.info('Found comment: %s', tag_summary(tag))
    return unicode(tag)
  else:
    logging.error('Could not find blog comment %s at url %s', idstr, url)
    return None


def blog_comment_id_from_url(url):
  blog_id, comment_id = parse_comment_link(url)
  return '%s:Comment:%s' % (blog_id, comment_id)


COMMENT_LINK_RE = re.compile(
  r'http://diydrones.com/xn/detail/([0-9]+):Comment:([0-9]+)')


def parse_comment_link(url):
  match = COMMENT_LINK_RE.search(url)
  if match:
    return match.group(1), match.group(2)
  else:
    raise Error('%s does not seem to be a comment link.' % (
      url,))


# --------------------
# Forum replies
# --------------------

def improve_forum_reply(unused_item_type, item):
  needed_url = item['link']

  def callback(url, html):
    logging.info('Forum reply callback for %s', url)
    reply_body = extract_forum_reply(url, html)
    if not reply_body:
      logging.error('Skipping improvement of item, could not find reply.')
    else:
      logging.info('Adding forum reply to item')
      summary = item['summary']
      summary += '\n'
      summary += reply_body
      item['summary'] = summary

  return Request(url=needed_url, callback=callback)

ItemType.def_item_type(
  name='FORUM REPLY',
  title_re=r'replied.*to.*discussion',
  link_re=r'http://diydrones.com/xn/detail/([0-9]+):Topic:([0-9])+',
  improver=improve_forum_reply)


def extract_forum_reply(url, soup):
  idstr = forum_reply_id_from_url(url)
  logging.info('Looking for forum reply %s from url %s', idstr, url)
  tag = soup.find(id=idstr)
  if tag:
    logging.info('Found forum reply: %s', tag_summary(tag))
    return unicode(tag)
  else:
    logging.error('Could not find forum reply %s at url %s', idstr, url)
    return None


def forum_reply_id_from_url(url):
  blog_id, reply_id = parse_comment_link(url)
  return 'desc_%sComment%s' % (blog_id, reply_id)


def tag_summary(tag):
  s = StringIO.StringIO(unicode(tag))
  for line in s:
    return line[:-1]


# --------------------
# Status comment
# --------------------

def improve_status_comment(unused_item_type, item):
  needed_url = item['link']

  def callback(url, html):
    logging.info('Status comment callback for %s', url)
    reply_body = extract_status_comment(url, html)
    if not reply_body:
      logging.error('Skipping improvement of item, could not find reply.')
    else:
      logging.info('Adding status comment to item')
      summary = item['summary']
      summary += '\n'
      summary += reply_body
      item['summary'] = summary

  return Request(url=needed_url, callback=callback)


ItemType.def_item_type(
  name='STATUS COMMENT',
  title_re=r'commented on.+status',
  link_re=r'http://diydrones.com/xn/detail/([0-9]+):Status:([0-9])+',
  improver=improve_status_comment)


def extract_status_comment(url, soup):
  idstr = status_comment_id_from_url(url)
  logging.info('Looking for status comment %s from url %s', idstr, url)
  tag = soup.find(_id=idstr)
  if tag:
    logging.info('Found status comment: %s', tag_summary(tag))
    return unicode(tag)
  else:
    logging.error('Could not find status comment %s at url %s', idstr, url)
    return None


def status_comment_id_from_url(url):
  blog_id, reply_id = parse_comment_link(url)
  return '%s:Comment:%s' % (blog_id, reply_id)


def fetch_html(url):
  start_time = time.time()
  req = urllib2.urlopen(url)
  content = req.read()
  encoding = req.headers['content-type'].split('charset=')[-1]
  end_time = time.time()
  logging.info('Fetched URL %s with charset=%s in %s secs',
               url, encoding, end_time - start_time)
  soup = bs4.BeautifulSoup(content, from_encoding='utf-8')
  return soup


FEED_TEMPLATES = {
  'atom1.0': 'atom_1.0.tmpl',
  'rss2.0': 'rss_2.0.tmpl'
  }


def get_template_for_format(feed_format):
  return FEED_TEMPLATES[feed_format]


def process_feed_url(feed_url, output_format='atom1.0'):
  feed = feedparser.parse(feed_url)
  return process_feed(feed, output_format=output_format, feed_id=feed_url)


def process_feed(feed, output_format='atom1.0', feed_id=None):
  improve_feed(feed)
  if feed_id:
    feed.feed.id = feed_id
  return generate_feed(feed, output_format)


def generate_feed(feed, feed_format):
  logging.info('Generating feed in format %s', feed_format)
  template = get_template_for_format(feed_format)
  with open(template, 'rb') as tmpl_in:
    template = jinja2.Template(tmpl_in.read())
    for item in feed['items']:
      item['title_detail']['language'] = 'en-us'
    return template.render(feed)


class AsyncUrlRequest(threading.Thread):
  def __init__(self, url, callback=None):
    threading.Thread.__init__(self, name='AsyncUrlRequest for %s' % (url,))
    self.url = url
    self.callback = callback
    self.html = None
    self.request_complete = threading.Event()

  def begin_fetch(self):
    logging.info('Starting async fetch of %s', self.url)
    self.start()

  def run(self):
    self.html = fetch_html(self.url)
    logging.info('Finished async fetch of %s', self.url)
    if self.callback:
      self.callback(self.url, self.html)
    self.request_complete.set()

  def wait(self):
    self.request_complete.wait()


class Request(object):
  def __init__(self, url=None, callback=None):
    self.url = url
    self.callback = callback


class AsyncURLFetchManager(object):
  def __init__(self):
    self.lock = threading.Condition()
    # 1:many map from URLs to callbacks.
    self.url_callbacks = {}

  def fetch_urls(self, requests):
    logging.info('Async fetch of %s URLs requested.', len(requests))
    # Build URL -> callback map.
    for request in requests:
      url = request.url
      callbacks = self.url_callbacks.get(url, [])
      self.url_callbacks[url] = callbacks + [request.callback]

    # Create requests.
    active_requests = []
    for url in self.url_callbacks:
      callback = self.make_multi_callback(self.url_callbacks[url])
      active_requests.append(AsyncUrlRequest(url, callback))

    # Begin issuing requests.
    logging.info('Beginning async fetch of %s URLs', len(active_requests))
    start_time = time.time()
    for request in active_requests:
      request.begin_fetch()

    # Wait for requests to complete.
    logging.info('Waiting for async fetch of %s URLs', len(active_requests))
    for request in active_requests:
      request.wait()
    end_time = time.time()
    logging.info('Finished async request of %s urls in %s secs',
                 len(active_requests), end_time - start_time)

  def make_multi_callback(self, callbacks):
    def do_callbacks(url, html):
      for callback in callbacks:
        callback(url, html)
    return do_callbacks


def main():
  parser = argparse.ArgumentParser(
    description='Improve a Ning activity feed.',
    formatter_class=argparse.ArgumentDefaultsHelpFormatter)
  parser.add_argument(
    'input',
    help='URL of the input feed')
  parser.add_argument(
    '--log_level',
    dest='log_level',
    choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
    default='INFO',
    help='The logging level to use.')
  parser.add_argument(
    '--output-format',
    dest='output_format',
    choices=['rss2.0', 'atom1.0'],
    default='rss2.0',
    help='The desired output format')
  args = parser.parse_args()
  logging.basicConfig(level=get_logging_level_by_name(args.log_level))
  feed = feedparser.parse(args.input)
  output_feed = process_feed(feed, output_format=args.output_format)
  sys.stdout.write(output_feed.encode('utf-8'))


if __name__ == '__main__':
  main()
