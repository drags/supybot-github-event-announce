import supybot.conf as conf
import supybot.registry as registry


def configure(advanced):
    # This will be called by supybot to configure this module.  advanced is
    # a bool that specifies whether the user identified himself as an advanced
    # user or not.  You should effect your configuration by manipulating the
    # registry as appropriate.
    from supybot.questions import expect, anything, something, yn
    conf.registerPlugin('GitHubEventAnnounce', True)

GitHubEventAnnounce = conf.registerPlugin('GitHubEventAnnounce')

conf.registerChannelValue(GitHubEventAnnounce, 'announceCreateEvents',
                          registry.Boolean(True, 'Announce Create events'))

conf.registerChannelValue(GitHubEventAnnounce, 'announceDeleteEvents',
                          registry.Boolean(True, 'Announce Delete events'))

conf.registerChannelValue(GitHubEventAnnounce, 'announcePushEvents',
                          registry.Boolean(True, 'Announce Push events'))

conf.registerChannelValue(GitHubEventAnnounce, 'announcePullRequestEvents',
                          registry.Boolean(True, 'Announce PullRequest events'))

conf.registerChannelValue(GitHubEventAnnounce, 'announceIssuesEvents',
                          registry.Boolean(True, 'Announce Issues events'))

conf.registerChannelValue(GitHubEventAnnounce, 'announceIssueCommentEvents',
                          registry.Boolean(True, 'Announce IssueComment events'))

conf.registerChannelValue(GitHubEventAnnounce, 'announceMemberEvents',
                          registry.Boolean(True, 'Announce Member events'))

conf.registerChannelValue(GitHubEventAnnounce, 'announceTeamAddEvents',
                          registry.Boolean(True, 'Announce TeamAdd events'))

conf.registerChannelValue(GitHubEventAnnounce, 'announceWatchEvents',
                          registry.Boolean(True, 'Announce Watch events'))

conf.registerChannelValue(GitHubEventAnnounce, 'silence',
                         registry.Boolean(False, 'Disable all subscription announcements'))

# vim:set shiftwidth=4 tabstop=4 expandtab textwidth=79:
