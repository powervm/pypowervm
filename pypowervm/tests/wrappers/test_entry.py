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

import copy

from lxml import etree
import mock
import six

import unittest

import pypowervm.adapter as apt
import pypowervm.const as pc
import pypowervm.entities as ent
from pypowervm.tests.wrappers.util import pvmhttp
import pypowervm.wrappers.cluster as clust
import pypowervm.wrappers.entry_wrapper as ewrap
import pypowervm.wrappers.network as net
import pypowervm.wrappers.storage as stor

NET_BRIDGE_FILE = 'fake_network_bridge.txt'


def _assert_clusters_equal(tc, cl1, cl2):
    tc.assertEqual(cl1.name, cl2.name)
    tc.assertEqual(cl1.repos_pv.name, cl2.repos_pv.name)
    tc.assertEqual(cl1.repos_pv.udid, cl2.repos_pv.udid)
    tc.assertEqual(cl1.nodes[0].hostname, cl2.nodes[0].hostname)


class SubWrapper(ewrap.Wrapper):
    schema_type = 'SubWrapper'
    _type_and_uuid = 'SubWrapper_TestClass'

    def __init__(self, **kwargs):
        class Txt(object):
            def __init__(self, val):
                self.text = val

        super(SubWrapper, self).__init__()
        self.data = dict((k, Txt(v)) for k, v in six.iteritems(kwargs))

    def _find(self, prop_name, use_find_all=False):
        try:
            return self.data[prop_name]
        except KeyError:
            return None


class TestWrapper(unittest.TestCase):
    def test_get_val_str(self):
        w = SubWrapper(one='1', foo='foo', empty='')
        self.assertEqual(w._get_val_str('one'), '1')
        self.assertEqual(w._get_val_str('foo'), 'foo')
        self.assertEqual(w._get_val_str('empty'), '')
        self.assertIsNone(w._get_val_str('nonexistent'))
        self.assertEqual(w._get_val_str('nonexistent', default='10'), '10')

    def test_get_val_int(self):
        w = SubWrapper(one='1', nan='foo', empty='')
        self.assertEqual(w._get_val_int('one'), 1)
        self.assertIsNone(w._get_val_int('nan'))
        self.assertIsNone(w._get_val_int('empty'))
        self.assertIsNone(w._get_val_int('nonexistent'))
        self.assertEqual(w._get_val_int('nonexistent', default=10), 10)

    def test_get_val_float(self):
        w = SubWrapper(one='1', two_point_two='2.2', nan='foo', empty='')
        self.assertAlmostEqual(w._get_val_float('one'), 1)
        self.assertAlmostEqual(w._get_val_float('two_point_two'), 2.2)
        self.assertIsNone(w._get_val_float('nan'))
        self.assertIsNone(w._get_val_float('empty'))
        self.assertIsNone(w._get_val_float('nonexistent'))
        self.assertAlmostEqual(w._get_val_float('one', default=2), 1)
        self.assertAlmostEqual(w._get_val_float('two_point_two', default=3),
                               2.2)
        self.assertAlmostEqual(w._get_val_float('nan', default=1), 1)
        self.assertAlmostEqual(w._get_val_float('empty', default=1), 1)
        self.assertAlmostEqual(w._get_val_int('nonexistent', default=1.7), 1.7)

    def test_get_val_bool(self):
        w = SubWrapper(one='1', t='true', T='TRUE', f='false', F='FALSE',
                       empty='')
        self.assertTrue(w._get_val_bool('t'))
        self.assertTrue(w._get_val_bool('T'))
        self.assertFalse(w._get_val_bool('one'))
        self.assertFalse(w._get_val_bool('empty'))
        self.assertFalse(w._get_val_bool('f'))
        self.assertFalse(w._get_val_bool('F'))
        self.assertFalse(w._get_val_bool('nonexistent'))
        self.assertTrue(w._get_val_bool('t', default=False))
        self.assertTrue(w._get_val_bool('T', default=False))
        self.assertFalse(w._get_val_bool('one', default=True))
        self.assertFalse(w._get_val_bool('empty', default=True))
        self.assertFalse(w._get_val_bool('f', default=True))
        self.assertFalse(w._get_val_bool('F', default=True))
        self.assertTrue(w._get_val_bool('nonexistent', default=True))


