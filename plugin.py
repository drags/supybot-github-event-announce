####################################
# Github Event Announcer
#
# Because the firehose is delicious.
####################################
# system
import requests
import datetime

# SupyBot
from supybot.commands import * #noqa
import supybot.callbacks as callbacks
import supybot.schedule as schedule
import supybot.ircmsgs as ircmsgs
import supybot.conf as conf
import logging
import json
import os

# debug
import pprint
pp = pprint.PrettyPrinter(indent=4)

# logs
logger = logging.getLogger('supybot')


class GitEventAnnounce(callbacks.Plugin):

    '''Github Event Announcer: Announce the public or private event stream to
        an IRC channel'''
    threaded = True

    def __init__(self, irc):
        self.__parent = super(GitEventAnnounce, self)
        self.__parent.__init__(irc)
        self.pending_subscriptions = {}
        self.subscriptions = {}
        self.authorizations = {}
        self.irc = irc
        self.loadsubs(irc)

    def loadsubs(self, irc):
        '''Load subscriptions at plugin startup'''
        # Stored in root of bot 'data' directory
        subs_file = conf.supybot.directories.data.dirize('git-event-subs.json')
        if not os.path.exists(subs_file):
            return False
        logger.debug('Loading subscriptions from %s' % subs_file)
        with open(subs_file, 'r') as sub_fh:
            try:
                sub_data = json.load(sub_fh)
            except ValueError, e:
                logger.error('Failed to load subscription data from %s' %
                             subs_file)
                logging.error('Got error %s' % e)
                return False
            for (name, sub) in sub_data.items():
                new_sub = Subscription(irc, str(sub['channel']),
                                       str(sub['login_user']),
                                       str(sub['sub_type']),
                                       str(sub['target']))
                # Restore token, etag, last seen
                new_sub.token = str(sub['token'])
                new_sub.api_session.headers['If-None-Match'] = sub['etag']
                latest_event_dt = \
                    datetime.datetime.fromtimestamp(sub['latest_event'])
                new_sub.latest_event_dt = latest_event_dt

                # Start job
                new_sub.start_polling()
                self.subscriptions[name] = new_sub

        # Rebuild authorizations table
        for (name, sub) in self.subscriptions.items():
            if sub.login_user not in self.authorizations:
                self.authorizations[sub.login_user] = sub.token

    def savesubs(self):
        if len(self.subscriptions.keys()) < 1:
            return False

        sub_data = {}
        for (name, sub) in self.subscriptions.items():
            sub_data[name] = {
                'name': name,
                'channel': sub.channel,
                'login_user': sub.login_user,
                'sub_type': sub.sub_type,
                'target': sub.target,
                'token': sub.token,
                'url': sub.url,
                'job_name': sub.job_name,
                'etag': sub.api_session.headers.get('If-None-Match', ''),
                'latest_event': int(sub.latest_event_dt.strftime('%s')),
            }

        # Stored in root of bot 'data' directory
        subs_file = conf.supybot.directories.data.dirize('git-event-subs.json')
        with open(subs_file, 'w') as sub_fh:
            json.dump(sub_data, sub_fh)

    def die(self):
        '''Cleanup polling jobs'''
        # TODO ensure all subscriptions are killed (including 404'd repos)
        for sub in self.subscriptions.values():
            sub.stop_polling()
        self.savesubs()

    # TODO trigger on authorization delete to delete subs which use that auth

    def addsub(self, irc, msg, args, login_user, sub_type, target):
        '''Add an event stream to watch: args(github_user, type, name)'''
        # TODO add 404 checking to ensure repo/org/etc exists
        if sub_type not in Subscription.sub_types:
            known_types = ', '.join(Subscription.sub_types.keys())
            irc.reply('Unknown subscription type: %s' % (sub_type))
            irc.reply('Subscription type should be one of: %s' % (known_types))
            return

        channel = msg.args[0]
        try:
            sub = Subscription(irc, channel, login_user, sub_type, target)
        except ValueError:
            # assume anything that raises a valueerror will reply on its own
            return

        if str(sub) in self.subscriptions:
            irc.reply('The subscription %s already exists' % sub)
            return
        self.pending_subscriptions[str(sub)] = sub

        irc.reply('Adding %s' % (sub))

        if login_user in self.authorizations:
            self._auth_with_token(login_user, self.authorizations[login_user])
        else:
            sub._authorize(msg)
    addsub = wrap(addsub, ['somethingWithoutSpaces', 'somethingWithoutSpaces',
                           'somethingWithoutSpaces'])

    def delsub(self, irc, msg, args, login_user, sub_type, target):
        '''Delete a subscription: args(github_user, type, name)'''
        if sub_type not in Subscription.sub_types:
            known_types = ', '.join(Subscription.sub_types.keys())
            irc.reply('Unknown subscription type: %s' % (sub_type))
            irc.reply('Subscription type should be one of: %s' % (known_types))
            return

        # create temp sub to match on __str__
        channel = msg.args[0]
        try:
            sub_to_delete = Subscription(irc, channel, login_user, sub_type,
                                         target)
        except ValueError:
            # assume anything that raises a valueerror will reply on its own
            return

        sub_found = False
        for sub_list in [self.subscriptions, self.pending_subscriptions]:
            if str(sub_to_delete) in sub_list:
                sub_found = True
                irc.reply('Removing subscription %s' % (sub_to_delete))
                sub_list[str(sub_to_delete)].stop_polling()
                del(sub_list[str(sub_to_delete)])

        if sub_found is False:
            irc.reply('Sub %s was not found.' % sub_to_delete)

        # TODO cleanup self.authorizations
    delsub = wrap(delsub, ['somethingWithoutSpaces', 'somethingWithoutSpaces',
                           'somethingWithoutSpaces'])

    def authorize(self, irc, msg, args, username, token):
        '''Accept an OAuth token'''
        self._auth_with_token(username, token)
    authorize = wrap(authorize, ['somethingWithoutSpaces',
                                 'somethingWithoutSpaces'])

    def _auth_with_token(self, username, token):
        '''Finish OAuth handshake and init job'''
        # TODO test if token works/ has acceptable scope
        for (name, sub) in self.pending_subscriptions.items():
            if sub.login_user == username:
                sub.token = token
                sub.start_polling()
                self.subscriptions[name] = sub
                del(self.pending_subscriptions[name])

        # Add/update token to known token list
        self.authorizations[username] = token

    def listsubs(self, irc, msg, args):
        '''List known subscriptions'''
        global pp
        if len(self.subscriptions) > 0:
            irc.reply("Active subscriptions:")
            for s in self.subscriptions:
                irc.reply(str(s))
        else:
            irc.reply('No active subscriptions')
        if len(self.pending_subscriptions) > 0:
            irc.reply("Pending subscriptions:")
            for s in self.pending_subscriptions:
                irc.reply(str(s))
    listsubs = wrap(listsubs)

