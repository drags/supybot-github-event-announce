###
# Github Event Announcer
#
# Because the firehose is delicious.
#
###

# SupyBot
from supybot.commands import *
import supybot.plugins as plugins
import supybot.callbacks as callbacks
import supybot.schedule as schedule
import supybot.ircmsgs as ircmsgs
import supybot.ircutils as ircutils
import supybot.log as log

# system
import time, threading, json, requests

# debug
import pprint
pp = pprint.PrettyPrinter(indent=4)

class GitEventAnnounce(callbacks.Plugin):
	"""Github Event Announcer: Announce the public or private event stream to an IRC channel"""
	threaded = True

	def __init__(self, irc):
		self.__parent = super(GitEventAnnounce, self)
		self.__parent.__init__(irc)
		self.pending_subscriptions = {}
		self.subscriptions = {}
		self.authorizations = {}
		self.irc = irc

		#loadsubs()

	def die(self):
		for sub in self.subscriptions.values():
			sub.stop_polling()

	def addsub(self, irc, msg, args, login_user, sub_type, target):
		"""Add an event stream to watch"""
		if sub_type not in Subscription.sub_types:
			irc.reply('Unknown subscription type: %s' %(sub_type))
			return

		sub = Subscription(irc, msg, login_user, sub_type, target)

		if str(sub) in self.subscriptions:
			irc.reply('The subscription %s already exists' % sub)
			return

		irc.reply('Adding %s' % (sub))
		if login_user in self.authorizations:
			sub.token = self.authorizations[login_user]['token']
			sub.start_polling()
		else:
			self.pending_subscriptions[str(sub)] = sub
			sub._authorize(msg)
	addsub = wrap(addsub, ['something', 'something', 'something'])

	def authorize(self, irc, msg, args, username, password):
		"""Retrieve an OAuth token"""
		reqdata = {
		'note': 'GitEventAnnouncer - https://github.com/drags/supybot-github-event-announce',
		'scopes': [ 'repo' ],
		}

		r = requests.post('https://api.github.com/authorizations', data=json.dumps(reqdata), auth=(username, password), headers={"Content-Type": "application/json" })
		if r.ok:
			self.authorizations[username] = {}
			self.authorizations[username]['id'] = r.json['id']
			self.authorizations[username]['token'] = r.json['token']

			for (name,sub) in self.pending_subscriptions.items():
				if sub.login_user == username:
					sub.token = r.json['token']
					sub.start_polling()
					self.subscriptions[name]=sub
					del(self.pending_subscriptions[name])
		else:
			msg = ircmsgs.privmsg(msg.nick, 'Failed to authorize against %s' % self.login_user)
			self.irc.queueMsg(msg)
	authorize = wrap(authorize, ['something','something'])

	def listsubs(self, irc, msg, args):
		"""LIst configured subscriptions"""
		global pp
		for s in self.subscriptions:
			pp.pprint(self.subscriptions[s])
			irc.reply(str(s))
		if len(self.pending_subscriptions) > 0:
			irc.reply("Pending subscriptions:")
			for s in self.pending_subscriptions:
				pp.pprint(self.pending_subscriptions[s])
				irc.reply(str(s))
	listsubs = wrap(listsubs)

Class = GitEventAnnounce

