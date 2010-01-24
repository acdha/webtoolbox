.. program:: log_replay
.. _log_replay:

log_replay
----------
:synopsis: Replay webserver log files in realtime

If you need to replace webserver log files at something approximating
realtime, :program:`log_replay` is your friend. It uses Tornado's non-blocking
HTTP client to fetch all of the URLs but will sleep any time it's too far
ahead of the simulated virtual time.

.. cmdoption:: --help

   Display all available options and full help
