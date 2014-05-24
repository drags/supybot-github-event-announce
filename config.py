import supybot.conf as conf
import supybot.registry as registry


def configure(advanced):
    # This will be called by supybot to configure this module.  advanced is
    # a bool that specifies whether the user identified himself as an advanced
    # user or not.  You should effect your configuration by manipulating the
    # registry as appropriate.
    from supybot.questions import expect, anything, something, yn
    conf.registerPlugin('GitEventAnnounce', True)

GitEventAnnounce = conf.registerPlugin('GitEventAnnounce')

conf.registerChannelValue(GitEventAnnounce, 'announceCreateEvents',
                          registry.Boolean(True, 'Announce Create events'))

conf.registerChannelValue(GitEventAnnounce, 'announceDeleteEvents',
                          registry.Boolean(True, 'Announce Delete events'))

conf.registerChannelValue(GitEventAnnounce, 'announcePushEvents',
                          registry.Boolean(True, 'Announce Push events'))

conf.registerChannelValue(GitEventAnnounce, 'announcePullRequestEvents',
                          registry.Boolean(True, 'Announce PullRequest events'))

conf.registerChannelValue(GitEventAnnounce, 'announceIssuesEvents',
                          registry.Boolean(True, 'Announce Issues events'))

conf.registerChannelValue(GitEventAnnounce, 'announceIssueCommentEvents',
                          registry.Boolean(True, 'Announce IssueComment events'))

conf.registerChannelValue(GitEventAnnounce, 'announceMemberEvents',
                          registry.Boolean(True, 'Announce Member events'))

conf.registerChannelValue(GitEventAnnounce, 'announceTeamAddEvents',
                          registry.Boolean(True, 'Announce TeamAdd events'))

conf.registerChannelValue(GitEventAnnounce, 'announceWatchEvents',
                          registry.Boolean(True, 'Announce Watch events'))

conf.registerChannelValue(GitEventAnnounce, 'silence',
                         registry.Boolean(False, 'Disable all subscription announcements'))

# vim:set shiftwidth=4 tabstop=4 expandtab textwidth=79:
