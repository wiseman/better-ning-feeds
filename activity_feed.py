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
    improve_item(item)


def improve_item(item):
  if is_blog_activity_item(item):
    logging.info('------ Improving blog activity item %s', item['title'])
    improve_blog_activity_item(item)
  else:
    logging.warn('------ Skipping unknown feed item %s (%s)',
                 item['id'], item['title'])


def improve_blog_activity_item(item):
  comment_body = get_comment(item['link'])
  summary = item['summary']
  summary += '\n'
  summary += comment_body
  item['summary'] = summary


def is_blog_activity_item(item):
  soup = bs4.BeautifulSoup(item['summary'])
  for anchor in soup.find_all('a'):
    if is_blog_activity_url(unicode(anchor)):
      return True
  return False


def is_blog_activity_url(url):
  regex = re.compile(r'http://diydrones.com/xn/detail/[0-9]+:BlogPost:[0-9]+')
  return regex.search(url)


def parse_activity_comment_link(url):
  """Returns (post ID, comment ID).

  Example: Given the URL
  'http://diydrones.com/xn/detail/705844:Comment:868656?xg_source=activity'
  we would return (705844, 868656).
  """
  regex = r'/detail/([0-9]*):Comment:([0-9]*)\?'
  match = re.search(regex, url)
  if match:
    return match.group(1), match.group(2)
  else:
    raise ValueError('%s does not seem to be an activity comment link.' % (
      url,))


def comment_id_from_comment_url(url):
  blog_id, comment_id = parse_activity_comment_link(url)
  return '%s:Comment:%s' % (blog_id, comment_id)


def get_comment(url):
  idstr = comment_id_from_comment_url(url)
  logging.info('Looking for comment %s from url %s', idstr, url)
  soup = fetch_html(url)
  tag = soup.find(_id=idstr)
  if not tag:
    raise Error('Could not find comment %s at url %s' % (idstr, url))
  logging.info('Found comment: %s', tag_summary(tag))
  return unicode(tag)


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
