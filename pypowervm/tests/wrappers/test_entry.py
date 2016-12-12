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
import re
import unittest
import uuid

from lxml import etree
import mock
import six
import testtools

import pypowervm.adapter as apt
import pypowervm.entities as ent
import pypowervm.tests.test_fixtures as fx
from pypowervm.tests.test_utils import pvmhttp
from pypowervm.tests.test_utils import test_wrapper_abc as twrap
import pypowervm.utils.uuid as pvm_uuid
import pypowervm.wrappers.cluster as clust
import pypowervm.wrappers.entry_wrapper as ewrap
import pypowervm.wrappers.iocard as card
import pypowervm.wrappers.logical_partition as lpar
import pypowervm.wrappers.managed_system as ms
import pypowervm.wrappers.network as net
import pypowervm.wrappers.storage as stor
import pypowervm.wrappers.vios_file as vf
import pypowervm.wrappers.virtual_io_server as vios

NET_BRIDGE_FILE = 'fake_network_bridge.txt'
LPAR_FILE = 'lpar.txt'
VIOS_FILE = 'fake_vios_feed.txt'
VNETS_FILE = 'nbbr_virtual_network.txt'
SYS_VNIC_FILE = 'vnic_feed.txt'
SYS_SRIOV_FILE = 'sys_with_sriov.txt'


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


class TestElement(twrap.TestWrapper):
    file = NET_BRIDGE_FILE
    wrapper_class_to_test = net.NetBridge

    def test_child_poaching(self):
        """Creating an element with children of another existing element.

        Ensure the existing element remains intact.
        """
        # How many load groups did we start with?
        num_lg = len(self.dwrap.load_grps)
        # Create a new element with a load group from the NetBridge as a child.
        newel = ent.Element('foo', None,
                            children=[self.dwrap.load_grps[0].element])
        # Element creation did not poach the load group from the NetBridge.
        self.assertEqual(num_lg, len(self.dwrap.load_grps))

        # pypowervm.entities.Element.append (not to be confused with
        # etree.Element.append or list.append) should behave the same way.
        newel.append(self.dwrap.load_grps[1].element)
        # TODO(IBM): ...but it doesn't.  See comment in that method.
        # self.assertEqual(num_lg, len(self.dwrap.load_grps))

    @mock.patch('lxml.etree.tostring')
    def test_toxmlstring(self, mock_tostring):
        newel = ent.Element('foo', None)
        # No args
        self.assertEqual(mock_tostring.return_value, newel.toxmlstring())
        mock_tostring.assert_called_once_with(newel.element)
        # With kwargs
        mock_tostring.reset_mock()
        self.assertEqual(mock_tostring.return_value, newel.toxmlstring(
            pretty=False))
        mock_tostring.assert_called_once_with(newel.element)
        mock_tostring.reset_mock()
        self.assertEqual(mock_tostring.return_value,
                         newel.toxmlstring(pretty=True))
        mock_tostring.assert_called_once_with(newel.element, pretty_print=True)


class TestElementList(twrap.TestWrapper):
    file = SYS_SRIOV_FILE
    wrapper_class_to_test = ms.System

    def setUp(self):
        super(TestElementList, self).setUp()
        self.pport = self.dwrap.asio_config.sriov_adapters[0].phys_ports[0]
        self.tag = 'ConfiguredOptions'

    def _validate_xml(self, val_list):
        outer_tag = self.pport.schema_type
        tag_before = 'ConfiguredMTU'
        tag_after = 'ConfiguredPortSwitchMode'
        # Opening
        tag_pat_fmt = r'<%s(\s[^>]*)?>'
        elem_pat_fmt = tag_pat_fmt + r'%s</%s>\s*'
        pattern = '.*'
        pattern += tag_pat_fmt % outer_tag
        pattern += '.*'
        pattern += elem_pat_fmt % (tag_before, '[^<]*', tag_before)
        for val in val_list:
            pattern += elem_pat_fmt % (self.tag, val, self.tag)
        pattern += elem_pat_fmt % (tag_after, '[^<]*', tag_after)
        pattern += '.*'
        pattern += tag_pat_fmt % ('/' + outer_tag)
        pattern += '.*'
        self.assertTrue(re.match(pattern.encode('utf-8'),
                                 self.pport.toxmlstring(), flags=re.DOTALL))

    def test_everything(self):
        """Ensure ElementList behaves like a list where implemented."""
        # Wrapper._get_elem_list, ElementList.__init__
        coel = self.pport._get_elem_list(self.tag)
        # index
        self.assertEqual(0, coel.index('autoDuplex'))
        self.assertEqual(1, coel.index('Veb'))
        self.assertRaises(ValueError, coel.index, 'foo')
        # __len__
        self.assertEqual(2, len(coel))
        # __repr__
        self.assertEqual("['autoDuplex', 'Veb']", repr(coel))
        # __contains__
        self.assertIn('autoDuplex', coel)
        self.assertIn('Veb', coel)
        self.assertNotIn('foo', coel)
        # __str__
        self.assertEqual("['autoDuplex', 'Veb']", str(coel))
        # __getitem__
        self.assertEqual('autoDuplex', coel[0])
        self.assertEqual('Veb', coel[1])
        self.assertRaises(IndexError, coel.__getitem__, 2)
        # __setitem__
        coel[0] = 'fullDuplex'
        self.assertEqual('fullDuplex', coel[0])
        self.assertRaises(IndexError, coel.__setitem__, 2, 'foo')
        # append
        coel.append('foo')
        self._validate_xml(['fullDuplex', 'Veb', 'foo'])
        # extend
        coel.extend(['bar', 'baz'])
        self._validate_xml(['fullDuplex', 'Veb', 'foo', 'bar', 'baz'])
        # __delitem__
        del coel[3]
        self._validate_xml(['fullDuplex', 'Veb', 'foo', 'baz'])
        # remove
        coel.remove('foo')
        self._validate_xml(['fullDuplex', 'Veb', 'baz'])
        # __iter__
        self.assertEqual(['fullDuplex', 'Veb', 'baz'], [val for val in coel])
        # clear
        coel.clear()
        self.assertEqual(0, len(coel))
        self._validate_xml([])
        # Inserting stuff back in puts it in the right place
        coel.extend(['one', 'two', 'three'])
        self._validate_xml(['one', 'two', 'three'])
        # Wrapper._set_elem_list
        self.pport._set_elem_list(self.tag, ['four', 'five', 'six'])
        self._validate_xml(['four', 'five', 'six'])


class TestWrapper(unittest.TestCase):
    def test_get_val_str(self):
        w = SubWrapper(one='1', foo='foo', empty='')
        self.assertEqual(w._get_val_str('one'), '1')
        self.assertEqual(w._get_val_str('foo'), 'foo')
        self.assertEqual(w._get_val_str('empty'), '')
        self.assertIsNone(w._get_val_str('nonexistent'))
        self.assertEqual(w._get_val_str('nonexistent', default='10'), '10')

    def test_get_val_percent(self):
        w = SubWrapper(one='2.45%', two='2.45', three=None, four='123',
                       five='1.2345', six='123.0', seven='123%',
                       eight='%123', nine='12%3')
        self.assertEqual(w._get_val_percent('one'), 0.0245)
        self.assertEqual(w._get_val_percent('two'), 0.0245)
        self.assertEqual(w._get_val_percent('three'), None)
        self.assertEqual(w._get_val_percent('four'), 1.23)
        self.assertEqual(w._get_val_percent('five'), 0.012345)
        self.assertEqual(w._get_val_percent('six'), 1.23)
        self.assertEqual(w._get_val_percent('seven'), 1.23)
        self.assertEqual(w._get_val_percent('eight'), 1.23)
        # Interesting test:
        self.assertEqual(w._get_val_percent('nine'), 0.12)
        self.assertIsNone(w._get_val_percent('nonexistent'))

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


