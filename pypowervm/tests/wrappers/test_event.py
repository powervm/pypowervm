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

import mock

import pypowervm.tests.test_utils.test_wrapper_abc as twrap
from pypowervm.wrappers import event


class TestEvent(twrap.TestWrapper):
    file = 'event_feed.txt'
    wrapper_class_to_test = event.Event

    @mock.patch('pypowervm.wrappers.entry_wrapper.EntryWrapper.get')
    def test_get(self, mock_ewrap_get):
        event.Event.get('adap', 'appid')
        mock_ewrap_get.assert_called_once_with('adap', xag=[], add_qp=[
            ('QUEUE_CLIENTKEY_METHOD', 'USE_APPLICATIONID'),
            ('QUEUE_APPLICATIONID', 'appid')])

    def test_getters(self):
        ev1, ev2 = self.entries[:2]
        self.assertEqual('510ae1e6-3e86-34c6-bf4c-c638e76a5f68', ev1.uuid)
        self.assertEqual(event.EventType.ADD_URI, ev1.etype)
        self.assertEqual('1473962006548', ev1.eid)
        self.assertEqual('http://localhost:12080/rest/api/uom/ManagedSystem/1c'
                         'ab7366-6b73-342c-9f43-ddfeb9f8edd3/LogicalPartition/'
                         '1E6FC741-6253-4B69-B88B-8A44BED92145', ev1.data)
        self.assertIsNone(ev1.detail)
        self.assertEqual(event.EventType.MODIFY_URI, ev2.etype)
        self.assertEqual('Other', ev2.detail)

    def test_bld(self):
        evt = event.Event.bld('adap', None, None)
        self.assertIsInstance(evt, event.Event)
        self.assertEqual('adap', evt.adapter)
        self.assertIsNone(evt.data)
        self.assertIsNone(evt.detail)
        evt = event.Event.bld('adap2', 'data', 'detail')
        self.assertIsInstance(evt, event.Event)
        self.assertEqual('adap2', evt.adapter)
        self.assertEqual('data', evt.data)
        self.assertEqual('detail', evt.detail)

    def test_str(self):
        self.assertEqual(
            'Event(id=1473962006548, type=ADD_URI, data=http://localhost:12080'
            '/rest/api/uom/ManagedSystem/1cab7366-6b73-342c-9f43-ddfeb9f8edd3/'
            'LogicalPartition/1E6FC741-6253-4B69-B88B-8A44BED92145, detail=Non'
            'e)', str(self.dwrap))