class TestEntryWrapper(unittest.TestCase):

    def test_etag(self):
        fake_entry = ent.Entry({}, ent.Element('fake_entry'))
        etag = '1234'
        ew = ewrap.EntryWrapper.wrap(fake_entry, etag=etag)
        self.assertEqual(etag, ew.etag)

        ew = ewrap.EntryWrapper.wrap(fake_entry)
        self.assertEqual(None, ew.etag)

    def test_load(self):
        etag = '1234'
        resp = apt.Response('reqmethod', 'reqpath', 'status',
                            'reason', dict(etag=etag))

        # Entry or Feed is not set, so expect an exception
        self.assertRaises(KeyError, ewrap.EntryWrapper.wrap, resp)

        # Set an entry...
        entry = ent.Entry({}, ent.Element('entry'))
        resp.entry = entry

        # Run
        ew = ewrap.EntryWrapper.wrap(resp)

        # Validate
        self.assertEqual(entry, ew.entry)
        self.assertEqual(etag, ew.etag)

        # Create a response with no headers
        resp2 = apt.Response('reqmethod', 'reqpath', 'status', 'reason', {})
        resp2.entry = entry
        # Run
        ew = ewrap.EntryWrapper.wrap(resp2)
        # Validate the etag is None since there were no headers
        self.assertEqual(None, ew.etag)

        # Wipe our entry, add feed.
        resp.entry = None
        e1 = ent.Entry({'etag': '1'}, ent.Element('e1'))
        e2 = ent.Entry({'etag': '2'}, ent.Element('e2'))
        resp.feed = ent.Feed({}, [e1, e2])

        # Run
        ew = ewrap.EntryWrapper.wrap(resp)

        # Validate
        self.assertEqual(e1, ew[0].entry)
        self.assertEqual('1', ew[0].etag)
        self.assertEqual(e2, ew[1].entry)
        self.assertEqual('2', ew[1].etag)


