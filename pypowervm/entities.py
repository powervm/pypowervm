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

"""High-level pythonic abstractions of XML entities returned by PowerVM."""

import collections
import copy
import re

from lxml import etree

from pypowervm import const
from pypowervm import util


class Atom(object):
    def __init__(self, properties):
        self.properties = properties

    @property
    def uuid(self):
        try:
            return self.properties['id']
        except KeyError:
            return None

    @property
    def links(self):
        """Get the rel-keyed dict of <link/>s for this Atom, or {} if none."""
        return self.properties.get('links', {})

    @property
    def self_link(self):
        """Get the *first* SELF link, or None if none exists."""
        return self.links.get('SELF', [None])[0]

    @classmethod
    def _process_props(cls, el, props):
        pat = '{%s}' % const.ATOM_NS
        if re.match(pat, el.tag):
            # strip off atom namespace qualification for easier access
            param_name = el.tag[el.tag.index('}') + 1:]
        else:
            # leave qualified anything that is not in the atom
            # namespace
            param_name = el.tag
        if param_name == 'link':
            # properties['links'][REL] = [href, ...]
            # Note that rel may (legally) be None
            rel = el.get('rel')
            if rel:
                rel = rel.upper()
            href = el.get('href')
            if 'links' not in props:
                props['links'] = collections.defaultdict(list)
            props['links'][rel].append(href)
        elif param_name == 'category':
            props[param_name] = el.get('term')
        elif param_name == '{%s}etag' % const.UOM_NS:
            props['etag'] = el.text
        elif el.text:
            props[param_name] = el.text


class Feed(Atom):
    """Represents an Atom Feed returned from PowerVM."""
    def __init__(self, properties, entries):
        super(Feed, self).__init__(properties)
        self.entries = entries

    def findentries(self, subelem, text):
        entries = []
        for entry in self.entries:
            subs = entry.element.findall(subelem)
            for s in subs:
                if s.text == text:
                    entries.append(entry)
                    break
        return entries

    @classmethod
    def unmarshal_atom_feed(cls, feedelem, resp):
        """Factory method producing a Feed object from a parsed ElementTree

        :param feedelem: Parsed ElementTree object representing an atom feed.
        :param resp: The Response from which this Feed was parsed.
        :return: a new Feed object representing the feedelem parameter.
        """
        ret = cls({}, [])
        for child in list(feedelem):
            if child.tag == str(etree.QName(const.ATOM_NS, 'entry')):
                # NB: The use of ret.self_link here relies on <entry>s being
                # AFTER the self link in the <feed>.  (They are in fact last.)
                ret.entries.append(Entry.unmarshal_atom_entry(child, resp))
            elif not list(child):
                cls._process_props(child, ret.properties)
        return ret


class Entry(Atom):
    """Represents an Atom Entry returned by the PowerVM API."""
    def __init__(self, properties, element, adapter):
        """Create an Entry from an etree.Element representing a PowerVM object.

        :param properties: Dict of <entry>-level properties as produced by
                           unmarshal_atom_entry.
        :param element: etree.Element (not entities.Element) - the root of the
                        PowerVM object (not the <feed>, <entry>, or <content>).
        :param adapter: pypowervm.adapter.Adapter through which the element was
                        fetched, and/or through which it should be updated.
        """
        super(Entry, self).__init__(properties)
        self.element = Element.wrapelement(element, adapter)

    def __deepcopy__(self, memo=None):
        """Produce a deep (except for adapter) copy of this Entry."""
        return self.__class__(copy.deepcopy(self.properties, memo=memo),
                              copy.deepcopy(self.element, memo=memo).element,
                              self.adapter)

    @property
    def etag(self):
        return self.properties.get('etag', None)

    @property
    def adapter(self):
        return self.element.adapter

    @classmethod
    def unmarshal_atom_entry(cls, entryelem, resp):
        """Factory method producing an Entry object from a parsed ElementTree

        :param entryelem: Parsed ElementTree object representing an atom entry.
        :param resp: The Response containing (the feed containing) the entry.
        :return: a new Entry object representing the entryelem parameter.
        """
        entryprops = {}
        element = None
        for child in list(entryelem):
            if child.tag == str(etree.QName(const.ATOM_NS, 'content')):
                # PowerVM API only has one element per entry
                element = child[0]
            elif not list(child):
                cls._process_props(child, entryprops)
        return cls(entryprops, element, resp.adapter)