class TestEntryWrapper(testtools.TestCase):

    def setUp(self):
        super(TestEntryWrapper, self).setUp()
        self.adpt = self.useFixture(fx.AdapterFx()).adpt

    def test_etag(self):
        fake_entry = ent.Entry({}, ent.Element('fake_entry', self.adpt),
                               self.adpt)
        etag = '1234'
        ew = ewrap.EntryWrapper.wrap(fake_entry, etag=etag)
        self.assertEqual(etag, ew.etag)

        ew = ewrap.EntryWrapper.wrap(fake_entry)
        self.assertEqual(None, ew.etag)

    def test_set_uuid(self):

        # Test that an AttributeError is raised
        def set_wrap_uuid(wrap, value):
            wrap.uuid = value
        self.assertRaises(AttributeError, set_wrap_uuid,
                          ewrap.EntryWrapper(None), 'fake-uuid-value')

        # Test that we call the mixin set_uuid method for valid cases.
        class ValidEntryWrap(ewrap.EntryWrapper, ewrap.WrapperSetUUIDMixin):
            pass
        with mock.patch('pypowervm.wrappers.entry_wrapper.WrapperSetUUIDMixin'
                        '.set_uuid') as mock_setup:
            uuid1 = pvm_uuid.convert_uuid_to_pvm(str(uuid.uuid4()))
            ValidEntryWrap(None).uuid = uuid1
            mock_setup.assert_called_with(uuid1)

    def test_load(self):
        etag = '1234'
        resp = apt.Response('reqmethod', 'reqpath', 'status', 'reason',
                            dict(etag=etag))

        # Entry or Feed is not set, so expect an exception
        self.assertRaises(KeyError, ewrap.EntryWrapper.wrap, resp)

        # Set an entry...
        entry = ent.Entry({}, ent.Element('entry', self.adpt), self.adpt)
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
        e1 = ent.Entry({'etag': '1'}, ent.Element('e1', self.adpt),
                       self.adpt)
        e2 = ent.Entry({'etag': '2'}, ent.Element('e2', self.adpt),
                       self.adpt)
        resp.feed = ent.Feed({}, [e1, e2])

        # Run
        ew = ewrap.EntryWrapper.wrap(resp)

        # Validate
        self.assertEqual(e1, ew[0].entry)
        self.assertEqual('1', ew[0].etag)
        self.assertEqual(e2, ew[1].entry)
        self.assertEqual('2', ew[1].etag)

    @mock.patch('lxml.etree.tostring')
    def test_toxmlstring(self, mock_tostring):
        wrp = ewrap.EntryWrapper.wrap(ent.Entry(
            {}, ent.Element('fake_entry', None), None))
        # No args
        self.assertEqual(mock_tostring.return_value, wrp.toxmlstring())
        mock_tostring.assert_called_once_with(wrp.entry.element)
        # With kwargs
        mock_tostring.reset_mock()
        self.assertEqual(mock_tostring.return_value, wrp.toxmlstring(
            pretty=False))
        mock_tostring.assert_called_once_with(wrp.entry.element)
        mock_tostring.reset_mock()
        self.assertEqual(mock_tostring.return_value, wrp.toxmlstring(
            pretty=True))
        mock_tostring.assert_called_once_with(
            wrp.entry.element, pretty_print=True)


class TestElementWrapper(testtools.TestCase):
    """Tests for the ElementWrapper class."""

    def setUp(self):
        super(TestElementWrapper, self).setUp()
        self.adpt = self.useFixture(fx.AdapterFx()).adpt
        self.resp = pvmhttp.load_pvm_resp(NET_BRIDGE_FILE).get_response()
        self.nb1 = ewrap.EntryWrapper.wrap(self.resp.feed.entries[0])
        self.resp2 = pvmhttp.load_pvm_resp(NET_BRIDGE_FILE).get_response()
        self.nb2 = ewrap.EntryWrapper.wrap(self.resp2.feed.entries[0])

    def test_equality(self):
        """Validates that two elements loaded from the same data is equal."""
        sea1 = self._find_seas(self.nb1.entry)[0]
        sea2 = self._find_seas(self.nb2.entry)[0]
        sea2copy = copy.deepcopy(sea2)
        self.assertTrue(sea1 == sea2)
        self.assertEqual(sea2, sea2copy)

        # Change the other SEA
        sea2.element.element.append(etree.Element('Bob'))
        self.assertFalse(sea1 == sea2)

    def test_inequality_by_subelem_change(self):
        sea1 = self._find_seas(self.nb1.entry)[0]
        sea2 = self._find_seas(self.nb2.entry)[0]
        sea_trunk = sea2.element.findall('TrunkAdapters/TrunkAdapter')[0]
        pvid = sea_trunk.find('PortVLANID')
        pvid.text = '1'
        self.assertFalse(sea1 == sea2)

    def test_unequal(self):
        sea1 = self._find_seas(self.nb1.entry)[0]
        sea2 = self._find_seas(self.nb2.entry)[0]
        self.assertEqual(sea1, sea2)
        # Different text makes 'em different
        sea1.element.text = 'Bogus'
        self.assertNotEqual(sea1, sea2)
        # reset
        sea1.element.text = sea2.element.element.text
        # Different tag makes 'em different
        sea1.element.tag = 'Bogus'
        self.assertNotEqual(sea1, sea2)

    def _find_seas(self, entry):
        """Wrapper for the SEAs."""
        found = entry.element.find('SharedEthernetAdapters')
        return ewrap.WrapperElemList(found, net.SEA)

    def test_fresh_element(self):
        # Default: UOM namespace, no <Metadata/>
        class MyElement(ewrap.ElementWrapper):
            schema_type = 'SomePowerObject'
        myel = MyElement._bld(self.adpt)
        self.assertEqual(myel.schema_type, 'SomePowerObject')
        self.assertEqual(myel.element.toxmlstring(),
                         '<SomePowerObject/>'.encode("utf-8"))

        # Can override namespace and attrs and trigger inclusion of <Metadata/>
        class MyElement3(ewrap.ElementWrapper):
            schema_type = 'SomePowerObject'
            default_attrib = {'foo': 'bar'}
            schema_ns = 'baz'
            has_metadata = True
        myel = MyElement3._bld(self.adpt)
        self.assertEqual(
            myel.element.toxmlstring(),
            '<ns0:SomePowerObject xmlns:ns0="baz" foo="bar"><ns0:Metadata>'
            '<ns0:Atom/></ns0:Metadata></ns0:SomePowerObject>'.encode("utf-8"))

        # Same thing, but via the decorator
        @ewrap.ElementWrapper.pvm_type('SomePowerObject', has_metadata=True,
                                       ns='baz', attrib={'foo': 'bar'})
        class MyElement4(ewrap.ElementWrapper):
            pass
        myel = MyElement4._bld(self.adpt)
        self.assertEqual(
            myel.element.toxmlstring(),
            '<ns0:SomePowerObject xmlns:ns0="baz" foo="bar"><ns0:Metadata>'
            '<ns0:Atom/></ns0:Metadata></ns0:SomePowerObject>'.encode("utf-8"))

        # Now 'SomePowerObject' is registered.  Prove that we can use wrap() to
        # instantiate MyElement4 straight from ElementWrapper.
        el = ent.Element('SomePowerObject', self.adpt, ns='baz',
                         attrib={'foo': 'bar'})
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
            'f5-ab60-40893d51d074/VirtualNetwork/2b4ab8ea-4b15-3430-b2cd-45954'
            'cfaba0d')
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

    def _verify_element_clone(self, el1, el2):
        # Equal according to _element_equality
        self.assertEqual(el1, el2)
        # Not the same reference
        self.assertIsNot(el1, el2)
        # Adapter references are the same
        self.assertIs(el1.adapter, el2.adapter)
        # etree.Elements are not the same reference
        self.assertIsNot(el1.element, el2.element)
        # But they marshal identically
        self.assertEqual(el1.toxmlstring().strip(),
                         el2.toxmlstring().strip())

    def test_element_clone(self):
        el1 = self.nb1.element
        el2 = copy.deepcopy(el1)
        self._verify_element_clone(el1, el2)

    def _verify_properties_clone(self, props1, props2):
        # Properties should be deeply equal
        self.assertEqual(props1, props2)
        # But not the same reference
        self.assertIsNot(props1, props2)
        # Strings are shared copy-on-write.  Ensure changing one does not
        # change the other
        props1['id'] = 'abc'
        self.assertNotEqual(props1['id'], props2['id'])

    def _verify_entry_clone(self, ent1, ent2):
        # Elements should be cloned to the same spec as Element.__deepcopy__()
        self._verify_element_clone(ent1.element, ent2.element)
        self._verify_properties_clone(ent1.properties, ent2.properties)
        # Ensure deep copy - sub-properties also not the same reference.
        links1 = ent1.properties['links']
        links2 = ent2.properties['links']
        self.assertIsNot(links1, links2)
        # And one more layer down
        self.assertIsNot(links1['SELF'], links2['SELF'])

    def test_entry_clone(self):
        ent1 = self.nb1.entry
        ent2 = copy.deepcopy(ent1)
        self._verify_entry_clone(ent1, ent2)

    def _verify_feed_clone(self, feed1, feed2):
        self._verify_properties_clone(feed1.properties, feed2.properties)
        self.assertEqual(len(feed1.entries), len(feed2.entries))
        for ent1, ent2 in zip(feed1.entries, feed2.entries):
            self._verify_entry_clone(ent1, ent2)

    def test_feed_clone(self):
        feed1 = self.resp.feed
        feed2 = copy.deepcopy(feed1)
        self._verify_feed_clone(feed1, feed2)

    def _verify_response_clone(self, resp1, resp2):
        for attr in ('reqmethod', 'reqpath', 'reqheaders', 'reqbody', 'status',
                     'reason', 'headers', 'body', 'adapter'):
            self.assertEqual(getattr(resp1, attr), getattr(resp2, attr))
        self.assertIsNot(resp1.headers, resp2.headers)
        self.assertIs(resp1.adapter, resp2.adapter)
        if resp1.feed is None:
            self.assertIsNone(resp2.feed)
        else:
            self._verify_feed_clone(resp1.feed, resp2.feed)
        if resp1.entry is None:
            self.assertIsNone(resp2.entry)
        else:
            self._verify_entry_clone(resp1.entry, resp2.entry)

    def test_response_clone(self):
        # Network Bridge Response has a feed
        resp1 = self.resp
        resp2 = copy.deepcopy(resp1)
        self._verify_response_clone(resp1, resp2)
        # This one has entry
        resp3 = pvmhttp.load_pvm_resp(
            'get_volume_group_no_rep.txt').get_response()
        resp4 = copy.deepcopy(resp3)
        self._verify_response_clone(resp3, resp4)

    def test_entrywrapper_clone(self):
        ew1 = self.nb1
        ew2 = copy.deepcopy(ew1)
        # Entrys should be cloned to the same spec as Entry.__deepcopy__()
        self._verify_entry_clone(ew1.entry, ew2.entry)
        # Etags should match
        self.assertEqual(ew1.etag, ew2.etag)
        # But changing one should not change the other
        ew1._etag = 'abc'
        self.assertNotEqual(ew1.etag, ew2.etag)

    def test_elementwrapper_clone(self):
        ew1 = self.nb1.seas[0]
        ew2 = copy.deepcopy(ew1)
        # Elements should be cloned to the same spec as Element.__deepcopy__()
        self._verify_element_clone(ew1.element, ew2.element)


