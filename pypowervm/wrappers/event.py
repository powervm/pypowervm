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
"""Wrappers and related artifacts around /rest/api/uom/Event.

Events are produced semi-synchronously by the REST server.  Event.get() will
return right away if there are events waiting to be retrieved.  Otherwise, it
will block for up to ten seconds.  If no events have been produced in that
time, the request will return an empty feed.  Using this mechanism, it is
practical to poll Event.get in a hard loop with no sleeping on the client side.

An Event has a type (Event.etype), a data field (Event.data), and a detail
field (Event.detail).  For *_URI types, the data field contains the REST URI of
the object triggering the event, and the detail field may provide more granular
information about the event.

Events arrive in the order they are produced.  Special event types
CACHE_CLEARED and MISSING_EVENTS indicate that the client should refetch any
objects of interest before processing subsequent events.

Different clients may access the same Event feed at the same time.  The REST
server keeps track of which client has seen which events based on an
application ID (the `appid` argument to the get method).  Requests using a
given application ID for repeated requests will receive a single stream of
events (no duplicates).  Two clients using different application IDs will each
receive the same stream of events.

It is possible to push a custom event to the server.  This event will appear to
all active listeners as a CUSTOM_CLIENT_EVENT.  To use this mechanism,
construct the event with Event.bld(), supplying any values desired in data and
detail, and invoke .create() on the resulting Event wrapper.
"""

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
        """Construct a custom Event.

        Invoke .create() on the resulting Event to broadcast it to active
        listeners.

        :param adapter: pypowervm.adapter.Adapter for REST API communication.
        :param data: Any desired string to be included in the 'data' field of
                     the Event.  May be None.
        :param detail: Any desired string to be included in the 'detail' field
                       of the Event.  May be None.
        :return: An Event wrapper suitable for sending to the REST server via
                 the .create() method.
        """
        event = cls._bld(adapter)
        if data is not None:
            event.set_parm_value(_E_DATA, data)
        if detail is not None:
            event.set_parm_value(_E_DETAIL, detail)
        return event

    @property
    def etype(self):
        """The Event type, one of the EventType enum values."""
        return self._get_val_str(_E_TYPE)

    @property
    def eid(self):
        """Unique sequence identifier of this Event."""
        return self._get_val_str(_E_ID)

    @property
    def data(self):
        """Event data; for *_URI EventType, the URI of the affected object."""
        return self._get_val_str(_E_DATA)

    @property
    def detail(self):
        """Custom Event detail; semantics dependent on type & data."""
        return self._get_val_str(_E_DETAIL)

    def __str__(self):
        return "Event(id=%s, type=%s, data=%s, detail=%s)" % (
            self.eid, self.etype, self.data, self.detail)