class TestElementWrapper(unittest.TestCase):
    """Tests for the ElementWrapper class."""

    def setUp(self):
        super(TestElementWrapper, self).setUp()
        self.resp = pvmhttp.load_pvm_resp(NET_BRIDGE_FILE).get_response()
        self.nb1 = ewrap.EntryWrapper.wrap(self.resp.feed.entries[0])
        self.resp2 = pvmhttp.load_pvm_resp(NET_BRIDGE_FILE).get_response()
        self.nb2 = ewrap.EntryWrapper.wrap(self.resp2.feed.entries[0])

    def test_equality(self):
        """Validates that two elements loaded from the same data is equal."""
        sea1 = self._find_seas(self.nb1.entry)[0]
        sea2 = self._find_seas(self.nb2.entry)[0]
        self.assertTrue(sea1 == sea2)

        # Change the other SEA
        sea2.element.element.append(etree.Element('Bob'))
        self.assertFalse(sea1 == sea2)

    def test_inequality_by_subelem_change(self):
        sea1 = self._find_seas(self.nb1.entry)[0]
        sea2 = self._find_seas(self.nb2.entry)[0]
        sea_trunk = sea2.element.findall('TrunkAdapters/TrunkAdapter')[1]
        pvid = sea_trunk.find('PortVLANID')
        pvid.text = '1'
        self.assertFalse(sea1 == sea2)

    def _find_seas(self, entry):
        """Wrapper for the SEAs."""
        found = entry.element.find('SharedEthernetAdapters')
        return ewrap.WrapperElemList(found, net.SEA)

    def test_fresh_element(self):
        # Default: UOM namespace, no <Metadata/>
        class MyElement(ewrap.ElementWrapper):
            schema_type = 'SomePowerObject'
        myel = MyElement._bld()
        self.assertEqual(myel.schema_type, 'SomePowerObject')
        self.assertEqual(myel.element.toxmlstring(),
                         '<SomePowerObject/>'.encode("utf-8"))

        # Can override namespace and attrs and trigger inclusion of <Metadata/>
        class MyElement3(ewrap.ElementWrapper):
            schema_type = 'SomePowerObject'
            default_attrib = {'foo': 'bar'}
            schema_ns = 'baz'
            has_metadata = True
        myel = MyElement3._bld()
        self.assertEqual(
            myel.element.toxmlstring(),
            '<ns0:SomePowerObject xmlns:ns0="baz" foo="bar"><ns0:Metadata>'
            '<ns0:Atom/></ns0:Metadata></ns0:SomePowerObject>'.encode("utf-8"))

        # Same thing, but via the decorator
        @ewrap.ElementWrapper.pvm_type('SomePowerObject', has_metadata=True,
                                       ns='baz', attrib={'foo': 'bar'})
        class MyElement4(ewrap.ElementWrapper):
            pass
        myel = MyElement4._bld()
        self.assertEqual(
            myel.element.toxmlstring(),
            '<ns0:SomePowerObject xmlns:ns0="baz" foo="bar"><ns0:Metadata>'
            '<ns0:Atom/></ns0:Metadata></ns0:SomePowerObject>'.encode("utf-8"))

        # Now 'SomePowerObject' is registered.  Prove that we can use wrap() to
        # instantiate MyElement4 straight from ElementWrapper.
        el = ent.Element('SomePowerObject', ns='baz', attrib={'foo': 'bar'})
        w = ewrap.ElementWrapper.wrap(el)
        self.assertIsInstance(w, MyElement4)

    def test_href(self):
        path = 'LoadGroups/LoadGroup/VirtualNetworks/link'
        # Get all
        hrefs = self.nb1.get_href(path)
        self.assertEqual(len(hrefs), 13)
        self.assertEqual(
            hrefs[2],
            'https://9.1.2.3:12443/rest/api/uom/ManagedSystem/726e9cb3-6576-3d'
            'f5-ab60-40893d51d074/VirtualNetwork/f417df1f-ff3a-35e5-a428-ab3b8'
            '2be7717')
        # Request one - should return None
        hrefs = self.nb1.get_href(path, one_result=True)
        self.assertIsNone(hrefs)
        # set_href should refuse to set multiple links
        self.assertRaises(ValueError, self.nb1.set_href, path, 'foo')

        # Drill down to the (only) SEA
        sea = ewrap.ElementWrapper.wrap(
            self.nb1._find('SharedEthernetAdapters/SharedEthernetAdapter'))
        path = 'AssignedVirtualIOServer'
        hrefs = sea.get_href(path)
        self.assertEqual(len(hrefs), 1)
        self.assertEqual(
            hrefs[0],
            'https://9.1.2.3:12443/rest/api/uom/ManagedSystem/726e9cb3-6576-3d'
            'f5-ab60-40893d51d074/VirtualIOServer/691019AF-506A-4896-AADE-607E'
            '21FA93EE')
        # Now make sure one_result returns the string (not a list)
        href = sea.get_href(path, one_result=True)
        self.assertEqual(
            href,
            'https://9.1.2.3:12443/rest/api/uom/ManagedSystem/726e9cb3-6576-3d'
            'f5-ab60-40893d51d074/VirtualIOServer/691019AF-506A-4896-AADE-607E'
            '21FA93EE')
        # Test setter
        sea.set_href(path, 'foo')
        self.assertEqual(sea.get_href(path, one_result=True), 'foo')
        # Now try setting one that doesn't exist.  First on a top-level path.
        path = 'NewElement'
        sea.set_href(path, 'bar')
        self.assertEqual(sea.get_href(path, one_result=True), 'bar')
        # ...and now on a nested path.
        path = 'BackingDeviceChoice/EthernetBackingDevice/NewLink'
        sea.set_href(path, 'baz')
        self.assertEqual(sea.get_href(path, one_result=True), 'baz')