class TestWrapperElemList(testtools.TestCase):
    """Tests for the WrapperElemList class."""

    def setUp(self):
        super(TestWrapperElemList, self).setUp()
        self.adpt = self.useFixture(fx.AdapterFx()).adpt
        # No indirect
        self.seas_wel = net.NetBridge.wrap(pvmhttp.load_pvm_resp(
            NET_BRIDGE_FILE).get_response())[0].seas
        # With indirect
        self.backdev_wel = card.VNIC.wrap(pvmhttp.load_pvm_resp(
            SYS_VNIC_FILE).get_response())[0].back_devs

    def test_get(self):
        self.assertIsInstance(self.seas_wel[0], net.SEA)
        self.assertRaises(IndexError, lambda a, i: a[i], self.seas_wel, 2)
        # Works with indirect
        self.assertIsInstance(self.backdev_wel[0], card.VNICBackDev)
        self.assertRaises(IndexError, lambda a, i: a[i], self.backdev_wel, 2)

    def test_length(self):
        self.assertEqual(2, len(self.seas_wel))
        self.assertEqual(2, len(self.backdev_wel))

    def test_append(self):
        sea_add = ewrap.ElementWrapper.wrap(
            ent.Element('SharedEthernetAdapter', self.adpt))
        self.assertEqual(2, len(self.seas_wel))

        # Test Append
        self.seas_wel.append(sea_add)
        self.assertEqual(3, len(self.seas_wel))
        # Appending to indirect
        backdev = copy.deepcopy(self.backdev_wel[0])
        self.backdev_wel.append(backdev)
        self.assertEqual(3, len(self.backdev_wel))

        # Make sure we can also remove what was just added.
        self.seas_wel.remove(sea_add)
        self.assertEqual(2, len(self.seas_wel))
        # Removing from indirect
        self.backdev_wel.remove(backdev)
        self.assertEqual(2, len(self.backdev_wel))

    def test_extend(self):
        seas = [
            ewrap.ElementWrapper.wrap(ent.Element('SharedEthernetAdapter',
                                                  self.adpt)),
            ewrap.ElementWrapper.wrap(ent.Element('SharedEthernetAdapter',
                                                  self.adpt))
        ]
        self.assertEqual(2, len(self.seas_wel))
        self.seas_wel.extend(seas)
        self.assertEqual(4, len(self.seas_wel))
        self.adpt.build_href.return_value = 'href'
        # Extending indirect
        backdevs = [card.VNICBackDev.bld(self.adpt, 'vios_uuid', 1, 2),
                    card.VNICBackDev.bld(self.adpt, 'vios_uuid', 3, 4)]
        self.backdev_wel.extend(backdevs)
        self.assertEqual(4, len(self.backdev_wel))

        # Make sure that we can also remove what we added.  We remove a
        # logically identical element to test the equivalence function
        e = ewrap.ElementWrapper.wrap(ent.Element('SharedEthernetAdapter',
                                                  self.adpt))
        self.seas_wel.remove(e)
        self.seas_wel.remove(e)
        self.assertEqual(2, len(self.seas_wel))
        # With indirect
        self.backdev_wel.remove(card.VNICBackDev.bld(self.adpt, 'vios_uuid', 1,
                                                     2))
        self.assertEqual(3, len(self.backdev_wel))
        # Non-equivalent one doesn't work
        self.assertRaises(ValueError, self.backdev_wel.remove,
                          card.VNICBackDev.bld(self.adpt, 'vios_uuid', 1, 3))

    def test_in(self):
        # This really does fail without __contains__
        self.assertIn(self.seas_wel[0], self.seas_wel)
        # Works with indirect
        self.assertIn(self.backdev_wel[0], self.backdev_wel)

    def test_index(self):
        self.assertEqual(self.seas_wel.index(self.seas_wel[0]), 0)
        # Works with indirect
        self.assertEqual(self.backdev_wel.index(self.backdev_wel[0]), 0)

    def test_str(self):
        strout = str(self.seas_wel)
        self.assertEqual('[', strout[0])
        self.assertEqual(']', strout[-1])
        for chunk in strout.split(','):
            self.assertIn('SEA', chunk)
        # And for indirect
        strout = str(self.backdev_wel)
        self.assertEqual('[', strout[0])
        self.assertEqual(']', strout[-1])
        for chunk in strout.split(','):
            self.assertIn('VNIC', chunk)

    def test_repr(self):
        strout = repr(self.seas_wel)
        self.assertEqual('[', strout[0])
        self.assertEqual(']', strout[-1])
        for chunk in strout.split(','):
            self.assertIn('SEA', chunk)
        # And for indirect
        strout = repr(self.backdev_wel)
        self.assertEqual('[', strout[0])
        self.assertEqual(']', strout[-1])
        for chunk in strout.split(','):
            self.assertIn('VNIC', chunk)


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


