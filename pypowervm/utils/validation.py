# Copyright 2015 IBM Corp.
#
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

"""Extended validation utilities."""

import abc
import logging
import six

from pypowervm.i18n import _

LOG = logging.getLogger(__name__)


class ValidatorException(Exception):
    """Exceptions thrown from the validators."""
    pass


class LPARWrapperValidator(object):
    """LPAR Validator.

    This class implements additional validation for LPARs for use
    during resize or deployment.

    It is meant to catch any violations that would cause errors at
    the PowerVM management interface.

    """
    def __init__(self, lpar_w, mngd_sys, curr_lpar_w=None):
        """Initialize the validator

        :param lpar_w: LPAR wrapper intended to be validated
        :param mngd_sys: managed_system wrapper intended to be validated
            against such as making sure the host has the desired resources
            of the LPAR available.
        :param curr_lpar_w: (Optional) current LPAR wrapper used to validate
            deltas during a resize operation. If this is passed in then it
            assumes resize validation.
        """
        self.lpar_w = lpar_w
        self.mngd_sys = mngd_sys
        self.curr_lpar_w = curr_lpar_w

    def validate_all(self):
        ProcValidator(self.lpar_w, self.mngd_sys, self.curr_lpar_w).validate()


@six.add_metaclass(abc.ABCMeta)
class BaseValidator(object):
    """Base Validator.

    This class is responsible for delegating validation depending on
    if it's a deploy, active resize, or inactive resize.

    """
    def __init__(self, lpar_w, mngd_sys, curr_lpar_w=None):
        self.lpar_w = lpar_w
        self.mngd_sys = mngd_sys
        self.curr_lpar_w = curr_lpar_w

    def validate(self):
        # Deploy
        if self.curr_lpar_w is None:
            self._validate_deploy()
        # Inactive Resize
        # TODO(IBM):

        # Active Resize
        # TODO(IBM):

    @abc.abstractmethod
    def _validate_deploy(self):
        pass

    @abc.abstractmethod
    def _validate_active_resize(self):
        pass

    @abc.abstractmethod
    def _validate_inactive_resize(self):
        pass

    def _validate_host_has_available_res(self, des, avail, res_name):
        if round(des, 2) > round(avail, 2):
            ex_args = {'requested': '%.2f' % des,
                       'avail': '%.2f' % avail,
                       'instance_name': self.lpar_w.name,
                       'res_name': res_name}
            msg = _("Insufficient available %(res_name)s on host for virtual "
                    "machine '%(instance_name)s' (%(requested)s "
                    "requested, %(avail)s available)") % ex_args
            LOG.error(msg)
            raise ValidatorException(msg)


class ProcValidator(BaseValidator):

    def _validate_deploy(self):
        procs_avail = self.mngd_sys.proc_units_avail
        if self.lpar_w.proc_config.has_dedicated:
            des_procs = (self.lpar_w.proc_config.
                         dedicated_proc_cfg.desired)
            self._validate_host_has_available_res(des_procs,
                                                  procs_avail,
                                                  'CPUs')
        else:
            des_procs = (self.lpar_w.proc_config.
                         shared_proc_cfg.desired_units)
            self._validate_host_has_available_res(des_procs,
                                                  procs_avail,
                                                  'processor units')

    def _validate_active_resize(self):
        pass

    def _validate_inactive_resize(self):
        pass
