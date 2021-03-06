####################################
# Github Event Announcer
#
# Because the firehose is delicious.
####################################
# system
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
import sys

# Import requests gracefully
try:
    import requests
except ImportError:
    raise callbacks.Error('GitHubEventAnnounce requires the python requests library. Install it via `pip`, `easy_install`, or from http://docs.python-requests.org/en/latest/user/install/#install') #noqa

# debug
import pprint
pp = pprint.PrettyPrinter(indent=4)

# logs
logger = logging.getLogger('supybot')


class GitHubEventAnnounce(callbacks.Plugin):

    '''Github Event Announcer: Announce the public or private event stream to
        an IRC channel'''
    threaded = True

    def __init__(self, irc):
        self.__parent = super(GitHubEventAnnounce, self)
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
                logger.error('Got error %s' % e)
                return False
            for (name, sub) in sub_data.items():
                channels = [str(x) for x in sub['channels']]
                new_sub = Subscription(irc, channels, str(sub['login_user']),
                                       str(sub['sub_type']),
                                       str(sub['target']),
                                       str(sub['privacy_type']))
                # Restore token, etag, last seen
                new_sub.api_session.headers['If-None-Match'] = sub['etag']
                if sub['privacy_type'] == 'private':
                    new_sub.set_token(sub['token'])
                latest_event_dt = \
                    datetime.datetime.fromtimestamp(sub['latest_event'])
                new_sub.latest_event_dt = latest_event_dt

                # Start job
                self._start_sub(new_sub)

        # Rebuild authorizations table
        for (name, sub) in self.subscriptions.items():
            if sub.login_user not in self.authorizations and \
                    sub.privacy_type == 'private':
                self.authorizations[sub.login_user] = sub.token

    def savesubs(self):
        sub_data = {}
        for (name, sub) in self.subscriptions.items():
            sub_data[name] = {
                'name': name,
                'channels': sub.channels,
                'login_user': sub.login_user,
                'sub_type': sub.sub_type,
                'target': sub.target,
                'token': sub.token,
                'url': sub.url,
                'job_name': sub.job_name,
                'etag': sub.api_session.headers.get('If-None-Match', ''),
                'latest_event': int(sub.latest_event_dt.strftime('%s')),
                'privacy_type': sub.privacy_type
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

    def addsub(self, irc, msg, args, login_user, sub_type, target,
               privacy_type):
        '''<github_user> <subscription type> <target> [public|private]

        Adds an event stream subscription. Privacy type defaults to 'public'
        '''
        if not self._check_sub_args(irc, privacy_type, login_user, sub_type,
                                    target):
            return

        channel = msg.args[0]
        try:
            sub = Subscription(irc, [channel], login_user, sub_type, target,
                               privacy_type)
        except ValueError:
            # assume anything that raises a valueerror will reply on its own
            # TODO bad assuming
            return
        if str(sub) in self.subscriptions:
            if channel in self.subscriptions[str(sub)].channels:
                irc.reply('The subscription %s already exists on channel %s' %
                          (sub, channel))
                return
            else:
                irc.reply('Adding channel %s to existing subscription' %
                          (channel))
                self.subscriptions[str(sub)].channels.append(channel)
                return
        self.pending_subscriptions[str(sub)] = sub

        irc.reply('Adding new subscription %s' % (sub))

        if privacy_type == 'private':
            if login_user in self.authorizations:
                self._auth_with_token(login_user,
                                      self.authorizations[login_user])
            else:
                sub._authorize(msg)
        else:
            self._start_sub(sub)
    addsub = wrap(addsub, [('checkCapability', 'admin'),
                           'somethingWithoutSpaces', 'somethingWithoutSpaces',
                           'somethingWithoutSpaces',
                           optional('somethingWithoutSpaces',
                                    default='public'),
                           ]
                  )

    def delsub(self, irc, msg, args, login_user, sub_type, target,
               privacy_type):
        '''<github_user> <subscription type> <target> [public|private]

        Deletes a known subscription. Privacy type defaults to 'public'
        '''
        if not self._check_sub_args(irc, privacy_type, login_user, sub_type,
                                    target):
            return

        # create temp sub to match on __str__
        channel = msg.args[0]
        try:
            sub_to_delete = Subscription(irc, [channel], login_user, sub_type,
                                         target, privacy_type)
        except ValueError:
            # assume anything that raises a valueerror will reply on its own
            # TODO bad assuming
            return

        sub_found = False
        for sub_list in [self.subscriptions, self.pending_subscriptions]:
            if str(sub_to_delete) in sub_list:
                mysub = sub_list[str(sub_to_delete)]
                if channel in mysub.channels:
                    sub_found = True
                    irc.reply('Removing subscription %s from channel %s' %
                              (sub_to_delete, channel))
                    mysub.channels.remove(channel)
                    if len(mysub.channels) < 1:
                        mysub.stop_polling()
                        del(sub_list[str(sub_to_delete)])

        if sub_found is False:
            irc.reply('Sub %s was not found.' % sub_to_delete)

        # cleanup self.authorizations if GitHub user's last subscription
        self.cleanup_auths(login_user)
    delsub = wrap(delsub, [('checkCapability', 'admin'),
                           'somethingWithoutSpaces', 'somethingWithoutSpaces',
                           'somethingWithoutSpaces',
                           optional('somethingWithoutSpaces',
                                    default='public'),
                           ]
                  )

    def cleanup_auths(self, login_user):
        '''Delete tokens for GitHub users having <1 subscriptions'''
        if login_user == 'public':
            return True

        if filter(lambda x: x.login_user == login_user,
                  self.subscriptions.values()) == []:
            try:
                del(self.authorizations[login_user])
            except KeyError:
                logger.error(
                    'Tried to delete non-existant authorizations entry for %s'
                    % login_user)

    def authorize(self, irc, msg, args, username, token):
        '''Accept an OAuth token'''
        self._auth_with_token(username, token)
    authorize = wrap(authorize, ['somethingWithoutSpaces',
                                 'somethingWithoutSpaces', 'private'])

    def _auth_with_token(self, username, token):
        '''Finish OAuth handshake and init job'''
        # TODO test if token works/ has acceptable scope
        for (name, sub) in self.pending_subscriptions.items():
            if sub.login_user == username:
                sub.set_token(token)
                self._start_sub(sub)

        # Add/update token to known token list
        self.authorizations[username] = token

    def _start_sub(self, sub):
        if sub.validate_sub():
            sub.start_polling()
            name = str(sub)
            self.subscriptions[name] = sub
            if name in self.pending_subscriptions:
                del(self.pending_subscriptions[name])
        else:
            return False

    def _check_sub_args(self, irc, privacy_type, login_user, sub_type, target):
        if sub_type not in Subscription.sub_types:
            known_types = ', '.join(Subscription.sub_types.keys())
            irc.reply('Unknown subscription type: %s' % (sub_type))
            irc.reply('Subscription type should be one of: %s' % (known_types))
            return False
        if privacy_type not in Subscription.privacy_types:
            irc.reply('Unknown privacy type: %s' % (privacy_type))
            irc.reply('Privacy type should be one of: %s' %
                      (Subscription.privacy_types))
            return False
        return True

    def listsubs(self, irc, msg, args, channel):
        '''List known subscriptions'''
        if len(self.subscriptions) > 0:
            irc.reply("Active subscriptions:")
            for (name, sub) in self.subscriptions.items():
                if channel in sub.channels:
                    irc.reply(name)
        else:
            irc.reply('No active subscriptions')
        if len(self.pending_subscriptions) > 0:
            irc.reply("Pending subscriptions:")
            for (name, sub) in self.pending_subscriptions.items():
                if channel in sub.channels:
                    irc.reply(name)
    listsubs = wrap(listsubs, ['channel'])

Class = GitHubEventAnnounce


class Subscription(object):
    sub_types = {
        'user':
        {'private': 'https://api.github.com/users/%(target)s/events',
         'public': 'https://api.github.com/users/%(target)s/events/public', #noqa
         },
        'repository':
        {'private':
         'https://api.github.com/repos/%(target_user)s/%(target_repo)s/events',
         'public':
         'https://api.github.com/repos/%(target_user)s/%(target_repo)s/events',
         },
        'organization':
        {'private':
         'https://api.github.com/users/%(login_user)s/events/orgs/%(target)s',
         'public': 'https://api.github.com/orgs/%(target)s/events',
         }
    }

    privacy_types = ['private', 'public']

    update_interval = 60
    minimum_update_interval = 60

    def __init__(self, irc, channels, login_user, sub_type, target,
                 privacy_type):
        if sub_type == 'repository':
            if target.find('/') == -1:
                irc.reply(
                    'For repositories the target must be in the form <username>/<repo>') #noqa
                raise ValueError('Failed to split target') #noqa
            (target_user, target_repo) = target.split('/')

        url = str(Subscription.sub_types[sub_type][privacy_type]) % locals()
        self.irc = irc
        self.channels = channels
        if privacy_type == 'private':
            self.login_user = login_user
        else:
            self.login_user = 'public'
        self.sub_type = sub_type
        self.privacy_type = privacy_type
        self.target = target
        self.url = url
        self.api_session = requests.Session()
        self.api_session.headers['content-type'] = 'application/json'
        self.api_session.headers['user-agent'] = 'Supybot-GithubEventAnnounce 0.4' #noqa
        self.latest_event_dt = datetime.datetime(1970, 1, 1)
        self.job_name = 'poll-%s' % str(self)
        self.token = ''  # placeholder token for saving/loading

    def __str__(self):
        '''[type] user@url'''
        return "[%s] %s@%s" % (self.sub_type, self.login_user, self.url)

    def validate_sub(self):
        r = self.api_session.get(self.url)
        if not r.ok:
            emsg = "Failed to load %s. Got error code: %d, msg: %s" % \
                (self, r.status_code, r.reason)
            self.irc.reply(emsg)
            #raise ValueError(emsg) # why raise here?
        return r.ok

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
                "Login to github as @%s, and generate a new 'Personal access token' on https://github.com/settings/applications" % (self.login_user))) #noqa
        self.irc.queueMsg(
            ircmsgs.privmsg(
                msg.nick,
                "Reply TO THIS PRIVATE MESSAGE with 'authorize %s <token>'" %
                self.login_user))

    def set_token(self, token):
        self.token = token
        self.api_session.headers['Authorization'] = 'token %s' % token

    def start_polling(self):
        logger.info("Starting GEA job %s" % self.job_name)
        self.fetch_updates(count=10)
        schedule.addPeriodicEvent(
            self.fetch_updates,
            self.update_interval,
            now=False,
            name=self.job_name)

    def stop_polling(self):
        logger.info("Stopping GEA job %s" % self.job_name)
        try:
            schedule.removeEvent(self.job_name)
        except KeyError:
            logger.error('Attempted to stop nonexistant GEA job: %s' %
                         self.job_name)

    def fetch_updates(self, count=None):
        r = self.api_session.get(self.url)
        # Way chatty
        # logger.debug("Request headers")
        # logger.debug(pp.pformat(self.api_session.headers))
        # logger.debug("Response headers")
        # logger.debug(pp.pformat(r.headers))

        if r.status_code == 304:
            # No updates since last fetch
            return
        elif r.ok:
            if 'etag' in r.headers:
                # Update ETag to keep position
                self.api_session.headers['If-None-Match'] = r.headers['etag']
            # Handle updates
            self.announce_updates(updates=r.json, count=count)
        else:
            err = 'Unable to retrieve updates for %s, error: %s (%s)' % (
                self, r.text, r.reason)
            logger.error('GEA: %s' % err)
            for ch in self.channels:
                msg = ircmsgs.privmsg(ch, err)
                self.irc.queueMsg(msg)

    def announce_updates(self, updates, count=None):
        '''Takes list of Event updates from GitHub, handles or discards event
            as configured'''
        sa = SubscriptionAnnouncer()

        # requests made .json a callable instead of an attr in 1.0.0
        if hasattr(updates, '__call__'):
            updates = updates()

        # TODO filter public==True for public subs
        updates = sorted(updates, key=lambda x: x['created_at'])
        if count is not None:
            updates = updates[-count:]

        for event in updates:
            #logger.debug(pp.pformat(event))
            #logger.debug("Saw a %s event" % event['type'])
            #logger.debug("** Got created at %s" % event['created_at'])
            e_dt = datetime.datetime.strptime(
                event['created_at'],
                '%Y-%m-%dT%H:%M:%SZ')
            if e_dt > self.latest_event_dt:
                self.latest_event_dt = e_dt
                try:
                    f = getattr(SubscriptionAnnouncer, event['type'])
                except AttributeError:
                    logger.error("Unhandled event type %s" % event['type'])
                    continue
                f(sa, self, event)


