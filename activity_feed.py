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
import urllib2

import bs4

try:
  from django.conf import settings as django_settings
  # Need to do this to use django templates.
  django_settings.configure()
except:
  pass

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
  for item in feed['items']:
    try:
      improve_item(item)
    except Error, e:
      logging.error('Skipping item %s (%s) due to error %s',
                    item['id'], item['title'], e)


def improve_item(item):
  item_type = ItemType.find_matching_item_type(item)
  if item_type:
    logging.info('------ Improving item of type %s title=%s',
                 item_type.name, item['title'])
    item_type.improve(item)
  else:
    logging.warn('------ Skipping unknown feed item %s (%s)',
                 item['id'], item['title'])


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
    for item_type in cls.ITEM_TYPES:
      if item_type.is_item_of_this_type(item):
        return item_type
    return None

  def __init__(self, name=None, title_re=None, link_re=None, improver=None):
    self.name = name
    self.title_re = re.compile(title_re)
    self.link_re = re.compile(link_re)
    self.improver = improver

  def is_item_of_this_type(self, item):
    if self.title_re.search(item['title']):
      soup = bs4.BeautifulSoup(item['summary'])
      for anchor in soup.find_all('a'):
        if self.link_re.search(unicode(anchor)):
          return True
    return False

  def improve(self, item):
    self.improver(self, item)


# --------------------
# Blog comments
# --------------------

def improve_blog_comment(unused_item_type, item):
  comment_body = get_blog_comment(item['link'])
  if not comment_body:
    logging.error('Skipping improvement of item, could not find comment.')
    return
  summary = item['summary']
  summary += '\n'
  summary += comment_body
  item['summary'] = summary


ItemType.def_item_type(
  name='BLOG COMMENT',
  title_re=r'commented on.+blog post',
  link_re=r'http://diydrones.com/xn/detail/([0-9]+):BlogPost:([0-9]+)',
  improver=improve_blog_comment)


def get_blog_comment(url):
  idstr = blog_comment_id_from_url(url)
  logging.info('Looking for comment %s from url %s', idstr, url)
  soup = fetch_html(url)
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
  reply_body = get_forum_reply(item['link'])
  if not reply_body:
    logging.error('Skipping improvement of item, could not find reply.')
    return
  summary = item['summary']
  summary += '\n'
  summary += reply_body
  item['summary'] = summary


ItemType.def_item_type(
  name='FORUM REPLY',
  title_re=r'replied.*to.*discussion',
  link_re=r'http://diydrones.com/xn/detail/([0-9]+):Topic:([0-9])+',
  improver=improve_forum_reply)


def get_forum_reply(url):
  idstr = forum_reply_id_from_url(url)
  logging.info('Looking for forum reply %s from url %s', idstr, url)
  soup = fetch_html(url)
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
  reply_body = get_status_comment(item['link'])
  if not reply_body:
    logging.error('Skipping improvement of item, could not find reply.')
    return
  summary = item['summary']
  summary += '\n'
  summary += reply_body
  item['summary'] = summary


ItemType.def_item_type(
  name='STATUS COMMENT',
  title_re=r'commented on.+status',
  link_re=r'http://diydrones.com/xn/detail/([0-9]+):Status:([0-9])+',
  improver=improve_status_comment)


def get_status_comment(url):
  idstr = status_comment_id_from_url(url)
  logging.info('Looking for status comment %s from url %s', idstr, url)
  soup = fetch_html(url)
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


# To improve feeds we do a little HTML scraping.  Here we keep a cache
# of web pages so that if we improve two blog comments we don't end up
# fetching the blog post twice.

HTML_CACHE = {}


def fetch_html(url):
  if not (url in HTML_CACHE):
    req = urllib2.urlopen(url)
    content = req.read()
    encoding = req.headers['content-type'].split('charset=')[-1]
    logging.info('Fetched URL %s with charset=%s', url, encoding)
    soup = bs4.BeautifulSoup(content, from_encoding='utf-8')
    HTML_CACHE[url] = soup
  return HTML_CACHE[url]


def get_template_for_format(format):
  if format == 'atom1.0':
    return 'atom_1.0.tmpl'
  elif format == 'rss2.0':
    return 'rss_2.0.tmpl'
  else:
    return Error('Unknown output format %s' % (format,))


def process_feed_url(feed_url, output_format='atom1.0'):
  feed = feedparser.parse(feed_url)
  return process_feed(feed, output_format=output_format, feed_id=feed_url)


def process_feed(feed, output_format='atom1.0', feed_id=None):
  improve_feed(feed)
  if feed_id:
    feed.feed.id = feed_id
  return generate_feed(feed, output_format)


def generate_feed(feed, format):
  template = get_template_for_format(format)
  with open(template, 'rb') as tmpl_in:
    template = jinja2.Template(tmpl_in.read())
    for item in feed['items']:
      item['title_detail']['language'] = 'en-us'
    return template.render(feed)


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