class Element(object):
    """Represents an XML element - a utility wrapper around etree.Element."""
    def __init__(self, tag, adapter, ns=const.UOM_NS, attrib=None, text='',
                 children=(), cdata=False):
        # Defaults shouldn't be mutable
        attrib = attrib if attrib else {}
        self.element = None
        if ns:
            self.element = etree.Element(str(etree.QName(ns, tag)),
                                         attrib=attrib)
        else:
            self.element = etree.Element(tag, attrib=attrib)
        if text:
            self.element.text = etree.CDATA(text) if cdata else text
        for c in children:
            # Use a deep copy, else, c.element gets *removed* from its parent
            # hierarchy (see fourth bullet: http://lxml.de/compatibility.html).
            # Doing the deepcopy here means the caller doesn't have to worry
            # about it.
            self.element.append(copy.deepcopy(c.element))
        self.adapter = adapter

    def __len__(self):
        return len(self.element)

    def __getitem__(self, index):
        return Element.wrapelement(self.element[index], self.adapter)

    def __setitem__(self, index, value):
        if not isinstance(value, Element):
            raise ValueError('Value must be of type Element')
        self.element[index] = value.element

    def __delitem__(self, index):
        del self.element[index]

    def __eq__(self, other):
        if other is None:
            return False
        return self._element_equality(self, other)

    def __deepcopy__(self, memo=None):
        """Produce a deep (except for adapter) copy of this Element."""
        return self.wrapelement(etree.fromstring(self.toxmlstring()),
                                self.adapter)

    @staticmethod
    def _element_equality(one, two):
        """Tests element equality.

        There is no common mechanism for defining 'equality' in the element
        tree.  This provides a good enough equality that meets the schema
        definition.

        :param one: The first element.  Is the backing element.
        :param two: The second element.  Is the backing element.
        :returns: True if the children, text, attributes and tag are equal.
        """

        # Make sure that the children length is equal
        one_children = list(one)
        two_children = list(two)
        if len(one_children) != len(two_children):
            return False

        if one.text != two.text:
            return False

        if one.tag != two.tag:
            return False

        # Recursively validate
        for one_child in one_children:
            found = util.find_equivalent(one_child, two_children)
            if found is None:
                return False

            # Found a match, remove it as it is no longer a valid match.
            # Its equivalence was validated by the upper block.
            two_children.remove(found)

        return True

    def __iter__(self):
        """Returns the children as a list of Elements."""
        return iter([Element.wrapelement(i, self.adapter)
                     for i in list(self.element)])

    @classmethod
    def wrapelement(cls, element, adapter):
        if element is None:
            return None
        # create with minimum inputs
        e = cls('element', adapter)
        # assign element over the one __init__ creates
        e.element = element
        return e

    def toxmlstring(self, pretty=False):
        """Produce an XML dump of this Element.

        :param pretty: If True, format the XML in a visually-pleasing manner.
        :return: An XML string representing this Element.
        """
        # To be sure of backward compatibility, don't pass pretty_print=False.
        kwargs = {'pretty_print': True} if pretty else {}
        return etree.tostring(self.element, **kwargs)

    @property
    def tag(self):
        return etree.QName(self.element.tag).localname

    @tag.setter
    def tag(self, tag):
        ns = self.namespace
        if ns:
            self.element.tag = etree.QName(ns, tag).text
        else:
            self.element.tag = tag

    @property
    def namespace(self):
        ns = etree.QName(self.element.tag).namespace
        return '' if ns is None else ns

    @namespace.setter
    def namespace(self, ns):
        self.element.tag = etree.QName(ns, self.tag).text

    @property
    def text(self):
        return self.element.text

    @text.setter
    def text(self, text):
        self.element.text = text

    @property
    def attrib(self):
        return self.element.attrib

    @attrib.setter
    def attrib(self, attrib):
        self.element.attrib = attrib

    def get(self, key, default=None):
        """Gets the element attribute named key.

        Returns the attribute value, or default if the attribute was not found.
        """
        return self.element.get(key, default)

    def items(self):
        """Returns the element attributes as a sequence of (name, value) pairs.

        The attributes are returned in an arbitrary order.
        """
        return self.element.items()

    def keys(self):
        """Returns the element attribute names as a list.

        The names are returned in an arbitrary order.
        """
        return self.element.keys()

    def set(self, key, value):
        """Set the attribute key on the element to value."""
        self.element.set(key, value)

    def append(self, subelement):
        """Adds subelement to the end of this element's list of subelements.

        Note: if subelement is a reference to an element within another XML
        hierarchy, it will be *removed* from that hierarchy.  If you intend to
        reuse the parent object, you should pass a copy.deepcopy of the
        subelement to this method.
        """
        # TODO(IBM): We *should* deepcopy to prevent child poaching (see fourth
        # bullet here: http://lxml.de/compatibility.html) - but this breaks the
        # world.  Figure out why, and fix it.
        # self.element.append(copy.deepcopy(subelement.element))
        self.element.append(subelement.element)

    def inject(self, subelement, ordering_list=(), replace=True):
        """Inserts subelement at the correct position in self's children.

        Uses ordering_list to determine the proper spot at which to insert the
        specified subelement.

        :param subelement: The element to inject as a child of this element.
        :param ordering_list: Iterable of string tag names representing the
                              desired ordering of children for this element.
                              If subelement's tag is not included in this list,
                              the behavior is self.append(subelement).
        :param replace: If True, and an existing child with subelement's tag is
                        found, it is replaced.  If False, subelement is added
                        after the existing child(ren).  Note: You probably want
                        to use True only/always when subelement is maxOccurs=1.
                        Conversely, you probably want to use False only/always
                        when subelement is unbounded.  If you use True and more
                        than one matching child is found, the last one is
                        replaced.
        """
        def lname(tag):
            """Localname of a tag (without namespace)."""
            return etree.QName(tag).localname

        children = list(self.element)
        # If no children, just append
        if not children:
            self.append(subelement)
            return

        # Any children with the subelement's tag?
        subfound = self.findall(subelement.tag)
        if subfound:
            if replace:
                self.replace(subfound[-1], subelement)
            else:
                subfound[-1].element.addnext(subelement.element)
            return

        # Now try to figure out insertion point based on ordering_list.
        # Ignore namespaces.
        ordlist = [lname(field) for field in ordering_list]
        subtag = lname(subelement.element.tag)
        # If subelement's tag is not in the ordering list, append
        if subtag not in ordlist:
            self.append(subelement)
            return

        # Get the tags preceding that of subelement
        pres = ordlist[:ordlist.index(subtag)]
        # Find the first child whose tag is not in that list
        for child in children:
            if lname(child.tag) not in pres:
                # Found the insertion point
                child.addprevious(subelement.element)
                return
        # If we got here, all existing children need to precede subelement.
        self.append(subelement)

    def find(self, match):
        """Finds the first subelement matching match.

        :param match: May be a tag name or path.
        :return: an element instance or None.
        """
        qpath = Element._qualifypath(match, self.namespace)
        e = self.element.find(qpath)
        if e is not None:
            # must specify "is not None" here to work
            return Element.wrapelement(e, self.adapter)
        else:
            return None

    def findall(self, match):
        """Finds all matching subelements.

        :param match: May be a tag name or path.
        :return: a list containing all matching elements in document order.
        """
        qpath = Element._qualifypath(match, self.namespace)
        e_iter = self.element.findall(qpath)
        elems = []
        for e in e_iter:
            elems.append(Element.wrapelement(e, self.adapter))
        return elems

    def findtext(self, match, default=None):
        """Finds text for the first subelement matching match.

        :param match: May be a tag name or path.
        :return: the text content of the first matching element, or default
                 if no element was found. Note that if the matching element
                 has no text content an empty string is returned.
        """
        qpath = Element._qualifypath(match, self.namespace)
        text = self.element.findtext(qpath, default)
        return text if text else default

    def insert(self, index, subelement):
        """Inserts subelement at the given position in this element.

        :raises TypeError: if subelement is not an etree.Element.
        """
        self.element.insert(index, subelement.element)

    def iter(self, tag=None):
        """Creates a tree iterator with the current element as the root.

        The iterator iterates over this element and all elements below it, in
        document (depth first) order. If tag is not None or '*', only elements
        whose tag equals tag are returned from the iterator. If the tree
        structure is modified during iteration, the result is undefined.
        """
        # Determine which iterator to use
        # etree.Element.getiterator has been deprecated in favor of
        # etree.Element.iter, but the latter was not added until python 2.7
        if hasattr(self.element, 'iter'):
            lib_iter = self.element.iter
        else:
            lib_iter = self.element.getiterator

        # Fix up the tag value
        if not tag or tag == '*':
            qtag = None
        else:
            qtag = str(etree.QName(self.namespace, tag))

        it = lib_iter(tag=qtag)

        for e in it:
            yield Element.wrapelement(e, self.adapter)

    def replace(self, existing, new_element):
        """Replaces the existing child Element with the new one."""
        self.element.replace(existing.element,
                             new_element.element)

    def remove(self, subelement):
        """Removes subelement from the element.

        Unlike the find* methods this method compares elements based on the
        instance identity, not on tag value or contents.
        """
        self.element.remove(subelement.element)

    @staticmethod
    def _qualifypath(path, ns):
        if not ns:
            return path
        parts = path.split('/')
        for i in range(len(parts)):
            if parts[i] and not re.match(r'[\.\*\[\{]', parts[i]):
                parts[i] = str(etree.QName(ns, parts[i]))
        return '/'.join(parts)


