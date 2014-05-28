###
# Pickup service announcements,
###

"""
Exposes an HTTP server, accepts posts, transforms to IRC msgs
"""

import supybot
import supybot.world as world

# Use this for the version of this plugin.  You may wish to put a CVS keyword
# in here if you're keeping the plugin in CVS or some similar system.
__version__ = "0.4.0"

# Replace this with an appropriate author or supybot.Author instance.
__author__ = supybot.Author('Tim Sogard', 'drags', 'tim@awe.sm')

# This is a dictionary mapping supybot.Author instances to lists of
# contributions.
__contributors__ = {}

# This is a url where the most recent plugin package can be downloaded.
__url__ = 'http://github.com/drags/supybot-github-event-announce'

import config
import plugin
reload(plugin) # In case we're being reloaded.
# Add more reloads here if you add third-party modules and want them to be
# reloaded when this plugin is reloaded.  Don't forget to import them as well!

if world.testing:
    import test

Class = plugin.Class
configure = config.configure


# vim:set shiftwidth=4 tabstop=4 expandtab textwidth=79:
