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
"""Wrappers and related artifacts around /rest/api/uom/Event."""

import pypowervm.wrappers.entry_wrapper as ewrap

# Constants for Event
_E_SCHEMA_TYPE = 'Event'
_E_TYPE = 'EventType'
_E_ID = 'EventID'
_E_DATA = 'EventData'
_E_DETAIL = 'EventDetail'

_E_EL_ORDER = (_E_TYPE, _E_ID, _E_DATA, _E_DETAIL)


class EventType(object):
    """Enumeration of event types (from EventType.Enum)."""
    INVALID_URI = 'INVALID_URI'
    CACHE_CLEARED = 'CACHE_CLEARED'
    MISSING_EVENTS = 'MISSING_EVENTS'
    ADD_URI = 'ADD_URI'
    MODIFY_URI = 'MODIFY_URI'
    DELETE_URI = 'DELETE_URI'
    NEW_CLIENT = 'NEW_CLIENT'
    HIDDEN_URI = 'HIDDEN_URI'
    VISIBLE_URI = 'VISIBLE_URI'
    CUSTOM_CLIENT_EVENT = 'CUSTOM_CLIENT_EVENT'


@ewrap.EntryWrapper.pvm_type(_E_SCHEMA_TYPE, child_order=_E_EL_ORDER)
class Event(ewrap.EntryWrapper):

    @classmethod
    def get(cls, adapter, appid):
        """Retrieve the latest Event feed for a given application ID.

        Note: This request may block for a finite amount of time (on the order
        of 10s) while the server is waiting for new events to occur.

        :param adapter: pypowervm.adapter.Adapter for REST API communication.
        :param appid: A hex string identifying the unique consumer.  Consumers
                      pulling Event feeds will see the same events duplicated
                      in each request that uses a different appid.  To see a
                      single stream of unique events, a consumer should make
                      repeated requests with the same appid.
        :return: Feed of Event EntryWrapper objects (may be empty).
        """
        return super(Event, cls).get(adapter, xag=[], add_qp=[
            ('QUEUE_CLIENTKEY_METHOD', 'USE_APPLICATIONID'),
            ('QUEUE_APPLICATIONID', appid)])

    @classmethod
    def bld(cls, adapter, data, detail):
        event = cls._bld(adapter)
        if data is not None:
            event.set_parm_value(_E_DATA, data)
        if detail is not None:
            event.set_parm_value(_E_DETAIL, detail)
        return event

    @property
    def etype(self):
        return self._get_val_str(_E_TYPE)

    @property
    def eid(self):
        return self._get_val_str(_E_ID)

    @property
    def edata(self):
        return self._get_val_str(_E_DATA)

    @property
    def edetail(self):
        return self._get_val_str(_E_DETAIL)

    def __str__(self):
        return "Event(type=%s, data=%s, detail=%s)" % (self.etype, self.edata,
                                                       self.edetail)