class ElementList(object):
    """Useful list ops on a list of Element.

    In a schema where a simpleType element has a multiplicity allowing more
    than one instance within the containing element, this class provides a way
    to treat those instances as a list, to a limited extent.

    For example, given XML like:
        <parent>
            ...(stuff that isn't <foo/>)...
            <foo>one</foo>
            <foo>two</foo>
            <foo>three</foo>
            ...(stuff that isn't <foo/>)...
        </parent>

        fooList = ElementList(parent_element, 'foo')
        len(fooList)
            3
        repr(fooList)
            "['one', 'two', 'three']"
        'two' in fooList
            True
        'four' in fooList
            False
        fooList.append('four')
        repr(fooList)
            "['one', 'two', 'three', 'four']"
        print root.toxmlstring()
            <parent>
                ...(stuff that isn't <foo/>)...
                <foo>one</foo>
                <foo>two</foo>
                <foo>three</foo>
                <foo>four</foo>
                ...(stuff that isn't <foo/>)...
            </parent>
    """

    def __init__(self, root_elem, tag, ordering_list=()):
        """Initialize a new ElementList.

        Note: The current implementation is limited to simple string elements.
              When inserting new values, they will have the default namespace
              and attrs.

        :param root_elem: The entities.Element representing the parent node
                          containing the elements of interest.
        :param tag: The XML tag of the elements of interest.
        :param ordering_list: Iterable of tag strings indicating the desired
                              overall ordering of the elements within the
                              root_elem.  Used to create the first value in
                              the appropriate spot if the ElementList is
                              initially empty.
        """
        self.root_elem = root_elem
        self.tag = tag
        self.order = ordering_list

    def __find_elems(self):
        """List of entities.Element under self.root_elem with tag self.tag."""
        return self.root_elem.findall(self.tag)

    def __get_values(self):
        """List of the string values within the entities.Element instances."""
        return [elem.text for elem in self.__find_elems()]

    def __create_elem(self, val):
        """Create a new entities.Element suitable for this list.

        :param val: The raw string value for the text content of the new
                    element. E.g. self.__create_elem('foo') will yield an
                    entities.Element representing <tag ...>foo</tag> (where tag
                    is whatever this ElementList was initialized with).
        :return: A new entities.Element containing the specified string val.
        """
        return Element(self.tag, self.root_elem.adapter, text=val)

    def index(self, val):
        return self.__get_values().index(val)

    def __len__(self):
        return len(self.__find_elems())

    def extend(self, val_list):
        for val in val_list:
            self.append(val)

    def __repr__(self):
        return repr(self.__get_values())

    def __contains__(self, val):
        return val in self.__get_values()

    def __str__(self):
        return str(self.__get_values())

    def append(self, val):
        self.root_elem.inject(
            self.__create_elem(val), ordering_list=self.order, replace=False)

    def __getitem__(self, idx):
        return self.__get_values()[idx]

    def __setitem__(self, idx, value):
        self.__find_elems()[idx].text = value

    def __delitem__(self, idx):
        self.root_elem.remove(self.__find_elems()[idx])

    def remove(self, val):
        self.__delitem__(self.__get_values().index(val))

    def __iter__(self):
        return iter(self.__get_values())

    def clear(self):
        for val in self.__get_values():
            self.remove(val)
