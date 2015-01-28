# Copyright 2014, 2015 IBM Corp.
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

from lxml import etree

import logging
import unittest

import mock
import requests.models as req_mod
import requests.structures as req_struct

import pypowervm.adapter as adp
import pypowervm.exceptions as pvmex
import pypowervm.tests.lib as testlib
from pypowervm.tests.wrappers.util import pvmhttp

logging.basicConfig()

logon_text = testlib.file2b("logon.xml")

response_text = testlib.file2b("event.xml")

NET_BRIDGE_FILE = 'fake_network_bridge.txt'


class TestAdapter(unittest.TestCase):
    """Test cases to test the adapter classes and methods."""

    def setUp(self):
        """Set up a mocked Session instance."""
        # Init test data
        host = '0.0.0.0'
        user = 'user'
        pwd = 'pwd'
        auditmemento = 'audit'

        # Create a Response object, that will serve as a mock return value
        my_response = req_mod.Response()
        my_response.status_code = 200
        my_response.reason = 'OK'
        dict_headers = {'content-length': '576',
                        'x-powered-by': 'Servlet/3.0',
                        'set-cookie': 'JSESSIONID=0000a41BnJsGTNQvBGERA' +
                        '3wR1nj:759878cb-4f9a-4b05-a09a-3357abfea3b4; ' +
                        'Path=/; Secure; HttpOnly, CCFWSESSION=E4C0FFBE9' +
                        '130431DBF1864171ECC6A6E; Path=/; Secure; HttpOnly',
                        'expires': 'Thu, 01 Dec 1994 16:00:00 GMT',
                        'x-transaction-id': 'XT10000073',
                        'cache-control': 'no-cache="set-cookie, ' +
                                         'set-cookie2"',
                        'date': 'Wed, 23 Jul 2014 21:51:10 GMT',
                        'content-type': 'application/vnd.ibm.powervm' +
                                        '.web+xml; type=LogonResponse'}
        my_response.headers = req_struct.CaseInsensitiveDict(dict_headers)
        my_response._content = logon_text

        # Mock out the method and class we are not currently testing
        with mock.patch('requests.Session') as mock_session:
            session = mock_session.return_value
            session.request.return_value = my_response

            # Create session for the test to use
            self.sess = adp.Session(host, user, pwd,
                                    auditmemento=auditmemento,
                                    certpath=None)
            # Mock out the logoff, which gets called when the session
            # goes out of scope during tearDown()
            self.sess._logoff = mock.Mock()

    def tearDown(self):
        """Tear down the Session instance."""
        self.sess = None

    @mock.patch('requests.Session')
    def test_read(self, mock_session):
        """Test read() method found in the Adapter class."""
        # Init test data
        root_type = 'ManagedSystem'
        root_id = 'caae9209-25e5-35cd-a71a-ed55c03f294d'
        child_type = 'child'
        child_id = 'child'
        suffix_type = 'quick'
        adapter = adp.Adapter(self.sess, use_cache=False)

        # Create a Response object, that will serve as a mock return value
        read_response = req_mod.Response()
        read_response.status_code = 200
        read_response.reason = 'OK'
        dict_headers = {'content-length': '576',
                        'content-language': 'en-US',
                        'x-powered-by': 'Servlet/3.0',
                        'set-cookie': 'JSESSIONID=0000Q6SoAlyICbmJA0bSiQV' +
                        'l69q:759878cb-4f9a-4b05-a09a-3357abfea3b4' +
                        'Path=/; Secure; HttpOnly, CCFWSESSION=E4C0FFBE9' +
                        '130431DBF1864171ECC6A6E; Path=/; Secure; HttpOnly',
                        'x-hmc-schema-version': 'V1_1_0',
                        'expires': 'Thu, 01 Dec 1994 16:00:00 GMT',
                        'x-transaction-id': 'XT10000058',
                        'cache-control': 'no-transform, must-revalidate, ' +
                        'proxy-revalidate, no-cache=set-cookie',
                        'date': 'Wed, 23 Jul 2014 04:29:09 GMT',
                        'content-type': 'application/vnd.ibm.powervm'}
        read_response.headers = req_struct.CaseInsensitiveDict(dict_headers)
        read_response._content = response_text

        # Mock out the method and class we are not currently testing
        session = mock_session.return_value
        session.request.return_value = read_response

        # Run the actual test
        ret_read_value = adapter.read(root_type, root_id, child_type,
                                      child_id, suffix_type)

        # Verify Correct path was built in build_path()
        reqpath = adp.Adapter.build_path('uom', root_type, root_id,
                                         child_type, child_id, suffix_type)
        # Verify the return value
        # self.assertIsInstance(ret_read_value, adp.Response)
        self.assertEqual('GET', ret_read_value.reqmethod)
        self.assertEqual(200, ret_read_value.status)
        self.assertEqual(reqpath, ret_read_value.reqpath)

    @mock.patch('requests.Session')
    def test_create(self, mock_session):
        """Test create() method found in the Adapter class."""
        # Init test data
        children = [adp.Element('AdapterType', text='Client'),
                    adp.Element('UseNextAvailableSlotID', text='true'),
                    adp.Element('RemoteLogicalPartitionID', text='1'),
                    adp.Element('RemoteSlotNumber', text='12')]
        new_scsi = adp.Element('VirtualSCSIClientAdapter',
                               attrib={'schemaVersion': 'V1_0'},
                               children=children)

        element = new_scsi
        root_type = 'ManagedSystem'
        root_id = 'id'
        child_type = 'LogicalPartition'
        adapter = adp.Adapter(self.sess, use_cache=False)

        # Create a Response object, that will serve as a mock return value
        create_response = req_mod.Response()
        create_response.status_code = 200
        create_response.reason = 'OK'
        dict_headers = {'content-length': '576',
                        'content-language': 'en-US',
                        'x-powered-by': 'Servlet/3.0',
                        'set-cookie': 'JSESSIONID=0000Q6SoAlyICbmJA0bSiQV' +
                        'l69q:759878cb-4f9a-4b05-a09a-3357abfea3b4' +
                        'Path=/; Secure; HttpOnly, CCFWSESSION=E4C0FFBE9' +
                        '130431DBF1864171ECC6A6E; Path=/; Secure; HttpOnly',
                        'x-hmc-schema-version': 'V1_1_0',
                        'expires': 'Thu, 01 Dec 1994 16:00:00 GMT',
                        'x-transaction-id': 'XT10000058',
                        'cache-control': 'no-transform, must-revalidate, ' +
                        'proxy-revalidate, no-cache=set-cookie',
                        'date': 'Wed, 23 Jul 2014 04:29:09 GMT',
                        'content-type': 'application/vnd.ibm.powervm'}
        create_response.headers = req_struct.CaseInsensitiveDict(dict_headers)
        create_response._content = response_text

        # Mock out the method and class we are not currently testing
        session = mock_session.return_value
        session.request.return_value = create_response

        # Run the actual test
        ret_create_value = adapter.create(element, root_type, root_id,
                                          child_type)

        # Verify Correct path was built in build_path()
        reqpath = adp.Adapter.build_path('uom', root_type, root_id,
                                         child_type)

        # Verify the return value
        # self.assertIsInstance(ret_create_value, adp.Response)
        self.assertEqual('PUT', ret_create_value.reqmethod)
        self.assertEqual(200, ret_create_value.status)
        self.assertEqual(reqpath, ret_create_value.reqpath)

    @mock.patch('requests.Session')
    def test_update(self, mock_session):
        """Test update() method found in the Adapter class."""
        # Init test data
        data = 'data'
        etag = 'etag'
        root_type = 'root type'
        root_id = 'root id'
        adapter = adp.Adapter(self.sess, use_cache=False)

        # Create a Response object, that will serve as a mock return value
        update_response = req_mod.Response()
        update_response.status_code = 200
        update_response.reason = 'OK'
        dict_headers = {'content-length': '576',
                        'content-language': 'en-US',
                        'x-powered-by': 'Servlet/3.0',
                        'set-cookie': 'JSESSIONID=0000Q6SoAlyICbmJA0bSiQV' +
                        'l69q:759878cb-4f9a-4b05-a09a-3357abfea3b4' +
                        'Path=/; Secure; HttpOnly, CCFWSESSION=E4C0FFBE9' +
                        '130431DBF1864171ECC6A6E; Path=/; Secure; HttpOnly',
                        'x-hmc-schema-version': 'V1_1_0',
                        'expires': 'Thu, 01 Dec 1994 16:00:00 GMT',
                        'x-transaction-id': 'XT10000058',
                        'cache-control': 'no-transform, must-revalidate, ' +
                        'proxy-revalidate, no-cache=set-cookie',
                        'date': 'Wed, 23 Jul 2014 04:29:09 GMT',
                        'content-type': 'application/vnd.ibm.powervm'}
        update_response.headers = req_struct.CaseInsensitiveDict(dict_headers)
        update_response._content = response_text

        # Mock out the method and class we are not currently testing
        session = mock_session.return_value
        session.request.return_value = update_response

        # Run the actual test
        ret_update_value = adapter.update(data, etag, root_type, root_id)

        # Verify Correct path was built in build_path()
        reqpath = adp.Adapter.build_path('uom', root_type, root_id)

        # Verify the return value
        # self.assertIsInstance(ret_update_value, adp.Response)
        self.assertEqual('POST', ret_update_value.reqmethod)
        self.assertEqual(200, ret_update_value.status)
        self.assertEqual(reqpath, ret_update_value.reqpath)

    @mock.patch('requests.Session')
    def test_delete(self, mock_session):
        """Test delete() method found in the Adapter class."""
        # Init test data
        root_type = 'ManagedSystem'
        root_id = 'id'
        adapter = adp.Adapter(self.sess, use_cache=False)

        # Create a Response object, that will serve as a mock return value
        delete_response = req_mod.Response()
        delete_response.status_code = 204
        delete_response.reason = 'No Content'
        dict_headers = {'content-length': '0',
                        'content-language': 'en-US',
                        'x-powered-by': 'Servlet/3.0',
                        'set-cookie': 'JSESSIONID=0000Q6SoAlyICbmJA0bSiQV' +
                        'l69q:759878cb-4f9a-4b05-a09a-3357abfea3b4' +
                        'Path=/; Secure; HttpOnly, CCFWSESSION=E4C0FFBE9' +
                        '130431DBF1864171ECC6A6E; Path=/; Secure; HttpOnly',
                        'x-hmc-schema-version': 'V1_1_0',
                        'expires': 'Thu, 01 Dec 1994 16:00:00 GMT',
                        'x-transaction-id': 'XT10000058',
                        'cache-control': 'no-transform, must-revalidate, ' +
                        'proxy-revalidate, no-cache=set-cookie',
                        'date': 'Wed, 23 Jul 2014 04:29:09 GMT',
                        'content-type': 'application/vnd.ibm.powervm'}
        delete_response.headers = req_struct.CaseInsensitiveDict(dict_headers)

        # Mock out the method and class we are not currently testing
        session = mock_session.return_value
        session.request.return_value = delete_response

        # Run the actual test
        ret_delete_value = adapter.delete(root_type, root_id)

        # Verify Correct path was built in build_path()
        reqpath = adp.Adapter.build_path('uom', root_type, root_id)

        # Verify the return value
        # self.assertIsInstance(ret_delete_value, adp.Response)
        self.assertEqual('DELETE', ret_delete_value.reqmethod)
        self.assertEqual(204, ret_delete_value.status)
        self.assertEqual(reqpath, ret_delete_value.reqpath)

    @mock.patch('pypowervm.adapter.LOG.warn')
    @mock.patch('requests.Session')
    def test_unauthorized_error(self, mock_session, mock_log):
        """401 (unauthorized) calling Adapter.create()."""

        # Init test data
        children = [adp.Element('AdapterType', text='Client'),
                    adp.Element('UseNextAvailableSlotID', text='true'),
                    adp.Element('RemoteLogicalPartitionID', text='1'),
                    adp.Element('RemoteSlotNumber', text='12')]
        new_scsi = adp.Element('VirtualSCSIClientAdapter',
                               attrib={'schemaVersion': 'V1_0'},
                               children=children)

        element = new_scsi
        root_type = 'ManagedSystem'
        root_id = 'id'
        child_type = 'LogicalPartition'
        adapter = adp.Adapter(self.sess, use_cache=False)

        # Create a Response object, that will serve as a mock return value
        create_response = req_mod.Response()
        create_response.status_code = 401
        create_response.reason = 'Unauthorized'
        dict_headers = {'content-length': '0',
                        'content-language': 'en-US',
                        'x-powered-by': 'Servlet/3.0',
                        'set-cookie': 'JSESSIONID=0000Q6SoAlyICbmJA0bSiQV' +
                        'l69q:759878cb-4f9a-4b05-a09a-3357abfea3b4' +
                        'Path=/; Secure; HttpOnly, CCFWSESSION=E4C0FFBE9' +
                        '130431DBF1864171ECC6A6E; Path=/; Secure; HttpOnly',
                        'x-hmc-schema-version': 'V1_1_0',
                        'expires': 'Thu, 01 Dec 1994 16:00:00 GMT',
                        'x-transaction-id': 'XT10000058',
                        'cache-control': 'no-transform, must-revalidate, ' +
                        'proxy-revalidate, no-cache=set-cookie',
                        'date': 'Wed, 23 Jul 2014 04:29:09 GMT',
                        'content-type': 'application/vnd.ibm.powervm'}
        create_response.headers = req_struct.CaseInsensitiveDict(dict_headers)

        # Mock out the method and class we are not currently testing
        session = mock_session.return_value
        session.request.return_value = create_response

        # Run the actual test
        self.assertRaises(pvmex.HttpError, adapter.create, element,
                          root_type, root_id, child_type)
        mock_log.assert_called_once_with(mock.ANY)

    def test_element_iter(self):
        """Test the ETElement iter() method found in the Adapter class."""

        # Init test data
        children = [adp.Element('Type1', text='T1_0'),
                    adp.Element('Type12', text='T12_0'),
                    adp.Element('Type1', text='T1_1'),
                    adp.Element('Type12', text='T12_1'),
                    adp.Element('Type1', text='T1_2')]
        top_element = adp.Element('Top',
                                  attrib={'schemaVersion': 'V1_0'},
                                  children=children)

        def _count_elem(top, tag, it=None, assert_tag=True):
            elem_count = 0
            it = it if it else top.iter(tag=tag)
            for elem in it:
                if assert_tag:
                    self.assertEqual(elem.tag, tag)
                elem_count += 1
            return elem_count

        # Run the actual tests

        # Ensure all elements are traversed if we don't specify a tag
        self.assertEqual(_count_elem(top_element, 'Type1',
                                     it=top_element.iter(),
                                     assert_tag=False), 6)

        # Ensure all elements are traversed for tag=*
        self.assertEqual(_count_elem(top_element, 'Type1',
                                     it=top_element.iter(tag='*'),
                                     assert_tag=False), 6)

        # Ensure all elements are traversed for tag=None
        self.assertEqual(_count_elem(top_element, 'Type1',
                                     it=top_element.iter(tag=None),
                                     assert_tag=False), 6)

        # Get only the Type1 elements
        self.assertEqual(_count_elem(top_element, 'Type1'), 3)

        # Get only the top
        self.assertEqual(_count_elem(top_element, 'Top'), 1)