class TestGet(testtools.TestCase):
    """Tests for EntryWrapper.get()."""

    def setUp(self):
        super(TestGet, self).setUp()
        self.adpt = self.useFixture(fx.AdapterFx()).adpt

    @mock.patch('pypowervm.wrappers.logical_partition.LPAR.wrap')
    def test_get_root(self, mock_wrap):
        """Various permutations of EntryWrapper.get on a ROOT object."""
        # Happy path - feed.  Ensure misc args are passed through.
        lpar.LPAR.get(self.adpt, foo='bar', baz=123)
        self.adpt.read.assert_called_with(lpar.LPAR.schema_type, foo='bar',
                                          baz=123)
        mock_wrap.assert_called_with(self.adpt.read.return_value)
        mock_wrap.reset_mock()
        # Happy path - entry with 'uuid'
        lpar.LPAR.get(self.adpt, uuid='123')
        self.adpt.read.assert_called_with(lpar.LPAR.schema_type, root_id='123')
        mock_wrap.assert_called_with(self.adpt.read.return_value)
        mock_wrap.reset_mock()
        # Happy path - entry with 'root_id'
        lpar.LPAR.get(self.adpt, root_id='123')
        self.adpt.read.assert_called_with(lpar.LPAR.schema_type, root_id='123')
        mock_wrap.assert_called_with(self.adpt.read.return_value)
        mock_wrap.reset_mock()

    @mock.patch('pypowervm.wrappers.network.CNA.wrap')
    def test_get_child(self, mock_wrap):
        """Various permutations of EntryWrapper.get on a CHILD object."""
        # Happy path - feed.  Parent specified as class
        net.CNA.get(self.adpt, parent_type=lpar.LPAR, parent_uuid='123')
        self.adpt.read.assert_called_with(lpar.LPAR.schema_type, root_id='123',
                                          child_type=net.CNA.schema_type)
        mock_wrap.assert_called_with(self.adpt.read.return_value)
        mock_wrap.reset_mock()
        # Happy path - entry with 'uuid'.  Parent specified as string.
        net.CNA.get(
            self.adpt, parent_type=lpar.LPAR.schema_type, parent_uuid='123',
            uuid='456')
        self.adpt.read.assert_called_with(
            lpar.LPAR.schema_type, root_id='123',
            child_type=net.CNA.schema_type, child_id='456')
        mock_wrap.assert_called_with(self.adpt.read.return_value)
        mock_wrap.reset_mock()
        # Happy path - entry with 'child_id'.  Parent specified as instance.
        parent = mock.Mock(spec=lpar.LPAR, schema_type=lpar.LPAR.schema_type,
                           uuid='123')
        net.CNA.get(self.adpt, parent=parent, child_id='456')
        self.adpt.read.assert_called_with(
            lpar.LPAR.schema_type, root_id='123',
            child_type=net.CNA.schema_type, child_id='456')
        mock_wrap.assert_called_with(self.adpt.read.return_value)
        mock_wrap.reset_mock()

    @mock.patch('pypowervm.wrappers.entry_wrapper.EntryWrapper.wrap')
    def test_get_errors(self, mock_wrap):
        """Error paths in EntryWrapper.get."""
        # parent_type specified, parent_uuid not.
        self.assertRaises(ValueError,
                          net.CNA.get, self.adpt, parent_type=lpar.LPAR)
        # CHILD mode forbids 'root_id' (must use 'parent_uuid').
        self.assertRaises(ValueError, net.CNA.get, self.adpt,
                          parent_type=lpar.LPAR, parent_uuid='1', root_id='2')
        # CHILD mode can't have both 'uuid' and 'child_id'.
        self.assertRaises(ValueError, net.CNA.get, self.adpt,
                          parent_type=lpar.LPAR, parent_uuid='12', uuid='34',
                          child_id='56')
        # ROOT mode forbids parent_uuid.
        self.assertRaises(ValueError,
                          lpar.LPAR.get, self.adpt, parent_uuid='123')
        # ROOT mode forbids child_type.
        self.assertRaises(ValueError,
                          lpar.LPAR.get, self.adpt, child_type=net.CNA)
        # ROOT mode forbids child_id.
        self.assertRaises(ValueError,
                          lpar.LPAR.get, self.adpt, child_id='123')
        # ROOT mode can't have both 'uuid' and 'root_id'.
        self.assertRaises(ValueError,
                          lpar.LPAR.get, self.adpt, uuid='12', root_id='34')
        # Nothing was ever wrapped
        mock_wrap.assert_not_called()

    @mock.patch('pypowervm.wrappers.entry_wrapper.EntryWrapper.wrap')
    def test_get_by_href(self, mock_wrap):
        self.assertEqual(
            mock_wrap.return_value,
            ewrap.EntryWrapper.get_by_href(self.adpt, 'href', one=2, three=4))
        self.adpt.read_by_href.assert_called_once_with('href', one=2, three=4)


