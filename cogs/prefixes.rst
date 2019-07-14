Prefixes
========

Handles all prefix related actions.

.. py:function:: prefix()

   Subcommand for all prefix related subcommands.
   Called without a subcommand, views all prefixes
   for this guild.

.. py:function:: prefix add(*prefixes)

   Adds prefixes to the available guild prefixes.
   Extraneous whitespace will be stripped.
   "thing " will become "thing"

   :param *prefixes: A list of prefixes to add. Must be split by a single space.
      To add a prefix with a space in it, use quotes, e.g.
      ``prefix add "foo bar"``

.. py:function:: prefix remove(*prefixes)

   Removes prefixes available to the server.
   Will silently ignore unknown prefixes.
   Invoke the prefix command with no subcommand to see all
   available prefixes. You cannot remove the @mentions.

   :param *prefixes: A list of prefixes to remove. Must be split by a single space.
      To remove a prefix with a space in it, use quotes, e.g.
      ``prefix remove "foo bar"``
