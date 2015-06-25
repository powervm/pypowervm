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
pypowervm provides a Python based API wrapper for interaction with IBM
PowerVM based systems.

License
-------
The library's license can be found under the LICENSE file.  It must be
reviewed prior to use.

Using Sonar
-----------

To enable sonar code scans through tox there are a few steps involved.

-Install sonar locally.  See:  http://www.sonarqube.org/downloads/

-Create a host mapping in /etc/hosts for the name 'sonar-server'. If the
sonar server were on the local host then the entry might be:

127.0.0.1  sonar-server

Alternatively, you can set the environment variable SONAR_SERVER prior to
invoking tox, to specify the server to use.

-The following environment variable must be set in order to log onto the
sonar server:

  SONAR_USER
  SONAR_PASSWORD

An example invocation:
  >SONAR_USER=user SONAR_PASSWORD=password tox -e sonar

-Sonar output is placed in:
  .sonar/