class TestSearch(testtools.TestCase):
    """Tests for EntryWrapper.search()."""

    def setUp(self):
        super(TestSearch, self).setUp()
        self.adp = apt.Adapter(self.useFixture(fx.SessionFx()).sess)

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
        def validate_result(clwrap):
            self.assertIsInstance(clwrap, clust.Cluster)
            self.assertEqual(clwrap.name, 'cl1')
            self.assertEqual(clwrap.repos_pv.name, 'hdisk1')
            self.assertEqual(clwrap.nodes[0].hostname, 'vios1')

        mock_rq.side_effect = self._validate_request(
            "/rest/api/uom/Cluster/search/(ClusterName=='cl1')?group=None",
            clust.Cluster.bld(self.adp, 'cl1', stor.PV.bld(self.adp, 'hdisk1',
                                                           'udid1'),
                              clust.Node.bld(
                                  self.adp, hostname='vios1')).entry)

        clwraps = clust.Cluster.search(self.adp, name='cl1')
        self.assertEqual(len(clwraps), 1)
        validate_result(clwraps[0])
        # Test one_result on a registered key with a single hit
        validate_result(clust.Cluster.search(self.adp, one_result=True,
                                             name='cl1'))

    @mock.patch('pypowervm.adapter.Adapter._request')
    def test_negate(self, mock_rq):
        mock_rq.side_effect = self._validate_request(
            "/rest/api/uom/Cluster/search/(ClusterName!='cl1')?group=None")
        clwraps = clust.Cluster.search(self.adp, negate=True, name='cl1')
        self.assertEqual(clwraps, [])
        # Test one_result with no hits
        self.assertIsNone(clust.Cluster.search(self.adp, negate=True,
                                               one_result=True, name='cl1'))

    def test_no_such_search_key(self):
        """Ensure an invalid search key gives ValueError."""
        self.assertRaises(ValueError, clust.Cluster.search, self.adp,
                          foo='bar')

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
        def validate_read(root_type, xag):
            # This should be called by _search_by_feed, not by search.
            # Otherwise, we'll get an exception on the arg list.
            self.assertEqual(net.NetBridge.schema_type, root_type)
            self.assertIsNone(xag)
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
        # Test one_result down the no-search-key path
        nb = net.NetBridge.search(self.adp, one_result=True, vswitch_id=0)
        self.assertEqual('d648eb60-4d39-34ad-ae2b-928d8c9577ad', nb.uuid)

        # Now do a search that returns more than one item.
        # Use a string for an int field to prove it works anyway.
        rets = net.NetBridge.search(self.adp, pvid='1')
        self.assertEqual(2, len(rets))
        self.assertIsInstance(rets[0], net.NetBridge)
        self.assertIsInstance(rets[1], net.NetBridge)
        self.assertEqual({'d648eb60-4d39-34ad-ae2b-928d8c9577ad',
                          '764f3423-04c5-3b96-95a3-4764065400bd'},
                         {nb.uuid for nb in rets})
        # Ensure one_result returns the first hit
        self.assertEqual(rets[0].uuid, net.NetBridge.search(
            self.adp, one_result=True, pvid=1).uuid)

    @mock.patch('pypowervm.adapter.Adapter.read')
    def test_search_with_xag(self, mock_read):
        """Test a search key that's in search_keys, but specifying xag."""
        def validate_read(root_type, xag):
            # This should be called by _search_by_feed, not by search.
            # Otherwise, we'll get an exception on the arg list.
            self.assertEqual(lpar.LPAR.schema_type, root_type)
            self.assertEqual(['Foo', 'Bar'], xag)
            return pvmhttp.load_pvm_resp(LPAR_FILE).get_response()
        mock_read.side_effect = validate_read
        rets = lpar.LPAR.search(self.adp, name='linux1', xag=['Foo', 'Bar'])
        self.assertEqual(1, len(rets))
        linux1 = rets[0]
        self.assertIsInstance(linux1, lpar.LPAR)
        self.assertEqual('9068B0FB-1CF0-4D23-8A23-31AC87D5F5D2', linux1.uuid)

    @mock.patch('pypowervm.adapter.Adapter.read')
    def test_child_no_search_key(self, mock_read):
        """CHILD search with or without a search key (uses GET-feed-loop)."""
        def validate_read(root_type, root_id, child_type, xag):
            # This should be called by _search_by_feed, not by search.
            # Otherwise, we'll get an exception on the arg list.
            self.assertEqual('SomeParent', root_type)
            self.assertEqual('some_uuid', root_id)
            self.assertEqual('Cluster', child_type)
            self.assertIsNone(xag)
            return pvmhttp.load_pvm_resp(NET_BRIDGE_FILE).get_response()
        mock_read.side_effect = validate_read
        clust.Cluster.search(self.adp, id=0, parent_type='SomeParent',
                             parent_uuid='some_uuid')
        clust.Cluster.search(self.adp, name='mycluster',
                             parent_type='SomeParent', parent_uuid='some_uuid')

    def test_child_bad_args(self):
        """Specifying parent_uuid without parent_type is an error."""
        self.assertRaises(ValueError, net.NetBridge.search, self.adp,
                          vswitch_id=0, parent_uuid='some_uuid')

    @mock.patch('pypowervm.adapter.Adapter.read')
    def test_search_all_parents(self, mock_read):
        """Anonymous ROOT for CHILD search."""
        # We're going to pretend that VSwitch is a CHILD of VirtualIOServer.
        parent_type = 'VirtualIOServer'
        child_schema_type = 'VirtualNetwork'

        # Anonymous CHILD search should call GET(ROOT feed), followed by one
        # GET(CHILD feed) for each ROOT parent.  Choosing a feed file with two
        # entries.  The following mock_reads are chained in order.
        def validate_feed_get(root):
            # Chain to the first entry GET
            mock_read.side_effect = validate_entry_get1
            self.assertEqual(parent_type, root)
            # VIOS_FILE has two <entry>s.
            return pvmhttp.load_pvm_resp(VIOS_FILE).get_response()

        def validate_entry_get1(root, root_id, child_type, **kwargs):
            # Chain to the second entry GET
            mock_read.side_effect = validate_entry_get2
            self.assertEqual(parent_type, root)
            self.assertEqual('1300C76F-9814-4A4D-B1F0-5B69352A7DEA', root_id)
            self.assertEqual(child_schema_type, child_type)
            entry_resp = pvmhttp.load_pvm_resp(VNETS_FILE).get_response()
            # Use the first half of the feed, which contains two tagged vlans
            entry_resp.feed.entries = entry_resp.feed.entries[:4]
            return entry_resp

        def validate_entry_get2(root, root_id, child_type, **kwargs):
            self.assertEqual(parent_type, root)
            self.assertEqual('7DBBE705-E4C4-4458-8223-3EBE07015CA9', root_id)
            self.assertEqual(child_schema_type, child_type)
            entry_resp = pvmhttp.load_pvm_resp(VNETS_FILE).get_response()
            # Use the second half of the feed, which contains two tagged vlans
            entry_resp.feed.entries = entry_resp.feed.entries[4:]
            return entry_resp

        # Set up the first mock_read in the chain
        mock_read.side_effect = validate_feed_get

        # Do the search (with class as parent_type)
        wraps = net.VNet.search(self.adp, parent_type=vios.VIOS, tagged=True)
        # Make sure we got the right networks
        self.assertEqual(4, len(wraps))
        for wrap, expected_vlanid in zip(wraps, (1234, 2, 1001, 1000)):
            self.assertIsInstance(wrap, net.VNet)
            self.assertTrue(wrap.tagged)
            self.assertEqual(expected_vlanid, wrap.vlan)

    @mock.patch('pypowervm.adapter.Adapter.read')
    def test_child_with_parent_spec(self, mock_read):
        """Test CHILD search using a parent instance."""
        def validate_read(root_type, root_id, child_type, xag):
            self.assertEqual('st', root_type)
            self.assertEqual('uuid', root_id)
            self.assertEqual('Cluster', child_type)
            self.assertIsNone(xag)
            return pvmhttp.load_pvm_resp(NET_BRIDGE_FILE).get_response()
        mock_read.side_effect = validate_read
        parent = mock.Mock(spec=clust.Cluster, schema_type='st', uuid='uuid')
        clust.Cluster.search(self.adp, id=0, parent=parent)


class TestRefresh(testtools.TestCase):
    """Tests for Adapter.refresh()."""

    clust_uuid = 'cluster_uuid'
    clust_href = 'https://server:12443/rest/api/uom/Cluster' + clust_uuid

    def setUp(self):
        super(TestRefresh, self).setUp()
        self.adp = apt.Adapter(mock.patch('requests.Session'))
        props = {'id': self.clust_uuid, 'links': {'SELF': [self.clust_href]}}
        self.old_etag = '123'
        self.clust_old = clust.Cluster.bld(
            self.adp, 'mycluster', stor.PV.bld(self.adp, 'hdisk1', 'udid1'),
            clust.Node.bld(self.adp, 'hostname1'))
        self.clust_old._etag = None
        self.clust_old.entry.properties = props
        self.new_etag = '456'
        self.clust_new = clust.Cluster.bld(
            self.adp, 'mycluster', stor.PV.bld(self.adp, 'hdisk2', 'udid2'),
            clust.Node.bld(self.adp, 'hostname2'))
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
        clust_refreshed = self.clust_old.refresh()
        _assert_clusters_equal(self, clust_old_save, clust_refreshed)

    @mock.patch('pypowervm.adapter.Adapter.read_by_href')
    def test_etag_match(self, mock_read):
        mock_read.side_effect = self._mock_read_by_href(
            self.old_etag, self.resp304)
        self.clust_old._etag = self.old_etag
        clust_refreshed = self.clust_old.refresh()
        # On an etag match, refresh should return the same instance
        self.assertEqual(self.clust_old, clust_refreshed)

    @mock.patch('pypowervm.adapter.Adapter.read_by_href')
    def test_etag_no_match(self, mock_read):
        mock_read.side_effect = self._mock_read_by_href(
            self.old_etag, self.resp200new)
        self.clust_old._etag = self.old_etag
        clust_new_save = copy.deepcopy(self.clust_new)
        clust_refreshed = self.clust_old.refresh()
        _assert_clusters_equal(self, clust_new_save, clust_refreshed)

    @mock.patch('pypowervm.adapter.Adapter.read_by_href')
    def test_use_etag_false(self, mock_read):
        mock_read.side_effect = self._mock_read_by_href(
            None, self.resp200new)
        self.clust_old._etag = self.old_etag
        clust_new_save = copy.deepcopy(self.clust_new)
        clust_refreshed = self.clust_old.refresh(use_etag=False)
        _assert_clusters_equal(self, clust_new_save, clust_refreshed)


