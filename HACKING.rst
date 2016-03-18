PyPowerVM Style Commandments
===============================
We generally follow the guidelines set out by the OpenStack community. We've
found them helpful in our development of PyPowerVM.

- Step 1: Read the OpenStack Style Commandments
  http://docs.openstack.org/developer/hacking/
- Step 2: Read on

PyPowerVM Specific Commandments
----------------------------------

- [P301] LOG.warn() is not allowed. Use LOG.warning()

Creating Unit Tests
-------------------
For every new feature, unit tests should be created that both test and
(implicitly) document the usage of said feature. If submitting a patch for a
bug that had no unit test, a new passing unit test should be added. If a
submitted bug fix does have a unit test, be sure to add a new one that fails
without the patch and passes with the patch.
