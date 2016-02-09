# Copyright 2016 IBM Corp.
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

"""Tasks around enterprise pools."""

from oslo_config import cfg
from oslo_log import log as logging

from pypowervm.utils import transaction
from pypowervm.wrappers import enterprise_pool as ep

LOG = logging.getLogger(__name__)

CONF = cfg.CONF


def set_mobile_proc_units(adapter, pool_uuid, member_uuid, num_proc_units):
    """Set the number of mobile proc units...

    for the member corresponding to member_uuid that belongs to the pool
    corresponding to pool_uuid.

    :param adapter: The adapter for the pypowervm API.
    :param pool_uuid: The UUID of the pool.
    :param member_uuid: The UUID of the member of the pool.
    :param num_proc_units: The integer number of mobile proc units the member
                           should have.
    """
    return _set_mobile_value(adapter, pool_uuid, member_uuid,
                             ep.EnterprisePoolMember.mobile_proc_units.fget,
                             ep.EnterprisePoolMember.mobile_proc_units.fset,
                             num_proc_units)


def set_mobile_memory(adapter, pool_uuid, member_uuid, memory_amount):
    """Set the amount of mobile memory...

    for the member corresponding to member_uuid that belongs to the pool
    corresponding to pool_uuid.

    :param adapter: The adapter for the pypowervm API.
    :param pool_uuid: The UUID of the pool.
    :param member_uuid: The UUID of the member of the pool.
    :param memory_amount: The integer amount of mobile memory the member
                          should have.
    """
    return _set_mobile_value(adapter, pool_uuid, member_uuid,
                             ep.EnterprisePoolMember.mobile_memory.fget,
                             ep.EnterprisePoolMember.mobile_memory.fset,
                             memory_amount)


def _set_mobile_value(adapter, pool_uuid, member_uuid, getter, setter, value):
    """Set the mobile value...

    for the member corresponding to member_uuid that belongs to the pool
    corresponding to pool_uuid.

    :param adapter: The adapter for the pypowervm API.
    :param pool_uuid: The UUID of the pool.
    :param member_uuid: The UUID of the member of the pool.
    :param getter: The function corresponding to the property getter
    :param setter: The function corresponding to the property setter
    :param value: The value to set the property to
    """
    member = ep.EnterprisePoolMember.getter(adapter, entry_uuid=member_uuid,
                                            parent_class=ep.EnterprisePool,
                                            parent_uuid=pool_uuid).get()

    @transaction.entry_transaction
    def run_update(pool_member):
        current_value = getter(pool_member)
        if current_value != value:
            setter(pool_member, value)
            pool_member.update()

    run_update(member)