class TestWrapperElemList(unittest.TestCase):
    """Tests for the WrapperElemList class."""

    def setUp(self):
        super(TestWrapperElemList, self).setUp()
        resp = pvmhttp.load_pvm_resp(NET_BRIDGE_FILE).get_response()
        nb = resp.feed.entries[0]
        self.wrapper = ewrap.EntryWrapper.wrap(nb)
        sea_elem = self.wrapper.element.find('SharedEthernetAdapters')

        self.elem_set = ewrap.WrapperElemList(sea_elem, net.SEA)

    def test_get(self):
        self.assertIsNotNone(self.elem_set[0])
        self.assertRaises(IndexError, lambda a, i: a[i], self.elem_set, 1)

    def test_length(self):
        self.assertEqual(1, len(self.elem_set))

    def test_append(self):
        sea_add = ewrap.ElementWrapper.wrap(
            ent.Element('SharedEthernetAdapter'))
        self.assertEqual(1, len(self.elem_set))

        # Test Append
        self.elem_set.append(sea_add)
        self.assertEqual(2, len(self.elem_set))

        # Make sure we can also remove what was just added.
        self.elem_set.remove(sea_add)
        self.assertEqual(1, len(self.elem_set))

    def test_extend(self):
        seas = [
            ewrap.ElementWrapper.wrap(ent.Element('SharedEthernetAdapter')),
            ewrap.ElementWrapper.wrap(ent.Element('SharedEthernetAdapter'))
        ]
        self.assertEqual(1, len(self.elem_set))
        self.elem_set.extend(seas)
        self.assertEqual(3, len(self.elem_set))

        # Make sure that we can also remove what we added.  We remove a
        # logically identical element to test the equivalence function
        e = ewrap.ElementWrapper.wrap(ent.Element('SharedEthernetAdapter'))
        self.elem_set.remove(e)
        self.elem_set.remove(e)
        self.assertEqual(1, len(self.elem_set))

    def test_in(self):
        # This really does fail without __contains__
        elem = self.elem_set[0]
        self.assertIn(elem, self.elem_set)

    def test_index(self):
        elem = self.elem_set[0]
        self.assertEqual(self.elem_set.index(elem), 0)


class TestActionableList(unittest.TestCase):
    """Tests for the Actionable List class."""

    def test_extend(self):
        def test(new_list):
            self.assertEqual([1, 2, 3, 4, 5], new_list)
        l = ewrap.ActionableList([1, 2, 3], test)

        # Extend here.
        l.extend([4, 5])
        self.assertEqual(5, len(l))
        self.assertEqual(5, l[4])

    def test_append(self):
        def test(new_list):
            self.assertEqual([1, 2, 3, 4], new_list)
        l = ewrap.ActionableList([1, 2, 3], test)

        # Append here.
        l.append(4)
        self.assertEqual(4, len(l))
        self.assertEqual(4, l[3])

    def test_remove(self):
        def test(new_list):
            self.assertEqual([1, 3], new_list)
        l = ewrap.ActionableList([1, 2, 3], test)

        # Remove here.
        l.remove(2)
        self.assertEqual(2, len(l))
        self.assertEqual(3, l[1])

    def test_insert(self):
        def test(new_list):
            self.assertEqual([1, 2, 3, 4], new_list)
        l = ewrap.ActionableList([1, 2, 3], test)

        # Insert here.
        l.insert(3, 4)
        self.assertEqual(4, len(l))
        self.assertEqual(4, l[3])

    def test_pop(self):
        def test(new_list):
            self.assertEqual([1, 2], new_list)
        l = ewrap.ActionableList([1, 2, 3], test)

        # Pop here.
        l.pop(2)
        self.assertEqual(2, len(l))
        self.assertEqual(2, l[1])

    def test_complex_path(self):
        function = mock.MagicMock()

        l = ewrap.ActionableList([1, 2, 3], function)
        self.assertEqual(3, len(l))
        self.assertEqual(3, l[2])

        # Try extending
        l.extend([4, 5])
        self.assertEqual(5, len(l))
        self.assertEqual(5, l[4])

        # Try appending
        l.append(6)
        self.assertEqual(6, len(l))
        self.assertEqual(6, l[5])

        # Try removing
        l.remove(6)
        self.assertEqual(5, len(l))
        self.assertEqual(5, l[4])

        # Try inserting
        l.insert(5, 6)
        self.assertEqual(6, len(l))
        self.assertEqual(6, l[5])

        # Try popping
        self.assertEqual(6, l.pop(5))
        self.assertEqual(5, len(l))
        self.assertEqual(5, l[4])

        # Make sure our function was called each time
        self.assertEqual(5, function.call_count)


