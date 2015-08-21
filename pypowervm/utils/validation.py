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
from pypowervm.wrappers import base_partition as bp

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
        MemValidator(self.lpar_w, self.host_w,
                     cur_lpar_w=self.cur_lpar_w).validate()


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
        """Determines what validation is requested and invokes it."""
        # Deploy
        self._populate_new_values()
        if self.cur_lpar_w is None:
            self._validate_deploy()
        # Resize
        else:
            self._populate_resize_diffs()
            # Active Resize
            if self.cur_lpar_w.state == bp.LPARState.RUNNING:
                if self.cur_lpar_w.rmc_state != bp.RMCState.ACTIVE:
                    ex_args = {'instance_name': self.lpar_w.name}
                    msg = _("Resizing instance '%(instance_name)s' in Active "
                            "state is not supported without RMC "
                            "connectivity.") % ex_args
                    LOG.error(msg)
                    raise ValidatorException(msg)
                self._validate_active_resize()
            # Inactive Resize
            else:
                self._validate_inactive_resize()
        self._validate_common()

    @abc.abstractmethod
    def _populate_new_values(self):
        """Abstract method for populating deploy values

        This method will always be called in validate() and should
        populate instance attributes with the new LPARWrapper
        values.
        """

    @abc.abstractmethod
    def _populate_resize_diffs(self):
        """Abstract method for populating resize values

        This method will only be called in validate() for resize
        operations and should populate instance attributes with
        the differences between the old and new LPARWrapper values.
        """

    @abc.abstractmethod
    def _validate_deploy(self):
        """Abstract method for deploy validation only."""

    @abc.abstractmethod
    def _validate_active_resize(self):
        """Abstract method for active resize validation only."""

    @abc.abstractmethod
    def _validate_inactive_resize(self):
        """Abstract method for inactive resize validation only."""

    @abc.abstractmethod
    def _validate_common(self):
        """Abstract method for common validation

        This method should be agnostic to the operation being validated
        (deploy or resize) because the instance attributes will
        be populated accordingly in validate().
        """

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


class MemValidator(BaseValidator):

    def _populate_new_values(self):
        """Set newly desired LPAR attributes as instance attributes."""
        mem_cfg = self.lpar_w.mem_config
        self.des_mem = mem_cfg.desired
        self.avail_mem = self.host_w.memory_free
        self.res_name = 'memory'

    def _populate_resize_diffs(self):
        """Calculate lpar_w vs cur_lpar_w diffs and set as attributes."""
        # TODO(IBM):
        pass

    def _validate_deploy(self):
        """Enforce validation rules specific to LPAR deployment."""
        self._validate_host_has_available_res(self.des_mem, self.avail_mem,
                                              self.res_name)

    def _validate_active_resize(self):
        """Enforce validation rules specific to active resize."""
        # TODO(IBM):
        pass

    def _validate_inactive_resize(self):
        """Enforce validation rules specific to inactive resize."""
        # TODO(IBM):
        pass

    def _validate_common(self):
        """Enforce operation agnostic validation rules."""
        # TODO(IBM):
        pass


class ProcValidator(BaseValidator):

    def _populate_dedicated_proc_values(self):
        """Set dedicated proc values as instance attributes."""
        ded_proc_cfg = self.lpar_w.proc_config.dedicated_proc_cfg
        self.des_procs = ded_proc_cfg.desired
        self.res_name = _('CPUs')
        # Proc host limits for dedicated proc
        self.max_procs_per_aix_linux_lpar =\
            self.host_w.max_procs_per_aix_linux_lpar
        self.max_sys_procs_limit =\
            self.host_w.max_sys_procs_limit

        # VCPUs doesn't mean anything in dedicated proc cfg
        # FAIP in dedicated proc cfg vcpus == procs for naming convention
        self.des_vcpus = self.des_procs
        self.max_vcpus = ded_proc_cfg.max

    def _populate_shared_proc_values(self):
        """Set shared proc values as instance attributes."""
        shr_proc_cfg = self.lpar_w.proc_config.shared_proc_cfg
        self.des_procs = shr_proc_cfg.desired_units
        self.res_name = _('processing units')
        # VCPU host limits for shared proc
        self.max_procs_per_aix_linux_lpar =\
            self.host_w.max_vcpus_per_aix_linux_lpar
        self.max_sys_procs_limit =\
            self.host_w.max_sys_vcpus_limit

        self.des_vcpus = shr_proc_cfg.desired_virtual
        self.max_vcpus = shr_proc_cfg.max_virtual

    def _populate_new_values(self):
        """Set newly desired LPAR values as instance attributes."""
        self.has_dedicated = self.lpar_w.proc_config.has_dedicated
        self.procs_avail = self.host_w.proc_units_avail
        if self.has_dedicated:
            self._populate_dedicated_proc_values()
        else:
            self._populate_shared_proc_values()

    def _populate_resize_diffs(self):
        """Calculate lpar_w vs cur_lpar_w diffs and set as attributes."""
        # TODO(IBM):
        pass

    def _validate_deploy(self):
        """Enforce validation rules specific to LPAR deployment."""
        self._validate_host_has_available_res(self.des_procs, self.procs_avail,
                                              self.res_name)

    def _validate_active_resize(self):
        """Enforce validation rules specific to active resize."""
        # TODO(IBM):
        pass

    def _validate_inactive_resize(self):
        """Enforce validation rules specific to inactive resize."""
        # TODO(IBM):
        pass

    def _validate_common(self):
        """Enforce operation agnostic validation rules."""
        self._validate_host_max_allowed_procs_per_lpar()
        self._validate_host_max_sys_procs_limit()

    def _validate_host_max_allowed_procs_per_lpar(self):
        if self.des_vcpus > self.max_procs_per_aix_linux_lpar:
            ex_args = {'vcpus': self.des_vcpus,
                       'max_allowed': self.max_procs_per_aix_linux_lpar,
                       'instance_name': self.lpar_w.name}
            msg = _("The desired processors (%(vcpus)d) cannot be above "
                    "the maximum allowed processors per partition "
                    "(%(max_allowed)d) for virtual machine "
                    "'%(instance_name)s'.") % ex_args
            LOG.error(msg)
            raise ValidatorException(msg)

    def _validate_host_max_sys_procs_limit(self):
        if self.max_vcpus > self.max_sys_procs_limit:
            ex_args = {'vcpus': self.max_vcpus,
                       'max_allowed': self.max_sys_procs_limit,
                       'instance_name': self.lpar_w.name}
            msg = _("The maximum processors (%(vcpus)d) cannot be above "
                    "the maximum system capacity processor limit "
                    "(%(max_allowed)d) for virtual machine "
                    "'%(instance_name)s'.") % ex_args
            LOG.error(msg)
            raise ValidatorException(msg)