class Subscription(object):
	sub_types = {
		'user': 'https://api.github.com/users/%(target)s/events',
		'repository': 'https://api.github.com/repos/%(target_user)s/%(target_repo)s/events',
		'organization': 'https://api.github.com/users/%(login_user)s/events/orgs/%(target)s',
	}

	update_interval = 90
	minimum_update_interval = 60

	def __init__(self, irc, msg, login_user, sub_type, target):

		if sub_type == 'repository':
			(target_user, target_repo) = target.split('/')

		url = str(Subscription.sub_types[sub_type]) % locals()
		self.irc = irc
		self.channel = msg.args[0]
		self.login_user = login_user
		self.sub_type = sub_type
		self.target = target
		self.url = url
		self.headers = {}
		self.headers['content-type'] = 'application/json'
		global pp
		pp.pprint(irc)

	def __str__(self):
		return "[%s] %s@%s" % (self.sub_type, self.login_user, self.url)

	def _authorize(self, msg):
		self.irc.reply('Messaging you to authorize the %s account' % self.login_user)
		msg = ircmsgs.privmsg(msg.nick, "What is the password for the github user: %s" % self.login_user)
		self.irc.queueMsg(msg)
		msg = ircmsgs.privmsg(msg.nick, "Reply with authorize '%s' <password>" % self.login_user)
		self.irc.queueMsg(msg)

	def start_polling(self):
		self.headers['Authorization'] = 'token %s' % self.token
		schedule.addPeriodicEvent(self.fetch_updates, self.update_interval, now=True, name=self)

	def stop_polling(self):
		schedule.removeEvent(self)


	def fetch_updates(self):
		r = requests.get(self.url, headers=self.headers)


		# Update ETag to keep position
		if r.ok:
			if 'etag' in r.headers:
				self.headers['If-None-Match'] = r.headers['etag']
			self.announce_updates(r.json)

		elif r.status_code == 304:
			# No updates since last fetch
			return
		else:
			err = 'Unable to retrieve updates for %s, error: %s (%s)' % (self.subscription, r.text, r.reason)
			log.error('GEA: %s' % err)
			msg = ircmsgs.privmsg(self.subscriptions.channel, err)
			self.irc.queueMsg(msg)

	def announce_updates(self, updates):
		"""Takes list of Event updates from GitHub, handles or discards event as configured"""
		sa = SubscriptionAnnouncer()

		for event in updates:
			try:
				f = getattr(SubscriptionAnnouncer, event['type'])
				f(sa, self, event)
			except AttributeError, e:
				log.error("Unhandled event type %s" % (event['type']))

class SubscriptionAnnouncer:

	def CreateEvent(self, sub, e):

		(a,p,r) = self._mkdicts('apr',e)

		try:
			if e['payload']['ref_type'] == 'repository':
				msg = "[%s] @%s created new repository %s" % (r['name'], a['login'], r['name'])
			else:
				msg = "[%s] @%s created new %s '%s' on %s" % (r['name'], a['login'], p['ref_type'], p['ref'], r['name'])
		except KeyError, err:
			print "Got KeyError: %s" % err
			print e
			msg = "GEA: Failed to parse"

		qmsg = ircmsgs.privmsg(sub.channel, msg)
		sub.irc.queueMsg(qmsg)

	def PullRequestEvent(self, sub, e):

		(a,p,r) = self._mkdicts('apr',e)
		pr = p['pull_request']

		try:
			msg = "[%s] @%s %s pull request \"%s\" [%s]" % (r['name'], a['login'], p['action'], pr['title'], pr['_links']['html']['href'])
		except KeyError, err:
			print "Got KeyError: %s" % err
			print p
			msg = "GEA: Failed to parse event"

		qmsg = ircmsgs.privmsg(sub.channel, msg)
		sub.irc.queueMsg(qmsg)

	def PushEvent(self, sub, e):
		# Meh, just spam
		return
		(a,p,r) = self._mkdicts('apr',e)

		try:
			msg = "%s pushed %d commits to %s" % (a['login'],p['size'],r['name'])
		except KeyError, err:
			print "Got KeyError: %s" % err
			print p
			msg = "GEA: Failed to parse event"

		qmsg = ircmsgs.privmsg(sub.channel, msg)
		sub.irc.queueMsg(qmsg)

	def _mkdicts(self, flags, event):
		mapping = { 'a': 'actor', 'p': 'payload', 'r': 'repo' }
		dicts = []
		for c in str(flags):
			if c in mapping:
				dicts.append(event[mapping[c]])
		return dicts