class TestSearch(unittest.TestCase):
    """Tests for EntryWrapper.search()."""

    def setUp(self):
        super(TestSearch, self).setUp()
        self.adp = apt.Adapter(mock.patch('requests.Session'), use_cache=False)

    def _validate_request(self, path, *feedcontents):
        def validate_request(meth, _path, *args, **kwargs):
            self.assertTrue(_path.endswith(path))
            resp = apt.Response('meth', 'path', 'status', 'reason', {},
                                reqheaders={'Accept': ''})
            resp.feed = ent.Feed({}, feedcontents)
            return resp
        return validate_request

    @mock.patch('pypowervm.adapter.Adapter._request')
    def test_good(self, mock_rq):
        mock_rq.side_effect = self._validate_request(
            "/rest/api/uom/Cluster/search/(ClusterName=='cl1')?group=None",
            clust.Cluster.bld('cl1', stor.PV.bld('hdisk1', 'udid1'),
                              clust.Node.bld(hostname='vios1')).entry)

        clwraps = clust.Cluster.search(self.adp, name='cl1')
        self.assertEqual(len(clwraps), 1)
        cl = clwraps[0]
        self.assertIsInstance(cl, clust.Cluster)
        self.assertEqual(cl.name, 'cl1')
        self.assertEqual(cl.repos_pv.name, 'hdisk1')
        self.assertEqual(cl.nodes[0].hostname, 'vios1')

    @mock.patch('pypowervm.adapter.Adapter._request')
    def test_negate(self, mock_rq):
        mock_rq.side_effect = self._validate_request(
            "/rest/api/uom/Cluster/search/(ClusterName!='cl1')?group=None")
        clwraps = clust.Cluster.search(self.adp, negate=True, name='cl1')
        self.assertEqual(clwraps, [])

    def test_no_search_keys(self):
        """Ensure a wrapper with no search_keys member gives AttributeError."""
        with self.assertRaises(AttributeError):
            clust.Node.search(self.adp, foo='bar')

    def test_no_such_search_key(self):
        """Ensure an invalid search key gives ValueError."""
        with self.assertRaises(ValueError):
            clust.Cluster.search(self.adp, foo='bar')

    @mock.patch('pypowervm.adapter.Adapter._request')
    def test_quote(self, mock_rq):
        """Ensure special chars in the search value are properly encoded."""
        mock_rq.side_effect = self._validate_request(
            "/rest/api/uom/Cluster/search/(ClusterName=="
            "'%3B%2F%3F%3A%40%20%26%3D%2B%24%2C')?group=None")
        clust.Cluster.search(self.adp, name=';/?:@ &=+$,')

    @mock.patch('pypowervm.adapter.Adapter.read')
    def test_search_by_feed(self, mock_read):
        """Test a search key that's not in search_keys."""
        def validate_read(root_type, xag='bogus'):
            # This should be called by _search_by_feed, not by search.
            # Otherwise, we'll get an exception on the arg list.
            self.assertEqual(net.NetBridge.schema_type, root_type)
            self.assertEqual([pc.XAG_NONE], xag)
            return pvmhttp.load_pvm_resp(NET_BRIDGE_FILE).get_response()
        mock_read.side_effect = validate_read
        # vswitch_id is particularly cool because it's not just a top-level
        # child element - it dives into the SEAs, finds the primary trunk
        # adapter, and returns the vswitch ID from there.
        rets = net.NetBridge.search(self.adp, vswitch_id=0)
        self.assertEqual(1, len(rets))
        nb = rets[0]
        self.assertIsInstance(nb, net.NetBridge)
        self.assertEqual('d648eb60-4d39-34ad-ae2b-928d8c9577ad', nb.uuid)
        # Now do a search that returns more than one item
        rets = net.NetBridge.search(self.adp, pvid=1)
        self.assertEqual(2, len(rets))
        self.assertIsInstance(rets[0], net.NetBridge)
        self.assertIsInstance(rets[1], net.NetBridge)
        self.assertEqual({'d648eb60-4d39-34ad-ae2b-928d8c9577ad',
                          '764f3423-04c5-3b96-95a3-4764065400bd'},
                         {nb.uuid for nb in rets})


