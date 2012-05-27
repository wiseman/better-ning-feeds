import logging
import sys
sys.path.insert(0, 'beautifulsoup4-4.0.5-py2.7.egg')


import activity_feed
import feedparser
from google.appengine.api import urlfetch
from google.appengine.ext import webapp
from google.appengine.ext.webapp import template
from google.appengine.ext.webapp.util import run_wsgi_app


class MainPage(webapp.RequestHandler):
  def get(self):
    self.response.headers['Content-Type'] = 'text/html'
    self.response.out.write(template.render('index.tmpl', {}))


class FeedHandler(webapp.RequestHandler):
  def get(self, url):
    self.response.headers['Content-Type'] = 'text/xml'
    logging.info('Fetching external feed %s', url)
    feed_response = urlfetch.fetch(url)
    logging.info('Response code = %s', feed_response.status_code)
    if feed_response.status_code == 200:
      feed = feedparser.parse(feed_response.content)
      improved_feed_str = activity_feed.process_feed(
        feed, output_format='rss2.0', feed_id=url)
      self.response.out.write(improved_feed_str)


application = webapp.WSGIApplication(
  [('/', MainPage),
   ('/feed/(.*)', FeedHandler)],
  debug=True)


def main():
  run_wsgi_app(application)

if __name__ == "__main__":
  main()
