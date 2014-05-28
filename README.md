# GitHub Event Announce

This SupyBot plugin scrapes GitHub API event streams and announces events to IRC channel(s). Event streams can be configured to track single repositories, entire users or entire organizations.

## Using

To get started, copy this plugin to the 'plugins' directory of your supybot's home directory (by default ~/.supybot). Load the plugin via the bot with `/msg MyBot load GitHubEventAnnounce`. Configuring the plugin requires at least the 'admin' capability.

Add a subscription. Subscriptions are per channel, issue these commands in the destination channel:

	<drags> SupyBot: addsub github_user repository drags/supybot-github-event-announce

The bot will ask you for a token for use in accessing the event stream. Be sure to send the token as a **private message** to the bot. Once the bot has a valid token for a GitHub user it will store and re-use that token for later subscriptions. The token will be forgotten once the last subscription is deleted for that GitHub user.

Events will begin flowing to the channel:

	<SupyBot> drags: Adding new subscription [repository] github_user@https://api.github.com/repos/drags/supybot-github-event-announce/events
	<SupyBot> drags created new repository drags/supybot-github-event-announce
	<SupyBot> [drags/supybot-github-event-announce] drags created new branch 'user_supplied_oauth'
	<SupyBot> [drags/supybot-github-event-announce] commit: 75d597db - Markdown [Tim Sogard]
	<SupyBot> [drags/supybot-github-event-announce] @sigmavirus24 starred repository drags/supybot-github-event-announce
	<SupyBot> [drags/supybot-github-event-announce] commit: dfc7e355 - Enable per channel message type filtering [Tim Sogard]


## Types of events announced

Currently this plugin understands the following event types:

	- CreateEvent: A new repository, branch, or tag is created.
	- DeleteEvent: A repository, branch, or tag is deleted.
	- PushEvent: Commits are pushed to a repository.
	- PullRequestEvent: A pull request is created, changes status, or is closed.
	- IssuesEvent: An issue is created, changes status, or is closed.
	- IssueCommentEvent: A comment is added to an issue or pull request.
	- MemberEvent: A user is added as a repository collaborator.
	- TeamAddEvent: A user or repository is added to a team.
	- WatchEvent: A repository is starred. (No, really: https://developer.github.com/changes/2012-9-5-watcher-api/)

Event types not currently supported:

	- PullRequestCommentEvent - Comments on a pull request diff
	- PublicEvent - From the GitHub API docs: "Triggered when a private repository is open sourced. Without a doubt: the best GitHub event."



## Creating GitHub tokens

To create a GitHub API token:

	- login to GitHub as the user the plugin should access GitHub as
	- Go to https://github.com/settings/applications
	- Click 'Generate new token'
	- When the bot asks for a token reply in a private message, ex: `/msg MyBot authorize MyGitHubUser abcdef0987654321abcdef0987654321`

## Security concerns

The plugin relies on a valid GitHub API token to function. These tokens are managed via the [GitHub settings page](https://github.com/settings/applications) under "Personal Access Tokens". By default the token allows for read & write access to repository commit data. There is no read-only access level that still allows access to private data.

The tokens are stored in one place on disk, inside the 'data' directory of your Supybot's home directory (~/.supybot by default). Therefor, anyone with access to Supybot's home directory will have access to this token.

Tokens for each GitHub user are stored as long as a single subscription remains using that GitHub user. After a user has been authorized the token will be re-used for other subscriptions using that GitHub user. Once no more subscriptions exist for a given GitHub user that token will be forgotten.

**Note**: When enabling access to a large organization: consider creating a separate github user and placing them on a new team within the organization. Be sure to remove them from the default 'non-owners' team that usually has access to all repositories. Once this is setup you can select exactly which repositories that team has access to (useful to segregate bot responsibilities and keep private data private).

## Config
The bot has channel-level configuration for the silencing of all event types. This allows controlling (for all subscriptions within a channel) which type of events get announced. **Be aware** that in order to change a configuration variable for **just the current channel** in Supybot, the 'config' command must be given the 'channel' keyword, for example:

	config channel plugins.GithubEventAnnounce.announcePushEvents False

Without the 'channel' keyword the setting will be changed globally.

To see a list of the settings available for configuration have the bot list the plugin:

    <drags> SupyBot: search plugins.GithubEventAnnounce