class TestElementWrapper(unittest.TestCase):
    """Tests for the ElementWrapper class."""

    def setUp(self):
        super(TestElementWrapper, self).setUp()
        self.resp = pvmhttp.load_pvm_resp(NET_BRIDGE_FILE).get_response()
        self.nb1 = self.resp.feed.entries[0]
        self.resp2 = pvmhttp.load_pvm_resp(NET_BRIDGE_FILE).get_response()
        self.nb2 = self.resp2.feed.entries[0]

    def test_equality(self):
        """Validates that two elements loaded from the same data is equal."""
        sea1 = self._find_seas(self.nb1)[0]
        sea2 = self._find_seas(self.nb2)[0]
        self.assertTrue(sea1 == sea2)

        # Change the other SEA
        sea2._element.append(etree.Element('Bob'))
        self.assertFalse(sea1 == sea2)

    def test_inequality_by_subelem_change(self):
        sea1 = self._find_seas(self.nb1)[0]
        sea2 = self._find_seas(self.nb2)[0]
        sea_trunk = sea2.findall('./TrunkAdapters/TrunkAdapter')[1]
        pvid = sea_trunk.find('PortVLANID')
        pvid.text = '1'
        self.assertFalse(sea1 == sea2)

    def _find_seas(self, entry):
        """Wrapper for the SEAs."""
        return entry.element.findall('./SharedEthernetAdapters/'
                                     'SharedEthernetAdapter')


if __name__ == '__main__':
    unittest.main()
