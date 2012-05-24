"""
Creates a usable version of the diydrones.com activity feed.
"""

__author__ = 'John Wiseman <jjwiseman@gmail.com>'

import logging
import re
import StringIO
import sys
import urllib2

import bs4
from django import template as django_template
from django.conf import settings as django_settings
import feedparser

# Need to do this to use django templates.
django_settings.configure()


class Error(Exception):
  pass


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


def is_blog_comment_item(item):
  soup = bs4.BeautifulSoup(item['summary'])
  for anchor in soup.find_all('a'):
    if is_blog_comment_url(unicode(anchor)):
      return True
  return False


def parse_blog_comment_link(url):
  match = BLOG_COMMENT_LINK_RE.search(url)
  if match:
    return match.group(1), match.group(2)
  else:
    raise Error('%s does not seem to be a blog comment link.' % (
      url,))


# --------------------
# Forum replies
# --------------------

def improve_forum_reply_item(item):
  reply_body = get_forum_reply(item['link'])


FORUM_REPLY_LINK_RE = re.compile(
  r'http://diydrones.com/xn/detail/([0-9]+):Topic:([0-9])+')


def is_forum_activity_url(url):
  return FORUM_REPLY_LINK_RE.search(url)


def is_forum_activity_item(item):
  soup = bs4.BeautifulSoup(item['summary'])
  for anchor in soup.find_all('a'):
    if is_forum_activity_url(unicode(anchor)):
      return True
  return False


def blog_comment_id_from_url(url):
  blog_id, comment_id = parse_blog_comment_link(url)
  return '%s:Comment:%s' % (blog_id, comment_id)


def get_blog_comment(url):
  idstr = blog_comment_id_from_url(url)
  logging.info('Looking for comment %s from url %s', idstr, url)
  soup = fetch_html(url)
  tag = soup.find(_id=idstr)
  if tag:
    logging.info('Found comment: %s', tag_summary(tag))
    return unicode(tag)
  else:
    logging.error('Could not find comment %s at url %s', idstr, url)
    return None


def parse_forum_reply_link(url):
  match = FORUM_REPLY_LINK_RE.search(url)
  if match:
    return match.group(1), match.group(2)
  else:
    raise ValueError('%s does not seem to be an activity forum reply link.' % (
      url,))


def get_forum_reply(url):
  idstr = forum_reply_id_from_url(url)
  logging.info('Looking for forum reply %s from url %s', idstr, url)
  soup = fetch_html(url)
  tag = soup.find(id=idstr)
  if not tag:
    raise Error('Could not find comment %s at url %s' % (idstr, url))
  logging.info('Found forum reply: %s', tag_summary(tag))


def forum_reply_id_from_url(url):
  blog_id, reply_id = parse_forum_reply_link(url)
  return 'desc%sComment%s' % (blog_id, reply_id)


def tag_summary(tag):
  s = StringIO.StringIO(unicode(tag))
  for line in s:
    return line[:-1]


def fetch_html(url):
  req = urllib2.urlopen(url)
  content = req.read()
  encoding = req.headers['content-type'].split('charset=')[-1]
  logging.info('Fetched URL %s with charset=%s', url, encoding)
  soup = bs4.BeautifulSoup(content, from_encoding='utf-8')
  return soup


def process_feed(feed_url):
  feed = feedparser.parse(feed_url)
  improve_feed(feed)
  return generate_feed(feed)


def generate_feed(feed):
  with open('atom_1.0.tmpl', 'rb') as tmpl_in:
    template = django_template.Template(tmpl_in.read())
    return template.render(django_template.Context(feed))


def main():
  logging.basicConfig(level=logging.DEBUG)
  input_feed_url = sys.argv[1]
  output_feed = process_feed(input_feed_url)
  sys.stdout.write(output_feed.encode('utf-8'))


if __name__ == '__main__':
  main()
