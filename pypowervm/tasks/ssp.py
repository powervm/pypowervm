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

import pypowervm.exceptions as exc
import pypowervm.wrappers.storage as stor


def crt_lu(adap, ssp, name, size, thin=None):
    """Create a Logical Unit on the specified Shared Storage Pool.

    :param adap: The pypowervm.adapter.Adapter through which to request the
                 change.
    :param ssp: SSP EntryWrapper denoting the Shared Storage Pool on which to
                create the LU.
    :param name: Name for the new Logical Unit.
    :param size: LU size in GB with decimal precision.
    :param thin: Provision the new LU as Thin (True) or Thick (False).  If
                 unspecified, use the server default.
    :return: The updated SSP wrapper.  (It will contain the new LU and have a
             new etag.)
    :return: LU ElementWrapper representing the Logical Unit just created.
    """
    # Refuse to add with duplicate name
    if name in [lu.name for lu in ssp.logical_units]:
        raise exc.DuplicateLUNameError(lu_name=name, ssp_name=ssp.name)

    lu = stor.LU.bld(name, size, thin)
    ssp.logical_units.append(lu)
    ssp = ssp.update(adap)
    newlu = None
    for lu in ssp.logical_units:
        if lu.name == name:
            newlu = lu
    return ssp, newlu


def rm_lu(adap, ssp, lu=None, name=None, udid=None):
    """Remove a LogicalUnit from a SharedStoragePool.

    This method allows the LU to be specified by wrapper, name, or UDID.

    :param adap: The pypowervm.adapter.Adapter through which to request the
                 change.
    :param ssp: SSP EntryWrapper denoting the Shared Storage Pool from which to
                remove the LU.
    :param lu: LU ElementWrapper indicating the LU to remove.  If specified,
               the name and udid parameters are ignored.
    :param name: The name of the LU to remove.  If both name and udid are
                 specified, udid is used.
    :param udid: The UDID of the LU to remove.  If both name and udid are
                 specified, udid is used.
    :return: The updated SSP wrapper.  (It will contain the modified LU list
             and have a new etag.)
    :return: LU ElementWrapper representing the Logical Unit removed.
    """
    lus = ssp.logical_units
    lu_to_rm = None
    label = None
    if lu:
        try:
            lu_to_rm = lus[lus.index(lu)]
        except ValueError:
            raise exc.LUNotFoundError(lu_label=lu.name, ssp_name=ssp.name)
    else:
        for l in lus:
            # This should implicitly account for 'None'
            if l.udid == udid or l.name == name:
                lu_to_rm = l
                break
        if lu_to_rm is None:
            label = name or udid
            raise exc.LUNotFoundError(lu_label=label, ssp_name=ssp.name)
    lus.remove(lu_to_rm)
    ssp = ssp.update(adap)
    return ssp, lu_to_rm