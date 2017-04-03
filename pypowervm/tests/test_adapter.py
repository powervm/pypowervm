# Copyright 2014, 2015, 2016 IBM Corp.
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

import copy
import errno
import fixtures
import gc
from lxml import etree
import six
import subunit

if six.PY2:
    import __builtin__ as builtins
elif six.PY3:
    import builtins

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
        dict_headers = {
            'content-length': clen, 'x-powered-by': 'Servlet/3.0',
            'set-cookie': ('JSESSIONID=0000a41BnJsGTNQvBGERA3wR1nj:759878cb-4f'
                           '9a-4b05-a09a-3357abfea3b4; Path=/; Secure; HttpOnl'
                           'y, CCFWSESSION=E4C0FFBE9130431DBF1864171ECC6A6E; P'
                           'ath=/; Secure; HttpOnly'),
            'expires': 'Thu, 01 Dec 1994 16:00:00 GMT',
            'x-transaction-id': 'XT10000073',
            'cache-control': 'no-cache="set-cookie, set-cookie2"',
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

    @mock.patch('pypowervm.wrappers.event.Event.wrap')
    @mock.patch('time.sleep')
    def test_event_listener(self, mock_sleep, mock_evt_wrap):

        with mock.patch.object(adp._EventListener, '_get_events') as m_events,\
                mock.patch.object(adp, '_EventPollThread') as mock_poll:
            # With some fake events, event listener can be initialized
            self.sess._sessToken = 'token'.encode('utf-8')
            m_events.return_value = {'general': 'init'}, 'raw_evt', 'wrap_evt'
            event_listen = self.sess.get_event_listener()
            self.assertIsNotNone(event_listen)

            # Register the fake handlers and ensure they are called
            evh = mock.Mock(spec=adp.EventHandler, autospec=True)
            raw_evh = mock.Mock(spec=adp.RawEventHandler, autospec=True)
            wrap_evh = mock.Mock(spec=adp.WrapperEventHandler, autospec=True)
            event_listen.subscribe(evh)
            event_listen.subscribe(raw_evh)
            event_listen.subscribe(wrap_evh)
            events, raw_events, evtwraps = event_listen._get_events()
            event_listen._dispatch_events(events, raw_events, evtwraps)
            evh.process.assert_called_once_with({'general': 'init'})
            raw_evh.process.assert_called_once_with('raw_evt')
            wrap_evh.process.assert_called_once_with('wrap_evt')
            self.assertTrue(mock_poll.return_value.start.called)

            # Ensure getevents() gets legacy events
            self.assertEqual({'general': 'init'}, event_listen.getevents())

        # Outside our patching of _get_events, get the formatted events
        with mock.patch.object(event_listen, '_format_events') as mock_format,\
                mock.patch.object(event_listen.adp, 'read') as mock_read:

            # Ensure exception path doesn't kill the thread
            mock_read.side_effect = Exception()
            self.assertEqual(({}, [], []), event_listen._get_events())
            self.assertEqual(1, mock_read.call_count)
            mock_format.assert_not_called()
            mock_evt_wrap.assert_not_called()
            mock_sleep.assert_called_once_with(5)

            mock_read.reset_mock()
            # side_effect takes precedence over return_value; so kill it.
            mock_read.side_effect = None

            # Fabricate some mock entries, so format gets called.
            mock_read.return_value.feed.entries = (['entry1', 'entry2'])

            self.assertEqual(({}, [], mock_evt_wrap.return_value),
                             event_listen._get_events())
            self.assertEqual(1, mock_read.call_count)
            mock_format.assert_has_calls([mock.call('entry1', {}, []),
                                          mock.call('entry2', {}, [])])
            mock_evt_wrap.assert_called_once_with(mock_read.return_value)

        # Test _format_events
        event_data = [
            {
                'EventType': 'NEW_CLIENT',
                'EventData': 'href1',
                'EventID': '1',
                'EventDetail': 'detail',
            },
            {
                'EventType': 'CACHE_CLEARED',
                'EventData': 'href2',
                'EventID': '2',
                'EventDetail': 'detail2',
            },
            {
                'EventType': 'ADD_URI',
                'EventData': 'LPAR1',
                'EventID': '3',
                'EventDetail': 'detail3',
            },
            {
                'EventType': 'DELETE_URI',
                'EventData': 'LPAR1',
                'EventID': '4',
                'EventDetail': 'detail4',
            },
            {
                'EventType': 'INVALID_URI',
                'EventData': 'LPAR1',
                'EventID': '4',
                'EventDetail': 'detail4',
            },
        ]

        # Setup a side effect that returns events from the test data.
        def get_event_data(item):
            data = event_data[0][item]
            if item == 'EventDetail':
                event_data.pop(0)
            return data

        # Raw events returns a sequence the same as the test data
        raw_result = copy.deepcopy(event_data)
        # Legacy events overwrites some events.
        dict_result = {'general': 'invalidate', 'LPAR1': 'delete'}

        # Build a mock entry
        entry = mock.Mock()
        entry.element.findtext.side_effect = get_event_data
        events = {}
        raw_events = []
        x = len(raw_result)
        while x:
            x -= 1
            event_listen._format_events(entry, events, raw_events)
        self.assertEqual(raw_result, raw_events)
        self.assertEqual(dict_result, events)

    @mock.patch('pypowervm.adapter.Session')
    def test_empty_init(self, mock_sess):
        adp.Adapter()
        mock_sess.assert_called_with()

    def test_no_cache(self):
        self.assertRaises(pvmex.CacheNotSupportedException,
                          adp.Adapter, use_cache=True)

    @mock.patch('requests.Session')
    def test_read(self, mock_session):
        """Test read() method found in the Adapter class."""
        # Init test data
        root_type = 'ManagedSystem'
        root_id = 'caae9209-25e5-35cd-a71a-ed55c03f294d'
        child_type = 'child'
        child_id = 'child'
        suffix_type = 'quick'
        adapter = adp.Adapter(self.sess)

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

    @mock.patch('pypowervm.adapter.Adapter._validate')
    @mock.patch('pypowervm.adapter.Adapter.build_path')
    @mock.patch('pypowervm.adapter.Adapter.read_by_path')
    def test_read2(self, mock_rbp, mock_bld, mock_val):
        """Validate shallow flow & arg passing."""
        adap = adp.Adapter(session=self.sess)
        # Defaults
        self.assertEqual(mock_rbp.return_value, adap.read('root_type'))
        mock_val.assert_called_once_with(
            'read', 'root_type', None, None, None, None, None, None)
        mock_bld.assert_called_once_with(
            'uom', 'root_type', None, None, None, None, None, None, xag=None,
            add_qp=None)
        mock_rbp.assert_called_once_with(
            mock_bld.return_value, None, timeout=-1, auditmemento=None, age=-1,
            sensitive=False, helpers=None)
        # Specified kwargs
        mock_val.reset_mock()
        mock_bld.reset_mock()
        mock_rbp.reset_mock()
        self.assertEqual(mock_rbp.return_value, adap.read(
            'root_type', root_id='root_id', child_type='child_type',
            child_id='child_id', suffix_type='suffix_type',
            suffix_parm='suffix_parm', detail='detail', service='service',
            etag='etag', timeout='timeout', auditmemento='auditmemento',
            age='age', xag='xag', sensitive='sensitive', helpers='helpers',
            add_qp='add_qp'))
        mock_val.assert_called_once_with(
            'read', 'root_type', 'root_id', 'child_type', 'child_id',
            'suffix_type', 'suffix_parm', 'detail')
        mock_bld.assert_called_once_with(
            'service', 'root_type', 'root_id', 'child_type', 'child_id',
            'suffix_type', 'suffix_parm', 'detail', xag='xag', add_qp='add_qp')
        mock_rbp.assert_called_once_with(
            mock_bld.return_value, 'etag', timeout='timeout',
            auditmemento='auditmemento', age='age', sensitive='sensitive',
            helpers='helpers')

    @mock.patch('pypowervm.adapter.Adapter.extend_path')
    def test_build_path(self, mock_exp):
        """Validate build_path."""
        adap = adp.Adapter(session=self.sess)
        # Defaults
        self.assertEqual(mock_exp.return_value, adap.build_path(
            'service', 'root_type'))
        mock_exp.assert_called_once_with(
            '/rest/api/service/root_type', suffix_type=None, suffix_parm=None,
            detail=None, xag=None, add_qp=None)
        # child specs ignored if no root ID
        mock_exp.reset_mock()
        self.assertEqual(mock_exp.return_value, adap.build_path(
            'service', 'root_type', child_type='child_type',
            child_id='child_id'))
        mock_exp.assert_called_once_with(
            '/rest/api/service/root_type', suffix_type=None, suffix_parm=None,
            detail=None, xag=None, add_qp=None)
        # child ID ignored if no child type
        mock_exp.reset_mock()
        self.assertEqual(mock_exp.return_value, adap.build_path(
            'service', 'root_type', root_id='root_id', child_id='child_id'))
        mock_exp.assert_called_once_with(
            '/rest/api/service/root_type/root_id', suffix_type=None,
            suffix_parm=None, detail=None, xag=None, add_qp=None)
        # Specified kwargs (including full child spec
        mock_exp.reset_mock()
        self.assertEqual(mock_exp.return_value, adap.build_path(
            'service', 'root_type', root_id='root_id', child_type='child_type',
            child_id='child_id', suffix_type='suffix_type',
            suffix_parm='suffix_parm', detail='detail', xag='xag',
            add_qp='add_qp'))
        mock_exp.assert_called_once_with(
            '/rest/api/service/root_type/root_id/child_type/child_id',
            suffix_type='suffix_type', suffix_parm='suffix_parm',
            detail='detail', xag='xag', add_qp='add_qp')

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
        hdr_json = '*/*'
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
        adapter = adp.Adapter(self.sess)
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
        adapter = adp.Adapter(self.sess)

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
        adapter = adp.Adapter(self.sess)

        # Mock data
        filedesc_mock = mock.MagicMock()
        filedesc_mock.findtext.side_effect = ['uuid', 'mime']

        with mock.patch.object(adapter, '_request') as mock_request:
            adapter.upload_file(filedesc_mock, None)

        # Validate
        expected_headers = {'Accept': 'application/vnd.ibm.powervm.web+xml',
                            'Content-Type': 'mime'}
        expected_path = '/rest/api/web/File/contents/uuid'
        mock_request.assert_called_once_with(
            'PUT', expected_path, helpers=None, headers=expected_headers,
            timeout=-1, auditmemento=None, filehandle=None, chunksize=65536)

    def _test_upload_request(self, mock_rq, mock_fh, fhdata):
        """Test an upload requests with different kinds of "filehandle"."""
        adapter = adp.Adapter(self.sess)
        mock_fd = mock.Mock(findtext=mock.Mock(side_effect=['uuid', 'mime']))

        def check_request(method, url, data=None, headers=None, timeout=None):
            """Validate the session.request call."""
            self.assertEqual('PUT', method)
            self.assertEqual(
                self.sess.dest + '/rest/api/web/File/contents/uuid', url)
            # Verify that data is iterable
            self.assertEqual(fhdata, [chunk for chunk in data])
            return mock.Mock(status_code=c.HTTPStatus.OK_NO_CONTENT)
        mock_rq.side_effect = check_request

        adapter.upload_file(mock_fd, mock_fh)

    @mock.patch('requests.sessions.Session.request')
    def test_upload_request_iter(self, mock_rq):
        """Test an upload request with an iterable."""
        fhdata = ['one', 'two']
        self._test_upload_request(mock_rq, fhdata, fhdata)

    @mock.patch('requests.sessions.Session.request')
    def test_upload_request_fh(self, mock_rq):
        """Test an upload request with a filehandle."""
        # filehandle is a read()able
        fhdata = ['one', 'two']
        mock_fh = mock.Mock(read=mock.Mock(side_effect=fhdata))
        self._test_upload_request(mock_rq, mock_fh, fhdata)
        # Make sure the file handle's read method was invoked
        mock_fh.read.assert_has_calls([mock.call(65536)] * len(fhdata))

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
        adapter = adp.Adapter(self.sess)

        path = adapter.extend_path('basepath', suffix_type='suffix',
                                   suffix_parm='suffix_parm',
                                   detail='detail',
                                   xag=[c.XAG.VIO_FMAP])

        expected_path = ('basepath/suffix/suffix_parm?detail=detail&'
                         'group=ViosFCMapping')
        self._assert_paths_equivalent(expected_path, path)

        # Multiple XAGs in a set
        path = adapter.extend_path('basepath', suffix_type='suffix',
                                   suffix_parm='suffix_parm',
                                   detail='detail',
                                   xag={c.XAG.VIO_FMAP, c.XAG.VIO_NET})

        expected_path = ('basepath/suffix/suffix_parm?detail=detail&'
                         'group=ViosFCMapping,ViosNetwork')
        self._assert_paths_equivalent(expected_path, path)

        # Verify sorting
        path = adapter.extend_path('basepath', suffix_type='suffix',
                                   suffix_parm='suffix_parm',
                                   detail='detail',
                                   xag=[c.XAG.VIO_NET, c.XAG.VIO_FMAP])

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

        # Additional queryparams (add_qp)
        # Explicit None
        self._assert_paths_equivalent(
            'basepath', adapter.extend_path('basepath', xag=[], add_qp=None))
        # Proper escaping
        self._assert_paths_equivalent(
            'basepath?one=%23%24%25%5E%26',
            adapter.extend_path('basepath', xag=[], add_qp=[('one', '#$%^&')]))
        # Duplicated keys (order preserved) and proper handling of non-strings
        self._assert_paths_equivalent(
            'basepath?1=3&1=2',
            adapter.extend_path('basepath', xag=[], add_qp=[(1, 3), (1, 2)]))
        # Proper behavior combined with implicit xag
        self._assert_paths_equivalent(
            'basepath?group=None&key=value&something=else',
            adapter.extend_path(
                'basepath', add_qp=[('key', 'value'), ('something', 'else')]))
        # Combined with xags and an existing querystring
        self._assert_paths_equivalent(
            'basepath?already=here&group=a,b,c&key=value&something=else',
            adapter.extend_path(
                'basepath?already=here', xag=['a', 'b', 'c'],
                add_qp=[('key', 'value'), ('something', 'else')]))

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
        adapter = adp.Adapter(self.sess)

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
        adapter = adp.Adapter(self.sess)
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
        self.assertEqual(1, mock_log.warning.call_count)

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

    @mock.patch('pypowervm.entities.Feed.unmarshal_atom_feed')
    @mock.patch('pypowervm.entities.Entry.unmarshal_atom_entry')
    @mock.patch('lxml.etree.fromstring')
    def test_extract_atom(self, mock_fromstring, mock_unm_ent, mock_unm_feed):
        resp = adp.Response('meth', '/rest/api/uom/Debug/SetLoggingLevel',
                            'status', 'reason', 'headers', body='body')
        feed_ret = mock.Mock(tag=etree.QName(c.ATOM_NS, 'feed'))
        entry_ret = mock.Mock(tag=etree.QName(c.ATOM_NS, 'entry'))

        # Empty content; "Response is not an Atom feed/entry"
        mock_fromstring.return_value = None
        self.assertIsNotNone(resp._extract_atom())
        mock_fromstring.assert_called_with('body')
        mock_unm_feed.assert_not_called()
        mock_unm_ent.assert_not_called()

        # Unmarshal feed (returns None)
        mock_fromstring.return_value = feed_ret
        self.assertIsNone(resp._extract_atom())
        mock_unm_feed.assert_called_once_with(feed_ret, resp)
        mock_unm_ent.assert_not_called()
        mock_unm_feed.reset_mock()

        # Unmarshal entry (returns None)
        mock_fromstring.return_value = entry_ret
        self.assertIsNone(resp._extract_atom())
        mock_unm_ent.assert_called_once_with(entry_ret, resp)
        mock_unm_feed.assert_not_called()
        mock_unm_ent.reset_mock()

        # Unmarshal a 'Debug' response (returns None)
        mock_fromstring.return_value = mock.Mock(tag='debug output')
        self.assertIsNone(resp._extract_atom())
        mock_unm_feed.assert_not_called()
        mock_unm_ent.assert_not_called()

        # 'fromstring' raises.  Make sure the return message came from the
        # right place (will include the exception text)
        mock_fromstring.side_effect = Exception("test_extract_atom")
        self.assertIn("test_extract_atom", resp._extract_atom())
        mock_unm_feed.assert_not_called()
        mock_unm_ent.assert_not_called()


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


class TestAdapterClasses(subunit.IsolatedTestCase, testtools.TestCase):
    def setUp(self):
        super(TestAdapterClasses, self).setUp()
        self.mock_logoff = self.useFixture(
            fixtures.MockPatchObject(adp.Session, '_logoff')).mock
        self.mock_logon = self.useFixture(
            fixtures.MockPatchObject(adp.Session, '_logon')).mock
        self.mock_events = self.useFixture(
            fixtures.MockPatchObject(adp._EventListener, '_get_events')).mock
        # Mock the initial events coming in on start
        self.mock_events.return_value = {'general': 'init'}, [], []

    def test_instantiation(self):
        """Direct instantiation of EventListener is not allowed."""
        # Get a session
        sess = adp.Session()
        # Now get the EventListener
        self.assertRaises(TypeError, adp.EventListener, sess)

        # Mock the session token like we logged on
        sess._sessToken = 'token'.encode('utf-8')
        # Ensure we get an EventListener
        self.assertIsInstance(sess.get_event_listener(), adp.EventListener)

    def test_shutdown_session(self):
        """Test garbage collection of the session.

        Ensures the Session can be properly garbage collected.
        """
        # Get a session
        sess = adp.Session()
        # Mock the session token like we logged on
        sess._sessToken = 'token'.encode('utf-8')
        # It should have logged on but not off.
        self.assertTrue(self.mock_logon.called)
        self.assertFalse(self.mock_logoff.called)

        # Get an event listener to test the weak references
        event_listen = sess.get_event_listener()

        # Test the circular reference (but one link is weak)
        sess.hello = 'hello'
        self.assertEqual(sess.hello, event_listen.adp.session.hello)

        # There should be 1 reference to the session (ours)
        self.assertEqual(1, len(gc.get_referrers(sess)))

    def test_shutdown_adapter(self):
        """Test garbage collection of the session, event listener.

        Ensures the proper shutdown of the session and event listener when
        we start with constructing an Adapter, implicit session and
        EventListener.
        """
        # Get Adapter, implicit session
        adapter = adp.Adapter()
        adapter.session._sessToken = 'token'.encode('utf-8')
        # Get construct and event listener
        adapter.session.get_event_listener()

        # Turn off the event listener
        adapter.session.get_event_listener().shutdown()
        # Session is still active
        self.assertFalse(self.mock_logoff.called)

        # The only thing that refers the adapter is our reference
        self.assertEqual(1, len(gc.get_referrers(adapter)))


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
        # etree.Element doesn't implement __eq__, so different instances of the
        # same Element aren't "equal".  Compare XML strings instead.
        actual = [etree.tostring(elem) for elem in list(parent.element)]
        expected = [etree.tostring(chld.element) for chld in expected_children]
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
