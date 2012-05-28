import logging
import sys
sys.path.insert(0, 'beautifulsoup4-4.0.5-py2.7.egg')


import activity_feed
import feedparser
from google.appengine.api import taskqueue
from google.appengine.api import urlfetch
from google.appengine.ext import db
from google.appengine.ext import webapp
from google.appengine.ext.webapp import template
from google.appengine.ext.webapp.util import run_wsgi_app



class Feed(db.Model):
  # We store the url in the key.
  last_fetched_time = db.DateTimeProperty(auto_now=True)
  improved_content = db.StringProperty()


class MainPage(webapp.RequestHandler):
  def get(self):
    self.response.headers['Content-Type'] = 'text/html'
    self.response.out.write(template.render('index.tmpl', {}))


class CronHandler(webapp.RequestHandler):
  def get(self):
    improve_feeds()


class TaskHandler(webapp.RequestHandler):
  def post(self):
    feed_url = self.request.get('url')
    logging.info('Running task to improve feed %s', url)
    improve_feed(url)
    logging.info('Task to improve feed %s is finished', url)


class FeedHandler(webapp.RequestHandler):
  def get(self, url):
    logging.info('Handling request for feed %s', url)
    feed_info = get_feed_info(url)
    if feed_info:
      # We know about this feed.  Now we check whether we've improved
      # its content yet.
      if feed_info.improved_content:
        # Return the improved content we have.
        logging.info('Returning cached content for feed %s', url)
        self.response.headers['Content-Type'] = 'text/xml'
        self.response.out.write(improved_content)
      else:
        # We don't have any improved content yet, so send a temporary
        # redirect to the original feed.
        self.redirect(url, permanent=False)
    else:
      # We don't know about this feed yet.  Create an info record for
      # it and then send a temporary redirect to the original.
      feed_info = Feed(key_name=url)
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
  url = feed_info.key()
  logging.info('Fetching external feed %s', url)
  feed_response = urlfetch.fetch(url)
  logging.info('Response code = %s', feed_response.status_code)
  if feed_response.status_code == 200:
    feed = feedparser.parse(feed_response.content)
    improved_feed_str = activity_feed.process_feed(
      feed, output_format='rss2.0', feed_id=url)
    feed_info.improved_content = improved_feed_str
    logging.info('Storing improved feed for %s', url)
    feed_info.put_async()


def improve_feeds():
  logging.info('Kicking off feed improvement tasks')
  for feed_info in Feed.all():
    logging.info('Adding task for feed %s', feed_info.key())
    taskqueue.add(
      url='/task/improve_feed',
      params={'url': feed_info.key()})


application = webapp.WSGIApplication(
  [('/', MainPage),
   ('/feed/(.*)', FeedHandler),
   ('/tasks/improve_feeds', CronHandler),
   ('/tasks/improve_feed', TaskHandler)],
  debug=True)


def main():
  run_wsgi_app(application)

if __name__ == "__main__":
  main()