class TestUpdate(testtools.TestCase):
    clust_uuid = 'cluster_uuid'
    clust_path = '/rest/api/uom/Cluster' + clust_uuid
    clust_href = 'https://server:12443' + clust_path
    clust_etag = '123'

    def setUp(self):
        super(TestUpdate, self).setUp()
        self.adp = apt.Adapter(self.useFixture(fx.SessionFx()).sess)

        props = {'id': self.clust_uuid, 'links': {'SELF': [self.clust_href]}}
        self.cl = clust.Cluster.bld(
            self.adp, 'mycluster', stor.PV.bld(
                self.adp, 'hdisk1', udid='udid1'),
            clust.Node.bld(self.adp, 'hostname1'))
        self.cl._etag = self.clust_etag
        self.cl.entry.properties = props

    @mock.patch('pypowervm.adapter.Adapter.update_by_path')
    def test_update(self, mock_ubp):
        new_etag = '456'
        resp = apt.Response('meth', 'path', 200, 'reason', {'etag': new_etag})
        resp.entry = self.cl.entry
        mock_ubp.return_value = resp
        newcl = self.cl.update()
        mock_ubp.assert_called_with(
            self.cl, self.clust_etag, self.clust_path, timeout=3600)
        _assert_clusters_equal(self, self.cl, newcl)
        self.assertEqual(newcl.etag, new_etag)

    @mock.patch('pypowervm.adapter.Adapter.update_by_path')
    @mock.patch('warnings.warn')
    def test_update_xag(self, mock_warn, mock_ubp):
        new_etag = '456'
        resp = apt.Response('meth', 'path', 200, 'reason', {'etag': new_etag})
        resp.entry = self.cl.entry
        mock_ubp.return_value = resp
        newcl = self.cl.update(xag=['one', 'two', 'three'], timeout=123)
        mock_ubp.assert_called_with(
            self.cl, self.clust_etag, self.clust_path, timeout=123)
        _assert_clusters_equal(self, self.cl, newcl)
        self.assertEqual(newcl.etag, new_etag)
        mock_warn.assert_called_with(mock.ANY, DeprecationWarning)

    @mock.patch('pypowervm.adapter.Adapter.update_by_path')
    @mock.patch('warnings.warn')
    def test_update_with_get_xag(self, mock_warn, mock_ubp):
        # Update the entry with the new properties
        get_href = self.clust_href + "?group=one,three,two"
        props = {'id': self.clust_uuid, 'links': {'SELF': [get_href]}}
        self.cl.entry.properties = props

        new_etag = '456'
        resp = apt.Response('meth', 'path', 200, 'reason', {'etag': new_etag})
        resp.entry = self.cl.entry
        mock_ubp.return_value = resp
        newcl = self.cl.update(xag=['should', 'be', 'ignored'], timeout=-1)
        mock_ubp.assert_called_with(
            self.cl, self.clust_etag, self.clust_path + '?group=one,three,two',
            timeout=3600)
        _assert_clusters_equal(self, self.cl, newcl)
        self.assertEqual(newcl.etag, new_etag)
        mock_warn.assert_called_with(mock.ANY, DeprecationWarning)


class TestDelete(testtools.TestCase):
    def setUp(self):
        super(TestDelete, self).setUp()
        self.adpt = self.useFixture(fx.AdapterFx()).adpt

    def test_delete(self):
        vswitch = net.VSwitch.bld(self.adpt, 'a_switch')
        vswitch.entry = mock.MagicMock()
        vswitch.entry.href = 'test'
        vswitch.entry.etag = 5

        def validate_delete(uri, etag):
            self.assertEqual('test', uri)
            self.assertEqual(5, etag)
            return

        self.adpt.delete_by_href.side_effect = validate_delete
        vswitch.delete()


class TestCreate(testtools.TestCase):
    def setUp(self):
        super(TestCreate, self).setUp()
        self.adpt = self.useFixture(fx.AdapterFx()).adpt

    def test_create_root(self):
        vswitch = net.VSwitch.bld(self.adpt, 'a_switch')

        def validate_create(element, root_type, service, timeout=-1):
            self.assertIsInstance(element, net.VSwitch)
            self.assertEqual(net.VSwitch.schema_type, root_type)
            self.assertEqual('uom', service)
            self.assertEqual(123, timeout)
            return vswitch.entry
        self.adpt.create.side_effect = validate_create
        vswitch.create(timeout=123)

    def test_create_child(self):
        # We can safely pretend VSwitch is a child for purposes of this test.
        vswitch = net.VSwitch.bld(self.adpt, 'a_switch')

        def validate_create(element, root_type, root_id, child_type, service,
                            timeout=456):
            self.assertIsInstance(element, net.VSwitch)
            self.assertEqual(net.VSwitch.schema_type, child_type)
            self.assertEqual('NetworkBridge', root_type)
            self.assertEqual('SomeUUID', root_id)
            self.assertEqual('uom', service)
            self.assertEqual(-1, timeout)
            return vswitch.entry
        self.adpt.create.side_effect = validate_create
        # Make sure it works when parent_type is a class...
        vswitch.create(parent_type=net.NetBridge, parent_uuid='SomeUUID')
        # ...or a string
        vswitch.create(parent_type='NetworkBridge', parent_uuid='SomeUUID')
        # Or an instance
        parent = mock.Mock(spec=net.NetBridge, schema_type='NetworkBridge',
                           uuid='SomeUUID')
        vswitch.create(parent=parent)

    def test_create_other_service(self):
        """Ensure non-UOM service goes through."""
        vfile = vf.File.bld(self.adpt, "filename", "filetype", "vios_uuid")

        def validate_create(element, root_type, service, timeout=345):
            self.assertIsInstance(element, vf.File)
            self.assertEqual(vf.File.schema_type, root_type)
            self.assertEqual('web', service)
            self.assertEqual(-1, timeout)
            return vfile.entry
        self.adpt.create.side_effect = validate_create
        vfile.create(timeout=-1)

    def test_create_raises(self):
        """Verify invalid inputs raise exceptions."""
        vswitch = net.VSwitch.bld(self.adpt, 'a_switch')
        self.assertRaises(ValueError, vswitch.create, parent_type='Foo')
        self.assertRaises(ValueError, vswitch.create, parent_uuid='Foo')


