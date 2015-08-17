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
    def __init__(self, lpar_w, host_w, cur_lpar_w=None):
        """Initialize the validator

        :param lpar_w: LPAR wrapper intended to be validated
        :param host_w: managed_system wrapper intended to be validated
            against such as making sure the host has the desired resources
            of the LPAR available.
        :param cur_lpar_w: (Optional) current LPAR wrapper used to validate
            deltas during a resize operation. If this is passed in then it
            assumes resize validation.
        """
        self.lpar_w = lpar_w
        self.host_w = host_w
        self.cur_lpar_w = cur_lpar_w

    def validate_all(self):
        """Invoke attribute validation classes to perform validation"""
        ProcValidator(self.lpar_w, self.host_w,
                      cur_lpar_w=self.cur_lpar_w).validate()
        # TODO(IBM): Memory Validation


@six.add_metaclass(abc.ABCMeta)
class BaseValidator(object):
    """Base Validator.

    This class is responsible for delegating validation depending on
    if it's a deploy, active resize, or inactive resize.

    If the caller intends to perform resize validation then they must pass
    the cur_lpar_w argument. The cur_lpar_w is the current LPAR wrapper
    describing the LPAR before any resizing has taken place, while lpar_w
    represents the LPAR with new (resized) values. If cur_lpar_w is None
    then deploy validation logic will ensue.
    """
    def __init__(self, lpar_w, host_w, cur_lpar_w=None):
        """Initialize LPAR and System Wrappers."""
        self.lpar_w = lpar_w
        self.host_w = host_w
        self.cur_lpar_w = cur_lpar_w

    def validate(self):
        """Determines what validation is needed and invokes it."""
        # Deploy
        if self.cur_lpar_w is None:
            self._validate_deploy()
        # Inactive Resize
        # TODO(IBM):

        # Active Resize
        # TODO(IBM):

    @abc.abstractmethod
    def _validate_deploy(self):
        """Deploy validation abstract method."""

    @abc.abstractmethod
    def _validate_active_resize(self):
        """Active resize validation abstract method."""

    @abc.abstractmethod
    def _validate_inactive_resize(self):
        """Inactive resize validation abstract method."""

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
        """Validate processor values for deployment.

        Validation logic in place
        1. desired processors are available on host
        """
        procs_avail = self.host_w.proc_units_avail
        if self.lpar_w.proc_config.has_dedicated:
            des_procs = (self.lpar_w.proc_config.
                         dedicated_proc_cfg.desired)
            res_name = _('CPUs')
        else:
            des_procs = (self.lpar_w.proc_config.
                         shared_proc_cfg.desired_units)
            res_name = _('processing units')
        self._validate_host_has_available_res(des_procs, procs_avail,
                                              res_name)

    def _validate_active_resize(self):
        # TODO(IBM):
        raise NotImplementedError()

    def _validate_inactive_resize(self):
        # TODO(IBM):
        raise NotImplementedError()