class SubscriptionAnnouncer:

    def CreateEvent(self, sub, e):
        (a, p, r) = self._mkdicts('apr', e)

        try:
            if p['ref_type'] == 'repository':
                msg = "%s created new repository %s" % (a['login'], r['name'])
            else:
                msg = "[%s] %s created new %s '%s'" % \
                    (r['name'], a['login'], p['ref_type'], p['ref'])
        except KeyError as err:
            logger.info("Got KeyError in CreateEvent: %s" % err)
            logger.info(e)
            msg = "GEA: Failed to parse event"
        self._send_messages(sub, msg, 'CreateEvent')

    def DeleteEvent(self, sub, e):
        (a, p, r) = self._mkdicts('apr', e)

        try:
            if p['ref_type'] == 'repository':
                msg = "%s deleted repository %s" % (a['login'], r['name'])
            else:
                msg = "[%s] %s deleted %s '%s'" % \
                    (r['name'], a['login'], p['ref_type'], p['ref'])
        except KeyError as err:
            logger.info("Got KeyError in DeleteEvent: %s" % err)
            logger.info(e)
            msg = "GEA: Failed to parse event"
        self._send_messages(sub, msg, 'DeleteEvent')

    def PushEvent(self, sub, e):
        (a, p, r) = self._mkdicts('apr', e)
        # Print summary if >1 commit
        if p['size'] > 1:
            try:
                msg = "%s pushed %d commits to %s:" % \
                    (a['login'], p['size'], r['name'])
            except KeyError as err:
                logger.error("Got KeyError in PushEvent: %s" % err)
                msg = "GEA: Failed to parse event"
                return
            self._send_messages(sub, msg, 'PushEvent')

        # Print shortlogs for commits
        commits = p['commits']
        commits.reverse()

        for i in xrange(min(len(commits), 5)):
            commit = commits.pop()
            commit_msg = commit['message'].split('\n')[0][0:50]
            qmsg = "[%s] commit: %s - %s [%s]" % \
                (r['name'], commit['sha'][0:8], commit_msg,
                 commit['author']['name'])
            self._send_messages(sub, qmsg, 'PushEvent')

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
        self._send_messages(sub, msg, 'PullRequestEvent')

    def IssuesEvent(self, sub, e):
        (a, p, r) = self._mkdicts('apr', e)
        i = p['issue']
        try:
            msg = "[%s] %s %s issue \"%s\" [%s]" % (r['name'], a['login'],
                                                    p['action'].upper(),
                                                    i['title'], i['html_url'])
        except KeyError as err:
            logger.error("Got KeyError in IssuesEvent: %s" % err)
            msg = "GEA: Failed to parse event"
        self._send_messages(sub, msg, 'IssuesEvent')

    def IssueCommentEvent(self, sub, e):
        (a, p, r) = self._mkdicts('apr', e)
        i = p['issue']
        c = p['comment']
        first_line = c['body'].split('\n')[0][0:100]
        try:
            msg = '[%s] %s commented on %s "%s"' % \
                (r['name'], c['user']['login'], i['html_url'], first_line)
        except KeyError as err:
            logger.error("Got KeyError in IssueCommentEvent: %s" % err)
            msg = "GEA: Failed to parse event"
        self._send_messages(sub, msg, 'IssueCommentEvent')

    def MemberEvent(self, sub, e):
        (a, p, r) = self._mkdicts('apr', e)
        try:
            msg = '[%s] %s %s collaborator %s' % \
                (r['name'], a['login'], p['action'], p['member']['login'])
        except KeyError as err:
            logger.error("Got KeyError in MemberEvent: %s" % err)
            msg = "GEA: Failed to parse event"
        self._send_messages(sub, msg, 'MemberEvent')

    def TeamAddEvent(self, sub, e):
        (a, p, r) = self._mkdicts('apr', e)
        if 'repository' in p:
            type = 'repository'
            # Using shortname (not including owner) since it should always be
            # the organization that the team belongs to
            target = p['repository']['name']
        elif 'user' in p:
            type = 'user'
            target = p['user']['login']
        else:
            logger.error('Did not find user or repository within TeamAddEvent')
            return

        try:
            msg = '[org: %s] %s %s added to team %s' % \
                (e['org']['login'], type, target, p['team']['name'])
        except KeyError as err:
            logger.error("Got KeyError in TeamAddEvent: %s" % err)
            msg = "GEA: Failed to parse event"
        self._send_messages(sub, msg, 'TeamAddEvent')

    def WatchEvent(self, sub, e):
        (a, p, r) = self._mkdicts('apr', e)
        try:
            msg = '[%s] @%s starred repository %s' % \
                (r['name'], a['login'], r['name'])
        except KeyError as err:
            logger.error("Got KeyError in WatchEvent: %s" % err)
            msg = "GEA: Failed to parse event"
        self._send_messages(sub, msg, 'WatchEvent')

    def ForkEvent(self, sub, e):
        (a, p, r) = self._mkdicts('apr', e)
        try:
            msg = '@%s forked repository %s as %s' % \
                (a['login'], r['name'], p['forkee']['full_name'])
        except KeyError as err:
            logger.error("Got KeyError in ForkEvent: %s" % err)
            msg = "GEA: Failed to parse event"
        self._send_messages(sub, msg, 'ForkEvent')

    def _send_messages(self, sub, msg, type):
        # Global silence
        if conf.get(conf.supybot.plugins.GitHubEventAnnounce.silence):
            return

        for chan in sub.channels:
            # See if we're under channel silence
            if conf.get(conf.supybot.plugins.GitHubEventAnnounce.silence, chan): #noqa
                return

            # Get config for event type in chan
            try:
                group = getattr(conf.supybot.plugins.GitHubEventAnnounce,
                                'announce%ss' % (type))
            except:
                e = sys.exc_info()
                logger.error('Failed to get config group for type %s' % (type))
                logger.error(pp.pformat(e))
                group = None

            # Allow if conf missing
            if group is None:
                event_allowed = True
            else:
                event_allowed = conf.get(group, chan)

            # Send allowed events
            if event_allowed:
                qmsg = ircmsgs.privmsg(chan, msg)
                sub.irc.queueMsg(qmsg)

    def _mkdicts(self, flags, event):
        mapping = {'a': 'actor', 'p': 'payload', 'r': 'repo'}
        dicts = []
        for c in str(flags):
            if c in mapping:
                dicts.append(event[mapping[c]])
        return dicts
