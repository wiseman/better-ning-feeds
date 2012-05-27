"""
Creates a usable version of the diydrones.com activity feed.
"""

__author__ = 'John Wiseman <jjwiseman@gmail.com>'

import argparse
import logging
import re
import StringIO
import sys
import urllib2

import bs4

try:
  from django import template as django_template
  from django.conf import settings as django_settings
  # Need to do this to use django templates.
  django_settings.configure()
except:
  from google.appengine.ext.webapp import template as django_template

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
  if is_blog_comment_item(item):
    logging.info('------ Improving blog comment item %s', item['title'])
    improve_blog_comment_item(item)
  elif is_forum_activity_item(item):
    logging.info('------ Improving forum reply item %s', item['title'])
    improve_forum_reply_item(item)
  else:
    logging.warn('------ Skipping unknown feed item %s (%s)',
                 item['id'], item['title'])


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
# Blog comments
# --------------------

def improve_blog_comment_item(item):
  comment_body = get_blog_comment(item['link'])
  if not comment_body:
    logging.error('Skipping improvement of item, could not find comment.')
    return
  summary = item['summary']
  summary += '\n'
  summary += comment_body
  item['summary'] = summary


BLOG_COMMENT_LINK_RE = re.compile(
  r'http://diydrones.com/xn/detail/([0-9]+):BlogPost:([0-9]+)')


def is_blog_comment_url(url):
  return BLOG_COMMENT_LINK_RE.search(url)


BLOG_COMMENT_TITLE_RE = re.compile(
  r'commented on.+blog post')


def is_blog_comment_item(item):
  if BLOG_COMMENT_TITLE_RE.search(item['title']):
    soup = bs4.BeautifulSoup(item['summary'])
    for anchor in soup.find_all('a'):
      if is_blog_comment_url(unicode(anchor)):
        return True
  return False


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


# --------------------
# Forum replies
# --------------------

def improve_forum_reply_item(item):
  reply_body = get_forum_reply(item['link'])
  if not reply_body:
    logging.error('Skipping improvement of item, could not find reply.')
    return
  summary = item['summary']
  summary += '\n'
  summary += reply_body
  item['summary'] = summary


FORUM_REPLY_LINK_RE = re.compile(
  r'http://diydrones.com/xn/detail/([0-9]+):Topic:([0-9])+')


def is_forum_activity_url(url):
  return FORUM_REPLY_LINK_RE.search(url)


FORUM_REPLY_TITLE_RE = re.compile(
  r'replied.*to.*discussion')


def is_forum_activity_item(item):
  if FORUM_REPLY_TITLE_RE.search(item['title']):
    soup = bs4.BeautifulSoup(item['summary'])
    for anchor in soup.find_all('a'):
      if is_forum_activity_url(unicode(anchor)):
        return True
  return False


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
    template = django_template.Template(tmpl_in.read())
    for item in feed['items']:
      item['title_detail']['language'] = 'en-us'
    return template.render(django_template.Context(feed))


# def generate_feed(feed):
#   rss = feedgenerator.Rss201rev2Feed(
#     title=feed.feed.title,
#     link=feed.feed.link,
#     description=feed.feed.description)
#   for item in feed['items']:
#     rss.add_item(title=item['title'],
#                  link=item['link'],
#                  description=item.summary)
#   return rss.writeString('utf8')


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
  output_feed = process_feed(args.input, output_format=args.output_format)
  sys.stdout.write(output_feed.encode('utf-8'))


if __name__ == '__main__':
  main()