class TestSetUUIDMixin(testtools.TestCase):
    """Generic tests for WrapperSetUUIDMixin."""
    def test_set_uuid(self):
        """Test mixins of Element (with/without Metadata) and Entry."""
        old_uuid = pvm_uuid.convert_uuid_to_pvm(str(uuid.uuid4()))
        new_uuid = pvm_uuid.convert_uuid_to_pvm(str(uuid.uuid4()))

        def set_wrap_uuid(wrap, value):
            wrap.uuid = value

        def assert_uuid(wrap, uuid, has_entry=True):
            if has_entry:
                self.assertEqual(uuid, wrap.uuid)
                # Same as above
                if uuid is None:
                    self.assertTrue('id' not in wrap.entry.properties or
                                    wrap.entry.properties['id'] is None)
                else:
                    self.assertEqual(uuid, wrap.entry.properties['id'])
            else:
                self.assertFalse(hasattr(wrap, 'entry'))
            self.assertEqual(uuid, wrap.uuid)

        @ewrap.EntryWrapper.pvm_type('SomeEntry')
        class SomeEntry(ewrap.EntryWrapper, ewrap.WrapperSetUUIDMixin):
            """EntryWrapper with set-uuid mixin."""
            pass

        # Set bad uuid value
        bad_uuid = 'F' + new_uuid[1:]
        self.assertRaises(ValueError, set_wrap_uuid,
                          SomeEntry(None), bad_uuid)

        # Entry has both Metadata and properties['id']
        some_ent = SomeEntry._bld(None)
        # Starts off empty
        assert_uuid(some_ent, None)
        # Can set from empty
        some_ent.set_uuid(old_uuid)
        assert_uuid(some_ent, old_uuid)
        # Can change from already-set
        some_ent.set_uuid(new_uuid)
        assert_uuid(some_ent, new_uuid)

        @ewrap.ElementWrapper.pvm_type('SomeObject', has_metadata=True)
        class SomeElementWithMetadata(ewrap.ElementWrapper,
                                      ewrap.WrapperSetUUIDMixin):
            """ElementWrapper with set-uuid mixin - WITH Metadata."""
            pass

        # Element has it in one place.  Also testing vivification of AtomID.
        sewm = SomeElementWithMetadata._bld(None)
        # Starts with no AtomID
        self.assertEqual(
            '<uom:SomeObject xmlns:uom="http://www.ibm.com/xmlns/systems/power'
            '/firmware/uom/mc/2012_10/" schemaVersion="V1_0"><uom:Metadata>'
            '<uom:Atom/></uom:Metadata></uom:SomeObject>'.encode('utf-8'),
            sewm.toxmlstring())
        assert_uuid(sewm, None, has_entry=False)
        # Can set
        sewm.set_uuid(old_uuid)
        assert_uuid(sewm, old_uuid, has_entry=False)
        # Can change
        sewm.set_uuid(new_uuid)
        assert_uuid(sewm, new_uuid, has_entry=False)

        @ewrap.ElementWrapper.pvm_type('SomeOtherObject')
        class SomeElementWithoutMetadata(ewrap.ElementWrapper,
                                         ewrap.WrapperSetUUIDMixin):
            """ElementWrapper with set-uuid mixin - WITHOUT Metadata."""
            pass

        sewom = SomeElementWithoutMetadata._bld(None)
        # No Metadata
        self.assertEqual(
            '<uom:SomeOtherObject xmlns:uom="http://www.ibm.com/xmlns/systems'
            '/power/firmware/uom/mc/2012_10/" schemaVersion="V1_0"/>'.
            encode('utf-8'),
            sewom.toxmlstring())
        assert_uuid(sewom, None, has_entry=False)
        # Exception attempting to set on an element with no metadata
        self.assertRaises(AttributeError, sewom.set_uuid, new_uuid)