Class = GitEventAnnounce


class Subscription(object):
    sub_types = {
        'user': 'https://api.github.com/users/%(target)s/events',
        'repository':
        'https://api.github.com/repos/%(target_user)s/%(target_repo)s/events',
        'organization':
        'https://api.github.com/users/%(login_user)s/events/orgs/%(target)s',
    }

    # TODO ##update_interval = 90
    update_interval = 60
    minimum_update_interval = 60

    def __init__(self, irc, channel, login_user, sub_type, target):
        if sub_type == 'repository':
            if target.find('/') == -1:
                irc.reply(
                    'For repositories the target must be in the form <username>/<repo>') #noqa
                raise ValueError('Failed to split target') #noqa
            (target_user, target_repo) = target.split('/')

        url = str(Subscription.sub_types[sub_type]) % locals()
        self.irc = irc
        self.channel = channel
        self.login_user = login_user
        self.sub_type = sub_type
        self.target = target
        self.url = url
        self.api_session = requests.Session()
        self.api_session.headers['content-type'] = 'application/json'
        self.latest_event_dt = datetime.datetime(1970, 1, 1)
        self.job_name = 'poll-%s' % str(self)

        # Test validity
        self.validate_sub()

    def __str__(self):
        '''[type] user@url'''
        return "[%s] %s@%s" % (self.sub_type, self.login_user, self.url)

    def validate_sub(self):
        r = self.api_session.get(self.url)
        if not r.ok:
            emsg = "Failed to load %s. Got error code: %d, msg: %s" % \
                (self, r.status_code, r.reason)
            self.irc.reply(emsg)
            raise ValueError(emsg)

    def _authorize(self, msg):
        '''Ask user for an OAuth token.'''
        self.irc.reply(
            'Messaging you to request an OAuth token for the %s user' %
            self.login_user)
        self.irc.queueMsg(
            ircmsgs.privmsg(
                msg.nick,
                "In order to access the %s event stream of %s as user %s an OAuth token is required." % (self.sub_type, self.target, self.login_user))) #noqa
        self.irc.queueMsg(
            ircmsgs.privmsg(
                msg.nick,
                "Login to github with the appropriate user, and click 'Create new token' on https://github.com/settings/applications")) #noqa
        self.irc.queueMsg(
            ircmsgs.privmsg(
                msg.nick,
                "Reply TO THIS PRIVATE MESSAGE with 'authorize %s <token>'" %
                self.login_user))

    def start_polling(self):
        self.api_session.headers['Authorization'] = 'token %s' % self.token
        logger.info("Starting GEA job %s" % self.job_name)
        schedule.addPeriodicEvent(
            self.fetch_updates,
            self.update_interval,
            now=True,
            name=self.job_name)

    def stop_polling(self):
        logger.info("Stopping GEA job %s" % self.job_name)
        try:
            schedule.removeEvent(self.job_name)
        except KeyError:
            logger.error('Attempted to stop nonexistant GEA job: %s' %
                         self.job_name)

    def fetch_updates(self):
        r = self.api_session.get(self.url)
