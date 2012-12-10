# GithubEventAnnouncer

This plugin uses the Github v3 API to publish selected events to an IRC channel. The plugin can monitor individual repos, users, or entire organizations.

Example:

01:09 <tim> Botname: load GithubEventAnnounce
01:09 <tim> Botname: addsub login_user organization awesm
01:09 <@awesm-o> tim: Messaging you to authorize the drags account
<...authorize account..>
01:10 <@awesm-o> [awesm/shares-api] @drags created new branch 'tcs-fabfile' on awesm/shares-api
01:10 <@awesm-o> [awesm/likebutton] @seldo created new tag 'release-2012-12-06-1' on awesm/likebutton
01:10 <@awesm-o> [awesm/shares-api] @drags opened pull request "v0.1 fabfile for shares-api @bhiles" [https://github.com/awesm/shares-api/pull/4]
01:10 <@awesm-o> [awesm/likebutton] @seldo closed pull request "@seldo conversion api v2" [https://github.com/awesm/likebutton/pull/3]

