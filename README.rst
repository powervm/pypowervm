==========================================
pypowervm - Python API wrapper for PowerVM
==========================================

NOTE
----
pypowervm is under active development and is currently unstable.  The API is
being developed openly and a 1.0 version will be declared when it is mature.
Any versions under 1.0 are not supported in any form and should not be used
in production or development environments.

See the VERSION.rst for detailed information about current version.

Current versions should utilize the local authentication mechanism.  The remote
authentication mechanism is intended only for development and test purposes for
the time being.

Overview
--------
pypowervm provides a Python-based API wrapper for interaction with IBM
PowerVM-based systems.

License
-------
The library's license can be found in the LICENSE_ file.  It must be
reviewed prior to use.

.. _LICENSE: LICENSE

Project Structure
-----------------
- ``debian/``: Debian packaging metadata and controls.

- ``pypowervm/``: Project source code.

  - ``helpers/``: Decorator methods suitable for passing to the ``helpers``
    parameter of the ``pypowervm.adapter.Adapter`` initializer.

  - ``locale/``: Translated message files for internationalization (I18N).

  - ``tasks/``: Modules for performing complex tasks on PowerVM objects.

    - ``monitor/``: Modules for tasks specific to the PowerVM Performance and
      Capacity Monitoring (PCM) API.

  - ``tests/``: Functional and unit tests.  The directory and file structure
    mirrors that of the project code.  For example, tests for module
    ``pypowervm/wrappers/logical_partition.py`` can be found in
    ``pypowervm/tests/wrappers/test_logical_partition.py``.

    - ``data/``: Data files used by test cases.  These are generally XML dumps
      obtained from real PowerVM REST API servers, often via the utilities
      found in ``pypowervm/tests/test_utils/``.

    - ``helpers/``: Tests for modules under ``pypowervm/helpers/``.

    - ``locale/``: Directory structure containing sample
      internationalization (I18N) files for I18N testing.

    - ``tasks/``: Tests for modules under ``pypowervm/tasks/``.

      - ``monitor/``: Tests for modules under ``pypowervm/tasks/monitor/``.

    - ``test_utils/``: Utilities useful for test development and implementation.

    - ``utils/``: Tests for modules under ``pypowervm/utils/``.

    - ``wrappers/``: Tests for modules under ``pypowervm/wrappers/``.

      - ``pcm/``: Tests for modules under ``pypowervm/wrappers/pcm/``.

  - ``utils/``: Common helper utilities.

  - ``wrappers/``: Modules presenting intuitive hierarchical views and controls
    on PowerVM REST objects.  Simple operations involving getting or setting single,
    independent attributes on an object are handled by the wrappers defined here.

    - ``pcm/``: Wrapper modules specific to the PowerVM Performance and Capacity
      Monitoring (PCM) API.


Using Sonar
-----------

To enable sonar code scans through tox there are a few steps involved.

- Install sonar locally.  See:  http://www.sonarqube.org/downloads/

- Create a host mapping in /etc/hosts for the name 'sonar-server'. If the
  sonar server were on the local host then the entry might be::

    127.0.0.1  sonar-server

  Alternatively, you can set the environment variable SONAR_SERVER prior to
  invoking tox, to specify the server to use.

- The following environment variable must be set in order to log onto the
  sonar server::

    SONAR_USER
    SONAR_PASSWORD

  An example invocation::

  # SONAR_USER=user SONAR_PASSWORD=password tox -e sonar

- Sonar output is placed in::

    .sonar/

