==========================================
pypowervm - Python API wrapper for PowerVM
==========================================

NOTE
----
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


Developer Notes
---------------

- The property ``pypowervm.base_partition.IOSlot.adapter`` is deprecated and
  will be removed no sooner than January 1st, 2017.  It has been replaced by
  the ``pypowervm.base_partition.IOSlot.io_adapter`` property.  Removal will
  break compatibility with PowerVC 1.3.0.0 and 1.3.0.1.  The issue is resolved
  as of PowerVC 1.3.0.2.

- The ``xag`` argument to the ``pypowervm.wrappers.entry_wrapper.EntryWrapper.update``
  method is deprecated and will be removed no sooner than January 1st, 2017.

- The ``xags`` member of the ``pypowervm.wrappers.virtual_io_server.VIOS``
  class is deprecated and will be removed no sooner than January 1st, 2017.
  Please use the members of ``pypowervm.const.XAG`` instead.

- Remote Restart in a NovaLink environment is handled by the consuming
  management layer, not by NovaLink itself.  As such, the properties
  ``rr_enabled`` and ``rr_state`` of ``pypowervm.wrappers.logical_partition.LPAR``
  should not be used.  These properties are now deprecated and will be removed
  no sooner than January 1st, 2017.  Use the ``srr_enabled`` property instead.

- The method ``pypowervm.tasks.storage.crt_lu_linked_clone`` is deprecated and
  will be removed no sooner than January 1st, 2017.  You should now use the
  ``pypowervm.tasks.storage.crt_lu`` method to create a linked clone by passing
  the source image LU wrapper via the ``clone`` parameter.

- The Adapter cache is removed as of release 1.0.0.4.  Attempting to
  create an Adapter with ``use_cache=True`` will result in a
  ``CacheNotSupportedException``.

- The property ``pypowervm.wrappers.managed_system.IOSlot.pci_sub_dev_id`` is
  deprecated and will be removed no sooner than January 1st, 2019. It has been
  replaced by the ``pypowervm.wrappers.managed_system.IOSlot.pci_subsys_dev_id``
  property.

- The property ``pypowervm.wrappers.managed_system.IOSlot.pci_revision_id`` is
  deprecated and will be removed no sooner than January 1st, 2019. It has been
  replaced by the ``pypowervm.wrappers.managed_system.IOSlot.pci_rev_id``
  property.

- The property ``pypowervm.wrappers.managed_system.IOSlot.pci_sub_vendor_id`` is
  deprecated and will be removed no sooner than January 1st, 2019. It has been
  replaced by the ``pypowervm.wrappers.managed_system.IOSlot.pci_subsys_vendor_id``
  property.

- The property ``pypowervm.wrappers.managed_system.IOSlot.dyn_reconfig_conn_index``
  is deprecated and will be removed no sooner than January 1st, 2019. It has
  been replaced by the ``pypowervm.wrappers.managed_system.IOSlot.drc_index``
  property.

- The property ``pypowervm.wrappers.managed_system.IOSlot.dyn_reconfig_conn_name``
  is deprecated and will be removed no sooner than January 1st, 2019. It has been
  replaced by the ``pypowervm.wrappers.managed_system.IOSlot.drc_name``
  property.

- Passing an arbitrary dictionary into the add_parms argument of
  ``pypowervm.tasks.power.power_on`` and ``power_off`` is deprecated.  Consumers
  should migrate to using ``pypowervm.tasks.power_opts.PowerOnOpts`` and
  ``PowerOffOpts`` instead.

- The ``pypowervm.tasks.power.power_off`` method is deprecated and will be
  removed no sooner than January 1st, 2019.  Consumers should migrate to using
  ``pypowervm.tasks.power.PowerOp.stop`` for single power-off; or
  ``pypowervm.tasks.power.power_off_progressive`` for soft-retry flows.
