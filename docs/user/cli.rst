.. _cli:

Command-line Interface (CLI)
=============================

pytubefix also ships with a tiny CLI for interacting with videos and playlists.

To download the highest resolution progressive stream:

.. code:: bash

    $ pytubefix https://www.youtube.com/watch?v=2lAe1cqCOXo

To view available streams:

.. code:: bash

    $ pytubefix https://www.youtube.com/watch?v=2lAe1cqCOXo --list

To download a specific stream, use the itag

.. code:: bash

    $ pytubefix https://www.youtube.com/watch?v=2lAe1cqCOXo --itag=22

To get a list of all subtitles (caption codes)

.. code:: bash

    $ pytubefix https://www.youtube.com/watch?v=2lAe1cqCOXo --list-captions

To download a specific subtitle (caption code) - in this case the
English subtitles (in srt format) - use:

.. code:: bash

    $ pytubefix https://www.youtube.com/watch?v=2lAe1cqCOXo -c en

It is also possible to just download the audio stream (default AAC/mp4):

.. code:: bash

    $ pytubefix https://www.youtube.com/watch?v=2lAe1cqCOXo -a

To list all command line options, simply type

.. code:: bash

    $ pytubefix --help

See version

.. code:: bash

    $ pytubefix -V


Finally, if you're filing a bug report, the cli contains a switch called
``--build-playback-report``, which bundles up the state, allowing others
to easily replay your issue.