class TestRefresh(unittest.TestCase):
    """Tests for Adapter.refresh()."""

    clust_uuid = 'cluster_uuid'
    clust_href = 'https://server:12443/rest/api/uom/Cluster' + clust_uuid

    def setUp(self):
        super(TestRefresh, self).setUp()
        self.adp = apt.Adapter(mock.patch('requests.Session'), use_cache=False)
        props = {'id': self.clust_uuid, 'links': {'SELF': [self.clust_href]}}
        self.old_etag = '123'
        self.clust_old = clust.Cluster.bld(
            'mycluster', stor.PV.bld('hdisk1', 'udid1'),
            clust.Node.bld('hostname1'))
        self.clust_old._etag = None
        self.clust_old.entry.properties = props
        self.new_etag = '456'
        self.clust_new = clust.Cluster.bld(
            'mycluster', stor.PV.bld('hdisk2', 'udid2'),
            clust.Node.bld('hostname2'))
        self.clust_new._etag = self.new_etag
        self.clust_new.entry.properties = props
        self.resp304 = apt.Response(
            'meth', 'path', 304, 'reason', {'etag': self.old_etag})
        self.resp200old = apt.Response(
            'meth', 'path', 200, 'reason', {'etag': self.old_etag})
        self.resp200old.entry = self.clust_old.entry
        self.resp200new = apt.Response(
            'meth', 'path', 200, 'reason', {'etag': self.new_etag})
        self.resp200new.entry = self.clust_new.entry

    def _mock_read_by_href(self, in_etag, out_resp):
        def read_by_href(href, etag, *args, **kwargs):
            self.assertEqual(href, self.clust_href)
            self.assertEqual(etag, in_etag)
            return out_resp
        return read_by_href

    @mock.patch('pypowervm.adapter.Adapter.read_by_href')
    def test_no_etag(self, mock_read):
        mock_read.side_effect = self._mock_read_by_href(
            None, self.resp200old)
        clust_old_save = copy.deepcopy(self.clust_old)
        clust_refreshed = self.clust_old.refresh(self.adp)
        _assert_clusters_equal(self, clust_old_save, clust_refreshed)

    @mock.patch('pypowervm.adapter.Adapter.read_by_href')
    def test_etag_match(self, mock_read):
        mock_read.side_effect = self._mock_read_by_href(
            self.old_etag, self.resp304)
        self.clust_old._etag = self.old_etag
        clust_refreshed = self.clust_old.refresh(self.adp)
        # On an etag match, refresh should return the same instance
        self.assertEqual(self.clust_old, clust_refreshed)

    @mock.patch('pypowervm.adapter.Adapter.read_by_href')
    def test_etag_no_match(self, mock_read):
        mock_read.side_effect = self._mock_read_by_href(
            self.old_etag, self.resp200new)
        self.clust_old._etag = self.old_etag
        clust_new_save = copy.deepcopy(self.clust_new)
        clust_refreshed = self.clust_old.refresh(self.adp)
        _assert_clusters_equal(self, clust_new_save, clust_refreshed)


class TestUpdate(unittest.TestCase):
    clust_uuid = 'cluster_uuid'
    clust_path = '/rest/api/uom/Cluster' + clust_uuid
    clust_href = 'https://server:12443' + clust_path
    clust_etag = '123'

    def setUp(self):
        super(TestUpdate, self).setUp()
        self.adp = apt.Adapter(mock.patch('requests.Session'), use_cache=False)
        props = {'id': self.clust_uuid, 'links': {'SELF': [self.clust_href]}}
        self.cl = clust.Cluster.bld(
            'mycluster', stor.PV.bld('hdisk1', 'udid1'),
            clust.Node.bld('hostname1'))
        self.cl._etag = self.clust_etag
        self.cl.entry.properties = props

    @mock.patch('pypowervm.adapter.Adapter.update_by_path')
    def test_update(self, mock_ubp):
        new_etag = '456'
        resp = apt.Response('meth', 'path', 200, 'reason', {'etag': new_etag})
        resp.entry = self.cl.entry
        mock_ubp.return_value = resp
        newcl = self.cl.update(self.adp)
        mock_ubp.assert_called_with(self.cl, self.clust_etag,
                                    self.clust_path + '?group=None')
        _assert_clusters_equal(self, self.cl, newcl)
        self.assertEqual(newcl.etag, new_etag)

    @mock.patch('pypowervm.adapter.Adapter.update_by_path')
    def test_update_xag(self, mock_ubp):
        new_etag = '456'
        resp = apt.Response('meth', 'path', 200, 'reason', {'etag': new_etag})
        resp.entry = self.cl.entry
        mock_ubp.return_value = resp
        newcl = self.cl.update(self.adp, xag=['one', 'two', 'three'])
        mock_ubp.assert_called_with(self.cl, self.clust_etag,
                                    self.clust_path + '?group=one,three,two')
        _assert_clusters_equal(self, self.cl, newcl)
        self.assertEqual(newcl.etag, new_etag)

if __name__ == '__main__':
    unittest.main()
