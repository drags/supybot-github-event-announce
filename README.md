# GitHub Event Announce

This SupyBot plugin scrapes GitHub API [event streams](https://developer.github.com/v3/activity/events/) and announces [events](https://developer.github.com/v3/activity/events/types/) to IRC channel(s) where a supybot is present. Initially created to track a small GitHub *organization* (~100 repos); it supports tracking single repositories, all repositories for a given user, or all repositories for an entire organization.

Since this plugin utilizes GitHub event streams numerous repositories can be tracked without being resource intensive. GitHub takes care of bundling the repositories into a single stream (using `user` or `organization` event streams), and use of Etags very little network or GitHub rate-limit impact.

By default this plugin is very chatty. One of the most verbose event types is 'PushEvents'. These events get sent for every batch of commits pushed into GitHub. If they're polluting the signal to noise ratio, disable them (for the current channel) with: `config channel plugins.GitHubEventAnnounce.announcePushEvents false`. Remove the `channel` keyword from that command to disable them globally.

## Using

To get started, copy this plugin to the 'plugins' directory of your supybot's home directory (by default ~/.supybot) and rename the directory: `GitHubEventAnnounce`. Load the plugin via the bot with `/msg MyBot load GitHubEventAnnounce`. Configuring the plugin requires at least the **admin** capability.

GitHub has both public and private event streams. Private events are events that occur on private repositories. If you do not specify the **private** keyword when adding a subscription then it will default to a public subscription. Be sure to use (or not use) the same keyword when deleting a subscription, otherwise the sub to delete will not be found.

Add a subscription. Subscriptions are per channel, issue these commands in the destination channel:

	addsub github_user repository <target_repo_owner>/<target_repo> [public|private]
	addsub github_user user <target_user> [public|private]
	addsub github_user organization <target_organization> [public|private]

Public subscriptions will start immediately. For private subscriptions: if the GitHub user is already known then the token for that user will be re-used. If the GitHub user was not already known a new token will need to be entered. See [Creating Github tokens](#Creating_Github_tokens) for instructions on creating tokens.

Once the subscription has started events will begin to flow into the channel starting with the lastest 10 for that event stream. After that the event stream will be checked every 60s and new events announced in chronological order.

	<SupyBot> drags: Adding new subscription [repository] github_user@https://api.github.com/repos/drags/supybot-github-event-announce/events
	<SupyBot> drags created new repository drags/supybot-github-event-announce
	<SupyBot> [drags/supybot-github-event-announce] drags created new branch 'user_supplied_oauth'
	<SupyBot> [drags/supybot-github-event-announce] commit: 75d597db - Markdown [Tim Sogard]
	<SupyBot> [drags/supybot-github-event-announce] @sigmavirus24 starred repository drags/supybot-github-event-announce
	<SupyBot> [drags/supybot-github-event-announce] commit: dfc7e355 - Enable per channel message type filtering [Tim Sogard]
	<SupyBot> [drags/supybot-github-event-announce] awesm-o CLOSED pull request "Add WatchEvents" (https://github.com/drags/supybot-github-event-announce/pull/8)

To delete a subscription send the bot a `delsub` command, using the same arguments that added the subscription:

	delsub github_user repository <target_repo_owner>/<target_repo> [public|private]

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

Event types not currently supported, roughly in order of priority:

	- ForkEvent - When a repository is forked
	- ReleaseEvent - When a release is published
	- PullRequestCommentEvent - Comments on a pull request diff
	- PublicEvent - From the GitHub API docs: "Triggered when a private repository is open sourced. Without a doubt: the best GitHub event."
	- PageBuildEvent - Only used to trigger hooks
	- DeploymentEvent - Only used to trigger hooks
	- DownloadEvent - Events are no longer being created, historical at this point.
	- FollowEvent - Events are no longer created, historical at this point.

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