class TestGetters(twrap.TestWrapper):
    file = LPAR_FILE
    wrapper_class_to_test = lpar.LPAR

    @mock.patch('pypowervm.wrappers.entry_wrapper.EntryWrapper.refresh')
    def test_entry_wrapper_getter(self, mock_refresh):
        self.adpt.read.return_value = self.dwrap.entry
        mock_refresh.return_value = self.dwrap
        # ROOT
        getter = ewrap.EntryWrapperGetter(self.adpt, lpar.LPAR, 'lpar_uuid')
        self.assertEqual('lpar_uuid', getter.uuid)
        lwrap = getter.get()
        self.assertIsInstance(lwrap, lpar.LPAR)
        self.assertEqual(self.dwrap.entry, lwrap.entry)
        self.adpt.read.assert_called_with(
            'LogicalPartition', 'lpar_uuid', child_id=None, child_type=None,
            xag=None)
        self.assertEqual(1, self.adpt.read.call_count)
        self.assertEqual(0, mock_refresh.call_count)
        # Second get doesn't re-read
        lwrap = getter.get()
        self.assertIsInstance(lwrap, lpar.LPAR)
        self.assertEqual(self.dwrap.entry, lwrap.entry)
        self.assertEqual(1, self.adpt.read.call_count)
        self.assertEqual(0, mock_refresh.call_count)
        # get with refresh doesn't read, but does refresh
        lwrap = getter.get(refresh=True)
        self.assertIsInstance(lwrap, lpar.LPAR)
        self.assertEqual(self.dwrap.entry, lwrap.entry)
        self.assertEqual(1, self.adpt.read.call_count)
        self.assertEqual(1, mock_refresh.call_count)

        # CHILD, use the EntryWrapper.getter classmethod, use xags
        getter = lpar.LPAR.getter(
            self.adpt, 'lpar_uuid', parent_class=stor.VDisk,
            parent_uuid='parent_uuid', xag=['one', 'two'])
        self.assertIsInstance(getter, ewrap.EntryWrapperGetter)
        self.assertEqual('lpar_uuid', getter.uuid)
        lwrap = getter.get()
        self.assertIsInstance(lwrap, lpar.LPAR)
        self.adpt.read.assert_called_with(
            'VirtualDisk', 'parent_uuid', child_type='LogicalPartition',
            child_id='lpar_uuid', xag=['one', 'two'])

        # With string parent_class
        getter = lpar.LPAR.getter(
            self.adpt, 'lpar_uuid', parent_class='VirtualDisk',
            parent_uuid='parent_uuid', xag=['one', 'two'])
        self.assertIsInstance(getter, ewrap.EntryWrapperGetter)
        self.assertEqual('lpar_uuid', getter.uuid)
        lwrap = getter.get()
        self.assertIsInstance(lwrap, lpar.LPAR)
        self.adpt.read.assert_called_with(
            'VirtualDisk', 'parent_uuid', child_type='LogicalPartition',
            child_id='lpar_uuid', xag=['one', 'two'])

        # With parent instance
        parent = mock.Mock(spec=stor.VDisk, schema_type='st', uuid='uuid')
        getter = lpar.LPAR.getter(self.adpt, 'lpar_uuid', parent=parent)
        self.assertIsInstance(getter, ewrap.EntryWrapperGetter)
        self.assertEqual('lpar_uuid', getter.uuid)
        lwrap = getter.get()
        self.assertIsInstance(lwrap, lpar.LPAR)
        self.adpt.read.assert_called_with(
            'st', 'uuid', child_type='LogicalPartition', child_id='lpar_uuid',
            xag=None)

        # parent type & uuid must both be specified
        self.assertRaises(ValueError, ewrap.EntryWrapperGetter, self.adpt,
                          lpar.LPAR, 'lpar_uuid', parent_class=stor.VDisk)
        self.assertRaises(ValueError, ewrap.EntryWrapperGetter, self.adpt,
                          lpar.LPAR, 'lpar_uuid', parent_uuid='parent_uuid')
        # entry_class must be a Wrapper subtype
        self.assertRaises(ValueError, ewrap.EntryWrapperGetter, self.adpt, 's',
                          'lpar_uuid')
        self.assertRaises(ValueError, ewrap.EntryWrapperGetter, self.adpt,
                          None, 'lpar_uuid')
        self.assertRaises(ValueError, ewrap.EntryWrapperGetter, self.adpt,
                          ewrap.EntryWrapperGetter, 'lpar_uuid')
        self.assertRaises(ValueError, ewrap.EntryWrapperGetter, self.adpt,
                          lpar.LPAR, 'lpar_uuid', parent_class=None,
                          parent_uuid='parent_uuid')
        self.assertRaises(ValueError, ewrap.EntryWrapperGetter, self.adpt,
                          lpar.LPAR, 'lpar_uuid',
                          parent_class=ewrap.EntryWrapperGetter,
                          parent_uuid='parent_uuid')

    @mock.patch('pypowervm.wrappers.entry_wrapper.EntryWrapper.refresh')
    def test_feed_getter(self, mock_refresh):
        self.adpt.read.return_value = self.resp
        feediter = iter(self.entries)
        mock_refresh.side_effect = lambda: next(feediter)
        # ROOT
        getter = ewrap.FeedGetter(self.adpt, lpar.LPAR)
        lfeed = getter.get()
        self.assertEqual(21, len(lfeed))
        self.assertEqual('089FFB20-5D19-4A8C-BB80-13650627D985', lfeed[0].uuid)
        self.adpt.read.assert_called_with(
            'LogicalPartition', None, child_id=None, child_type=None, xag=None)
        self.assertEqual(1, self.adpt.read.call_count)
        self.assertEqual(0, mock_refresh.call_count)
        # Second get doesn't re-read
        lfeed = getter.get()
        self.assertEqual(21, len(lfeed))
        self.assertEqual('089FFB20-5D19-4A8C-BB80-13650627D985', lfeed[0].uuid)
        self.assertEqual(1, self.adpt.read.call_count)
        self.assertEqual(0, mock_refresh.call_count)
        # get with refresh refreshes all 21 wrappers (but doesn't call read)
        lfeed = getter.get(refresh=True)
        self.assertEqual(21, len(lfeed))
        self.assertEqual('089FFB20-5D19-4A8C-BB80-13650627D985', lfeed[0].uuid)
        self.assertEqual(1, self.adpt.read.call_count)
        self.assertEqual(21, mock_refresh.call_count)
        # get with refetch calls read, not refresh
        lfeed = getter.get(refetch=True)
        self.assertEqual(21, len(lfeed))
        self.assertEqual('089FFB20-5D19-4A8C-BB80-13650627D985', lfeed[0].uuid)
        self.assertEqual(2, self.adpt.read.call_count)
        self.adpt.read.assert_called_with(
            'LogicalPartition', None, child_id=None, child_type=None, xag=None)
        self.assertEqual(21, mock_refresh.call_count)

        # CHILD, use the EntryWrapper.getter classmethod, use xags
        getter = lpar.LPAR.getter(self.adpt, parent_class=stor.VDisk,
                                  parent_uuid='p_uuid', xag=['one', 'two'])
        self.assertIsInstance(getter, ewrap.FeedGetter)
        lfeed = getter.get()
        self.assertEqual(21, len(lfeed))
        self.assertEqual('089FFB20-5D19-4A8C-BB80-13650627D985', lfeed[0].uuid)
        self.adpt.read.assert_called_with(
            'VirtualDisk', 'p_uuid', child_type='LogicalPartition',
            child_id=None, xag=['one', 'two'])

        # CHILD, parent_class as string schema type
        getter = lpar.LPAR.getter(self.adpt, parent_class='VirtualDisk',
                                  parent_uuid='p_uuid', xag=['one', 'two'])
        self.assertIsInstance(getter, ewrap.FeedGetter)
        lfeed = getter.get()
        self.assertEqual(21, len(lfeed))
        self.assertEqual('089FFB20-5D19-4A8C-BB80-13650627D985', lfeed[0].uuid)
        self.adpt.read.assert_called_with(
            'VirtualDisk', 'p_uuid', child_type='LogicalPartition',
            child_id=None, xag=['one', 'two'])

        # CHILD, parent instance
        parent = mock.Mock(spec=stor.VDisk, schema_type='st', uuid='uuid')
        getter = lpar.LPAR.getter(self.adpt, parent=parent)
        self.assertIsInstance(getter, ewrap.FeedGetter)
        lfeed = getter.get()
        self.assertEqual(21, len(lfeed))
        self.assertEqual('089FFB20-5D19-4A8C-BB80-13650627D985', lfeed[0].uuid)
        self.adpt.read.assert_called_with(
            'st', 'uuid', child_type='LogicalPartition', child_id=None,
            xag=None)

        # entry_class must be a Wrapper subtype
        self.assertRaises(ValueError, ewrap.FeedGetter, self.adpt, 's')
        self.assertRaises(ValueError, ewrap.FeedGetter, self.adpt, None)
        self.assertRaises(ValueError, ewrap.FeedGetter, self.adpt,
                          ewrap.EntryWrapperGetter)
        self.assertRaises(ValueError, ewrap.FeedGetter, self.adpt, lpar.LPAR,
                          parent_class=None, parent_uuid='parent_uuid')
        self.assertRaises(ValueError, ewrap.FeedGetter, self.adpt, lpar.LPAR,
                          parent_class=ewrap.EntryWrapperGetter,
                          parent_uuid='parent_uuid')

    @mock.patch('pypowervm.wrappers.entry_wrapper.EntryWrapper.refresh')
    def test_uuid_feed_getter(self, mock_refresh):
        """Verify UUIDFeedGetter."""
        # Mock return separate entries per read.  Need multiple copies for
        # multiple calls.
        read_iter = iter(wrp.entry for wrp in (
            self.entries[:3] + self.entries[:3] + self.entries[:3] +
            self.entries[:3]))
        self.adpt.read.side_effect = lambda *a, **k: next(read_iter)
        # Separate iterator for refreshes
        refresh_iter = iter(self.entries[:3])
        mock_refresh.side_effect = lambda: next(refresh_iter)
        # ROOT
        uuids = ['u1', 'u2', 'u3']
        getter = ewrap.UUIDFeedGetter(self.adpt, lpar.LPAR, uuids)
        # In order to be useful for a FeedTask, this has to evaluate as an
        # instance of FeedGetter
        self.assertIsInstance(getter, ewrap.FeedGetter)
        lfeed = getter.get()
        self.assertEqual(3, len(lfeed))
        self.assertEqual('089FFB20-5D19-4A8C-BB80-13650627D985', lfeed[0].uuid)
        # This does three separate reads
        self.adpt.read.assert_has_calls([mock.call(
            lpar.LPAR.schema_type, uuid, child_type=None, child_id=None,
            xag=None) for uuid in uuids])
        self.assertEqual(0, mock_refresh.call_count)
        # Second get doesn't re-read
        lfeed = getter.get()
        self.assertEqual(3, len(lfeed))
        self.assertEqual('089FFB20-5D19-4A8C-BB80-13650627D985', lfeed[0].uuid)
        self.assertEqual(3, self.adpt.read.call_count)
        self.assertEqual(0, mock_refresh.call_count)
        # get with refresh refreshes all thre wrappers (but doesn't call read)
        lfeed = getter.get(refresh=True)
        self.assertEqual(3, len(lfeed))
        self.assertEqual('089FFB20-5D19-4A8C-BB80-13650627D985', lfeed[0].uuid)
        self.assertEqual(3, self.adpt.read.call_count)
        self.assertEqual(3, mock_refresh.call_count)
        # get with refetch calls read, not refresh
        lfeed = getter.get(refetch=True)
        self.assertEqual(3, len(lfeed))
        self.assertEqual('089FFB20-5D19-4A8C-BB80-13650627D985', lfeed[0].uuid)
        self.assertEqual(6, self.adpt.read.call_count)
        self.assertEqual(3, mock_refresh.call_count)

        # CHILD
        getter = ewrap.UUIDFeedGetter(
            self.adpt, lpar.LPAR, uuids, parent_class=stor.VDisk,
            parent_uuid='p_uuid', xag=['one', 'two'])
        self.assertIsInstance(getter, ewrap.FeedGetter)
        lfeed = getter.get()
        self.assertEqual(3, len(lfeed))
        self.assertEqual('089FFB20-5D19-4A8C-BB80-13650627D985', lfeed[0].uuid)
        self.adpt.read.assert_has_calls([mock.call(
            stor.VDisk.schema_type, 'p_uuid', child_type=lpar.LPAR.schema_type,
            child_id=uuid, xag=['one', 'two']) for uuid in uuids])

        # With parent instance
        parent = mock.Mock(spec=stor.VDisk, schema_type='st', uuid='uuid')
        getter = ewrap.UUIDFeedGetter(
            self.adpt, lpar.LPAR, uuids, parent=parent)
        self.assertIsInstance(getter, ewrap.FeedGetter)
        lfeed = getter.get()
        self.assertEqual(3, len(lfeed))
        self.assertEqual('089FFB20-5D19-4A8C-BB80-13650627D985', lfeed[0].uuid)
        self.adpt.read.assert_has_calls(
            [mock.call('st', 'uuid', child_type=lpar.LPAR.schema_type,
                       child_id=uuid, xag=None) for uuid in uuids])


if __name__ == '__main__':
    unittest.main()
