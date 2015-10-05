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

import errno

from lxml import etree
import six

if six.PY2:
    import __builtin__ as builtins
elif six.PY3:
    import builtins
import unittest

try:
    import urlparse
except ImportError:
    import urllib.parse as urlparse

import mock
import requests.models as req_mod
import requests.structures as req_struct
import testtools

import pypowervm.adapter as adp
import pypowervm.const as c
import pypowervm.entities as ent
import pypowervm.exceptions as pvmex
import pypowervm.tests.lib as testlib
import pypowervm.tests.test_fixtures as fx
from pypowervm.tests.test_utils import pvmhttp
from pypowervm.wrappers import storage as pvm_stor
from pypowervm.wrappers import virtual_io_server as pvm_vios

logon_text = testlib.file2b("logon.xml")

response_text = testlib.file2b("event.xml")

NET_BRIDGE_FILE = 'fake_network_bridge.txt'


class TestAdapter(testtools.TestCase):
    """Test cases to test the adapter classes and methods."""

    def _mk_response(self, status, content=None):
        reasons = {200: 'OK', 204: 'No Content', 401: 'Unauthorized'}
        # Create a Response object, that will serve as a mock return value
        my_response = req_mod.Response()
        my_response.status_code = status
        my_response.reason = reasons[status]
        clen = '0'
        if status == 200 and content:
            clen = str(len(content))
        dict_headers = {'content-length': clen,
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
                        'content-type': 'application/vnd.ibm.powervm'}
        my_response.headers = req_struct.CaseInsensitiveDict(dict_headers)
        my_response._content = content
        return my_response

    def setUp(self):
        super(TestAdapter, self).setUp()
        """Set up a mocked Session instance."""
        # Init test data
        host = '0.0.0.0'
        user = 'user'
        pwd = 'pwd'
        auditmemento = 'audit'

        # Create a Response object, that will serve as a mock return value
        my_response = self._mk_response(200, logon_text)

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
        super(TestAdapter, self).tearDown()

    @mock.patch('pypowervm.adapter.Session')
    def test_empty_init(self, mock_sess):
        adp.Adapter()
        mock_sess.assert_called_with()

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
        read_response = self._mk_response(200, response_text)

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

    @mock.patch('pypowervm.adapter.Adapter._request')
    def test_headers(self, mock_request):
        def validate_hdrs_func(acc=None, inm=None):
            expected_headers = {}
            if acc is not None:
                expected_headers['Accept'] = acc
            if inm is not None:
                expected_headers['If-None-Match'] = inm

            def validate_request(meth, path, **kwargs):
                self.assertEqual(expected_headers, kwargs['headers'])

            return validate_request

        adpt = adp.Adapter(mock.Mock())
        basepath = c.API_BASE_PATH + 'uom/SomeRootObject'
        uuid = "abcdef01-2345-2345-2345-67890abcdef0"
        hdr_xml = 'application/atom+xml'
        hdr_json = 'application/json'
        etag = 'abc123'

        # Root feed
        mock_request.side_effect = validate_hdrs_func(acc=hdr_xml)
        adpt._read_by_path(basepath, None, None, None, None)

        # Root instance with etag
        mock_request.side_effect = validate_hdrs_func(acc=hdr_xml, inm=etag)
        adpt._read_by_path(basepath + '/' + uuid, etag, None, None, None)

        # Quick root anchor (produces XML report of available quick properties
        mock_request.side_effect = validate_hdrs_func(acc=hdr_xml)
        adpt._read_by_path(basepath + '/quick', None, None, None, None)

        # Quick root instance (JSON of all quick properties)
        mock_request.side_effect = validate_hdrs_func(acc=hdr_json)
        adpt._read_by_path('/'.join([basepath, uuid, 'quick']), None, None,
                           None, None)

        # Specific quick property
        mock_request.side_effect = validate_hdrs_func(acc=hdr_json)
        adpt._read_by_path('/'.join([basepath, uuid, 'quick', 'property']),
                           None, None, None, None)

        # Explicit JSON file
        mock_request.side_effect = validate_hdrs_func(acc=hdr_json)
        adpt._read_by_path('/'.join([basepath, 'somefile.json']), None, None,
                           None, None)

        # Object that happens to end in 'json'
        mock_request.side_effect = validate_hdrs_func(acc=hdr_xml)
        adpt._read_by_path('/'.join([basepath, 'xml_about_json']), None, None,
                           None, None)

        # Quick with query params and fragments
        mock_request.side_effect = validate_hdrs_func(acc=hdr_json)
        adpt._read_by_path('/'.join([basepath, uuid, 'quick']) +
                           '?group=None#frag', None, None, None, None)

    @mock.patch('requests.Session')
    def test_create(self, mock_session):
        """Test create() method found in the Adapter class."""
        # Init test data
        adapter = adp.Adapter(self.sess, use_cache=False)
        new_scsi = pvm_stor.VSCSIClientAdapterElement.bld(adapter)

        element = new_scsi
        root_type = 'ManagedSystem'
        root_id = 'id'
        child_type = 'LogicalPartition'

        create_response = self._mk_response(200, response_text)

        # Mock out the method and class we are not currently testing
        session = mock_session.return_value
        session.request.return_value = create_response

        # Run the actual test
        ret_create_value = adapter.create(element, root_type, root_id,
                                          child_type)

        # Verify Correct path was built in build_path()
        reqpath = adp.Adapter.build_path('uom', root_type, root_id,
                                         child_type, xag=[])

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

        update_response = self._mk_response(200, response_text)

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
    def test_upload(self, mock_session):
        # Build the adapter
        adapter = adp.Adapter(self.sess, use_cache=False)

        # Mock data
        filedesc_mock = mock.MagicMock()
        filedesc_mock.findtext.side_effect = ['uuid', 'mime']

        mock_request = mock.MagicMock()
        adapter._request = mock_request

        # Invoke
        adapter.upload_file(filedesc_mock, None)

        # Validate
        expected_headers = {'Accept': 'application/vnd.ibm.powervm.web+xml',
                            'Content-Type': 'mime'}
        expected_path = '/rest/api/web/File/contents/uuid'
        mock_request.assert_called_with('PUT', expected_path, helpers=None,
                                        headers=expected_headers,
                                        timeout=-1, auditmemento=None,
                                        filehandle=None, chunksize=65536)

    def _assert_paths_equivalent(self, exp, act):
        """Ensures two paths or hrefs are "the same".

        Query parameter keys may be specified in any order, though their values
        must match exactly.  The rest of the path must be identical.

        :param exp: Expected path
        :param act: Actual path (produced by test)
        """
        p_exp = urlparse.urlparse(exp)
        p_act = urlparse.urlparse(act)
        self.assertEqual(p_exp.scheme, p_act.scheme)
        self.assertEqual(p_exp.netloc, p_act.netloc)
        self.assertEqual(p_exp.path, p_act.path)
        self.assertEqual(p_exp.fragment, p_act.fragment)
        qs_exp = urlparse.parse_qs(p_exp.query)
        qs_act = urlparse.parse_qs(p_act.query)
        for vals in qs_exp.values():
            vals.sort()
        for vals in qs_act.values():
            vals.sort()
        self.assertEqual(qs_exp, qs_act)

    @mock.patch('requests.Session')
    def test_extend_path(self, mock_session):
        # Init test data
        adapter = adp.Adapter(self.sess, use_cache=False)

        path = adapter.extend_path('basepath', suffix_type='suffix',
                                   suffix_parm='suffix_parm',
                                   detail='detail',
                                   xag=[pvm_vios.VIOS.xags.FC_MAPPING])

        expected_path = ('basepath/suffix/suffix_parm?detail=detail&'
                         'group=ViosFCMapping')
        self._assert_paths_equivalent(expected_path, path)

        # Multiple XAGs in a set
        path = adapter.extend_path('basepath', suffix_type='suffix',
                                   suffix_parm='suffix_parm',
                                   detail='detail',
                                   xag={pvm_vios.VIOS.xags.FC_MAPPING,
                                        pvm_vios.VIOS.xags.NETWORK})

        expected_path = ('basepath/suffix/suffix_parm?detail=detail&'
                         'group=ViosFCMapping,ViosNetwork')
        self._assert_paths_equivalent(expected_path, path)

        # Verify sorting
        path = adapter.extend_path('basepath', suffix_type='suffix',
                                   suffix_parm='suffix_parm',
                                   detail='detail',
                                   xag=[pvm_vios.VIOS.xags.NETWORK,
                                        pvm_vios.VIOS.xags.FC_MAPPING])

        expected_path = ('basepath/suffix/suffix_parm?detail=detail&'
                         'group=ViosFCMapping,ViosNetwork')
        self._assert_paths_equivalent(expected_path, path)

        # Explicitly no XAG
        path = adapter.extend_path('basepath', suffix_type='suffix',
                                   suffix_parm='suffix_parm', detail='detail',
                                   xag=[])

        expected_path = 'basepath/suffix/suffix_parm?detail=detail'
        self._assert_paths_equivalent(expected_path, path)

        # Ensure unspecified XAG defaults to group=None
        path = adapter.extend_path('basepath', suffix_type='suffix',
                                   suffix_parm='suffix_parm')

        expected_path = 'basepath/suffix/suffix_parm?group=None'
        self._assert_paths_equivalent(expected_path, path)

        # ...except for specific suffix types 'quick' and 'do'
        path = adapter.extend_path('basepath', suffix_type='quick',
                                   suffix_parm='suffix_parm')

        expected_path = 'basepath/quick/suffix_parm'
        self._assert_paths_equivalent(expected_path, path)

        path = adapter.extend_path('basepath', suffix_type='do',
                                   suffix_parm='suffix_parm')

        expected_path = 'basepath/do/suffix_parm'
        self._assert_paths_equivalent(expected_path, path)

        # Ensure arg xags and path xags interact correctly
        # path_xag=None, arg_xag=None => group=None
        self._assert_paths_equivalent(
            'basepath?group=None', adapter.extend_path('basepath'))
        # path_xag='None', arg_xag=None => group=None
        self._assert_paths_equivalent(
            'basepath?group=None', adapter.extend_path('basepath?group=None'))
        # path_xag='a,b,c', arg_xag=None => group=a,b,c
        self._assert_paths_equivalent(
            'basepath?group=a,b,c',
            adapter.extend_path('basepath?group=a,b,c'))
        # path_xag=None, arg_xag=() => no group=
        self._assert_paths_equivalent(
            'basepath', adapter.extend_path('basepath', xag=()))
        # path_xag='None', arg_xag={} => no group=
        self._assert_paths_equivalent(
            'basepath', adapter.extend_path('basepath?group=None', xag={}))
        # path_xag='a,b,c', arg_xag=[] => ValueError
        self.assertRaises(
            ValueError, adapter.extend_path, 'basepath?group=a,b,c', xag=[])
        # path_xag=None, arg_xag='a,b,c' => group='a,b,c'
        self._assert_paths_equivalent(
            'basepath?group=a,b,c',
            adapter.extend_path('basepath', xag={'a', 'b', 'c'}))
        # path_xag='None', arg_xag='a,b,c' => group='a,b,c'
        self._assert_paths_equivalent(
            'basepath?group=a,b,c',
            adapter.extend_path('basepath?group=None', xag=('a', 'b', 'c')))
        # path_xag='a,b,c', arg_xag='a,b,c' => group='a,b,c'
        self._assert_paths_equivalent(
            'basepath?group=a,b,c',
            adapter.extend_path('basepath?group=a,b,c', xag=['a', 'b', 'c']))
        # path_xag='a,b,c', arg_xag='d,e,f' => ValueError
        self.assertRaises(ValueError, adapter.extend_path,
                          'basepath?group=a,b,c', xag=['d', 'e', 'f'])
        # Multi-instance query params properly reassembled.
        self._assert_paths_equivalent(
            'basepath?foo=1,2,3&group=a,b,c&foo=4,5,6',
            adapter.extend_path('basepath?foo=4,5,6&group=None&foo=1,2,3',
                                xag=['a', 'b', 'c']))

    @mock.patch('pypowervm.adapter.LOG')
    @mock.patch('pypowervm.adapter.Adapter.read_by_path')
    def test_read_by_href(self, mock_read_by_path, mock_log):
        """Ensure read_by_href correctly extends, preserves query strings."""
        def validate_read_by_path(expected):
            def _read_by_path(path, etag, timeout, auditmemento, age,
                              sensitive, helpers):
                self._assert_paths_equivalent(expected, path)
                for param in (etag, auditmemento, helpers):
                    self.assertIsNone(param)
                for param2 in (age, timeout):
                    self.assertEqual(-1, param2)
                self.assertFalse(sensitive)
            return _read_by_path

        self.sess.host = 'foo'
        self.sess.port = 123
        adapter = adp.Adapter(self.sess)
        mock_read_by_path.side_effect = validate_read_by_path(
            '/rest/api/uom/Bar?k=v&group=None#frag')
        adapter.read_by_href('http://foo:123/rest/api/uom/Bar?k=v#frag')
        self.assertFalse(mock_log.debug.called)

        self.sess.host = 'bar'
        mock_read_by_path.side_effect = validate_read_by_path(
            '/rest/api/uom/Bar?k=v&group=None#frag')
        adapter.read_by_href('http://foo:123/rest/api/uom/Bar?k=v#frag')
        self.assertTrue(mock_log.debug.called)

        mock_read_by_path.side_effect = validate_read_by_path(
            '/rest/api/uom/Bar?k=v&group=RealGroup#frag')
        adapter.read_by_href(
            'http://foo:123/rest/api/uom/Bar?k=v&group=RealGroup#frag')

    @mock.patch('requests.Session')
    def test_delete(self, mock_session):
        """Test delete() method found in the Adapter class."""
        # Init test data
        root_type = 'ManagedSystem'
        root_id = 'id'
        adapter = adp.Adapter(self.sess, use_cache=False)

        delete_response = self._mk_response(204)

        # Mock out the method and class we are not currently testing
        session = mock_session.return_value
        session.request.return_value = delete_response

        # Run the actual test
        ret_delete_value = adapter.delete(root_type, root_id)

        # Verify Correct path was built in build_path()
        reqpath = adp.Adapter.build_path('uom', root_type, root_id, xag=[])

        # Verify the return value
        # self.assertIsInstance(ret_delete_value, adp.Response)
        self.assertEqual('DELETE', ret_delete_value.reqmethod)
        self.assertEqual(204, ret_delete_value.status)
        self.assertEqual(reqpath, ret_delete_value.reqpath)

    @mock.patch.object(builtins, 'open')
    def test_auth_file_error(self, mock_open_patch):
        mock_open_patch.side_effect = IOError(errno.EACCES, 'Error')
        self.assertRaises(pvmex.AuthFileReadError,
                          self.sess._get_auth_tok_from_file,
                          mock.Mock(), mock.Mock())

        mock_open_patch.side_effect = IOError(errno.EIO, 'Error')
        self.assertRaises(pvmex.AuthFileAccessError,
                          self.sess._get_auth_tok_from_file,
                          mock.Mock(), mock.Mock())

    @mock.patch('pypowervm.adapter.LOG')
    @mock.patch('requests.Session')
    def test_unauthorized_error(self, mock_session, mock_log):
        """401 (unauthorized) calling Adapter.create()."""

        # Init test data
        adapter = adp.Adapter(self.sess, use_cache=False)
        new_scsi = pvm_stor.VSCSIClientAdapterElement.bld(adapter)

        element = new_scsi
        root_type = 'ManagedSystem'
        root_id = 'id'
        child_type = 'LogicalPartition'

        create_response = self._mk_response(401)

        # Mock out the method and class we are not currently testing
        session = mock_session.return_value
        session.request.return_value = create_response

        # Run the actual test
        self.assertRaises(pvmex.HttpError, adapter.create, element,
                          root_type, root_id, child_type)
        mock_log.warn.assert_called_once_with(mock.ANY)

    def test_element_iter(self):
        """Test the ETElement iter() method found in the Adapter class."""

        # Init test data
        children = [ent.Element('Type1', None, text='T1_0'),
                    ent.Element('Type12', None, text='T12_0'),
                    ent.Element('Type1', None, text='T1_1'),
                    ent.Element('Type12', None, text='T12_1'),
                    ent.Element('Type1', None, text='T1_2')]
        top_element = ent.Element('Top', None,
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


class TestElement(testtools.TestCase):
    def setUp(self):
        super(TestElement, self).setUp()
        self.adpt = self.useFixture(fx.AdapterFx()).adpt

    def test_cdata(self):
        no_cdata = ent.Element('tag', self.adpt, text='text', cdata=False)
        with_cdata = ent.Element('tag', self.adpt, text='text', cdata=True)
        self.assertEqual(
            no_cdata.toxmlstring(),
            '<uom:tag xmlns:uom="http://www.ibm.com/xmlns/systems/power/'
            'firmware/uom/mc/2012_10/">text</uom:tag>'.encode('utf-8'))
        self.assertEqual(
            with_cdata.toxmlstring(),
            '<uom:tag xmlns:uom="http://www.ibm.com/xmlns/systems/power/firmwa'
            're/uom/mc/2012_10/"><![CDATA[text]]></uom:tag>'.encode('utf-8'))

    def test_tag_namespace(self):
        el = ent.Element('tag', self.adpt)
        self.assertEqual(el.element.tag, '{http://www.ibm.com/xmlns/systems/po'
                                         'wer/firmware/uom/mc/2012_10/}tag')
        # entities.Element.tag strips the namespace
        self.assertEqual(el.tag, 'tag')
        self.assertEqual(el.namespace, 'http://www.ibm.com/xmlns/systems/powe'
                                       'r/firmware/uom/mc/2012_10/')
        # Test setter
        el.tag = 'gat'
        self.assertEqual(el.element.tag, '{http://www.ibm.com/xmlns/systems/po'
                                         'wer/firmware/uom/mc/2012_10/}gat')
        self.assertEqual(el.tag, 'gat')
        el.namespace = 'foo'
        self.assertEqual(el.namespace, 'foo')
        # Now with no namespace
        el = ent.Element('tag', self.adpt, ns='')
        self.assertEqual(el.element.tag, 'tag')
        self.assertEqual(el.tag, 'tag')
        self.assertEqual(el.namespace, '')
        el.tag = 'gat'
        self.assertEqual(el.element.tag, 'gat')
        self.assertEqual(el.tag, 'gat')
        el.namespace = 'foo'
        self.assertEqual(el.namespace, 'foo')


class TestElementInject(testtools.TestCase):

    def setUp(self):
        super(TestElementInject, self).setUp()
        self.adpt = self.useFixture(fx.AdapterFx()).adpt
        self.ordering_list = ('AdapterType', 'UseNextAvailableSlotID',
                              'RemoteLogicalPartitionID', 'RemoteSlotNumber')
        self.child_at = ent.Element('AdapterType', self.adpt, text='Client')
        self.child_unasi = ent.Element('UseNextAvailableSlotID', self.adpt,
                                       text='true')
        self.child_rlpi1 = ent.Element('RemoteLogicalPartitionID', self.adpt,
                                       text='1')
        self.child_rlpi2 = ent.Element('RemoteLogicalPartitionID', self.adpt,
                                       text='2')
        self.child_rlpi3 = ent.Element('RemoteLogicalPartitionID', self.adpt,
                                       text='3')
        self.child_rsn = ent.Element('RemoteSlotNumber', self.adpt,
                                     text='12')
        self.all_children = [
            self.child_at, self.child_unasi, self.child_rlpi1, self.child_rsn]

    def _mk_el(self, children):
        return ent.Element('VirtualSCSIClientAdapter', self.adpt,
                           attrib={'schemaVersion': 'V1_0'},
                           children=children)

    def assert_expected_children(self, parent, *expected_children):
        """Assert that *children are the children of parent, in that order.

        :param parent: Parent adapter.Element
        :param children: Child adapter.Elements
        """
        actual = list(parent.element)
        expected = [child.element for child in expected_children]
        self.assertEqual(actual, expected)

    def test_no_children(self):
        """Inject when the element has no children - should "append"."""
        el = self._mk_el([])
        el.inject(self.child_rlpi1)
        self.assert_expected_children(el, self.child_rlpi1)
        # Result should be same regardless of other params
        el = self._mk_el([])
        el.inject(self.child_rlpi1, self.ordering_list, replace=False)
        self.assert_expected_children(el, self.child_rlpi1)

    def test_subelement_found_one_replace_true(self):
        """Replace existing child with same tag."""
        el = self._mk_el(self.all_children)
        el.inject(self.child_rlpi2, self.ordering_list)
        self.assert_expected_children(el, self.child_at, self.child_unasi,
                                      self.child_rlpi2, self.child_rsn)
        # Proving default replace=True - same result if specified
        el = self._mk_el(self.all_children)
        el.inject(self.child_rlpi2, self.ordering_list, replace=True)
        self.assert_expected_children(el, self.child_at, self.child_unasi,
                                      self.child_rlpi2, self.child_rsn)

    def test_subelement_found_mult_replace_true(self):
        """Replace existing child with same tag when >1 such children.

        Should replace the last such child.
        """
        el = self._mk_el([self.child_at, self.child_unasi, self.child_rlpi1,
                          self.child_rlpi3, self.child_rsn])
        el.inject(self.child_rlpi2, self.ordering_list)
        self.assert_expected_children(el, self.child_at, self.child_unasi,
                                      self.child_rlpi1, self.child_rlpi2,
                                      self.child_rsn)

    def test_subelement_found_replace_false(self):
        """Inject after existing child(ren) with same tag."""
        el = self._mk_el(self.all_children)
        el.inject(self.child_rlpi2, self.ordering_list, False)
        self.assert_expected_children(el, self.child_at, self.child_unasi,
                                      self.child_rlpi1, self.child_rlpi2,
                                      self.child_rsn)
        el.inject(self.child_rlpi3, self.ordering_list, False)
        self.assert_expected_children(el, self.child_at, self.child_unasi,
                                      self.child_rlpi1, self.child_rlpi2,
                                      self.child_rlpi3, self.child_rsn)

    def test_subelement_not_in_ordering_list(self):
        """Subelement not in ordering list - should append."""
        el = self._mk_el(self.all_children)
        ch = ent.Element('SomeNewElement', self.adpt, text='foo')
        el.inject(ch, ordering_list=self.ordering_list)
        self.assert_expected_children(el, self.child_at, self.child_unasi,
                                      self.child_rlpi1, self.child_rsn, ch)

    def test_first_populated(self):
        """Inject the first child when children are otherwise populated."""
        el = self._mk_el(self.all_children[1:])
        el.inject(self.child_at, self.ordering_list)
        self.assert_expected_children(el, self.child_at, self.child_unasi,
                                      self.child_rlpi1, self.child_rsn)

    def test_first_sparse(self):
        """Inject the first child when children are sparsely populated."""
        # This is most interesting when the existing child is not the one right
        # next to the injectee.
        el = self._mk_el([self.child_rlpi1])
        el.inject(self.child_at, self.ordering_list)
        self.assert_expected_children(el, self.child_at, self.child_rlpi1)

    def test_last_populated(self):
        """Inject the last child when children are otherwise populated."""
        el = self._mk_el(self.all_children[:-1])
        el.inject(self.child_rsn, self.ordering_list)
        self.assert_expected_children(el, self.child_at, self.child_unasi,
                                      self.child_rlpi1, self.child_rsn)

    def test_last_sparse(self):
        """Inject the last child when children are sparsely populated."""
        # This is most interesting when the existing child is not the one right
        # next to the injectee.
        el = self._mk_el([self.child_unasi])
        el.inject(self.child_rsn, self.ordering_list)
        self.assert_expected_children(el, self.child_unasi, self.child_rsn)

    def test_middle_populated(self):
        """Inject a middle child when children are otherwise populated."""
        el = self._mk_el([self.child_at, self.child_unasi, self.child_rsn])
        el.inject(self.child_rlpi1, self.ordering_list)
        self.assert_expected_children(el, self.child_at, self.child_unasi,
                                      self.child_rlpi1, self.child_rsn)

    def test_middle_sparse(self):
        """Inject a middle child when children are sparsely populated."""
        el = self._mk_el([self.child_at, self.child_rsn])
        el.inject(self.child_rlpi1, self.ordering_list)
        self.assert_expected_children(
            el, self.child_at, self.child_rlpi1, self.child_rsn)


class TestElementWrapper(testtools.TestCase):
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
        sea2.element.append(etree.Element('Bob'))
        self.assertFalse(sea1 == sea2)

    def test_inequality_by_subelem_change(self):
        sea1 = self._find_seas(self.nb1)[0]
        sea2 = self._find_seas(self.nb2)[0]
        sea_trunk = sea2.findall('TrunkAdapters/TrunkAdapter')[0]
        pvid = sea_trunk.find('PortVLANID')
        pvid.text = '1'
        self.assertFalse(sea1 == sea2)

    def _find_seas(self, entry):
        """Wrapper for the SEAs."""
        return entry.element.findall('SharedEthernetAdapters/'
                                     'SharedEthernetAdapter')

if __name__ == '__main__':
    unittest.main()