# Way chatty
#        logger.debug("Request headers")
#        logger.debug(pp.pformat(self.api_session.headers))
#        logger.debug("Response headers")
#        logger.debug(pp.pformat(r.headers))

        if r.ok:
            if 'etag' in r.headers:
                # Update ETag to keep position
                self.api_session.headers['If-None-Match'] = r.headers['etag']
            # Handle updates
            self.announce_updates(r.json)
        elif r.status_code == 304:
            # No updates since last fetch
            return
        else:
            err = 'Unable to retrieve updates for %s, error: %s (%s)' % (
                self, r.text, r.reason)
            logger.error('GEA: %s' % err)
            msg = ircmsgs.privmsg(self.subscriptions.channel, err)
            self.irc.queueMsg(msg)

    def announce_updates(self, updates):
        '''Takes list of Event updates from GitHub, handles or discards event
            as configured'''
        sa = SubscriptionAnnouncer()

        # requests made .json a callable instead of an attr in 1.0.0
        if hasattr(updates, '__call__'):
            updates = updates()

        updates = sorted(updates, key=lambda x: x['created_at'])

        for event in updates:
            #logger.debug(pp.pformat(event))
            #logger.debug("Saw a %s event" % event['type'])
            if 'created_at' in event:
                #logger.debug("** Got created at %s" % event['created_at'])
                e_dt = datetime.datetime.strptime(
                    event['created_at'],
                    '%Y-%m-%dT%H:%M:%SZ')
                if e_dt > self.latest_event_dt:
                    self.latest_event_dt = e_dt
                    try:
                        f = getattr(SubscriptionAnnouncer, event['type'])
                        f(sa, self, event)
                    except AttributeError:
                        logger.error("Unhandled event type %s" % event['type'])


class SubscriptionAnnouncer:

#   def __init__():
#       self.maxcommits = 5

    def CreateEvent(self, sub, e):

        (a, p, r) = self._mkdicts('apr', e)

        try:
            if e['payload']['ref_type'] == 'repository':
                msg = "%s created new repository %s" % (a['login'], r['name'])
            else:
                msg = "[%s] %s created new %s '%s'" % \
                    (r['name'], a['login'], p['ref_type'], p['ref'])
        except KeyError as err:
            logger.info("Got KeyError in CreateEvent: %s" % err)
            logger.info(e)
            msg = "GEA: Failed to parse event"

        qmsg = ircmsgs.privmsg(sub.channel, msg)
        sub.irc.queueMsg(qmsg)

    def PullRequestEvent(self, sub, e):

        (a, p, r) = self._mkdicts('apr', e)
        pr = p['pull_request']

        # TODO display closing comment if available
        try:
            msg = "[%s] %s %s pull request \"%s\" (%s)" % \
                (r['name'], a['login'], p['action'].upper(), pr['title'],
                 pr['_links']['html']['href'])
        except KeyError as err:
            logger.error("Got KeyError in PullRequestEvent: %s" % err)
            msg = "GEA: Failed to parse event"

        qmsg = ircmsgs.privmsg(sub.channel, msg)
        sub.irc.queueMsg(qmsg)

    def PushEvent(self, sub, e):
        # Meh, just spam
        # Scratch that, now broken
        # TODO was it broken? or was it due to screen being in copy mode for
        # that process?
        return

        global pp
        logger.debug(pp.pformat(e))
        (a, p, r) = self._mkdicts('apr', e)

        try:
            msg = "%s pushed %d commits to %s:" % \
                (a['login'], p['size'], r['name'])
        except KeyError as err:
            logger.error("Got KeyError: %s" % err)
            logger.debug(p)
            msg = "GEA: Failed to parse event"

        qmsg = ircmsgs.privmsg(sub.channel, msg)
        sub.irc.queueMsg(qmsg)

        # Print shortlogs for commits
        commits = p['commits'].reverse()
        for i in xrange(1, self.maxcommits):
            commit = commits.pop()
            qmsg = "[%s] %s" % (commit.sha[0:7], commit.message)
            sub.irc.queueMsg(qmsg)

    def _mkdicts(self, flags, event):
        mapping = {'a': 'actor', 'p': 'payload', 'r': 'repo'}
        dicts = []
        for c in str(flags):
            if c in mapping:
                dicts.append(event[mapping[c]])
        return dicts
