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
import functools
import re

from lxml import etree

from pypowervm import const
from pypowervm import util


class XAG(object):
    """Extended Attribute Groups enumeration for an EntryWrapper subclass.

    Intended use: Within an EntryWrapper subclass, define a class variable xags
    of type XAG, initialized with the names of the extended attribute groups
    supported by the corresponding PowerVM REST object.  The keys may be any
    value convenient for use in the consuming code.

    Extended attribute groups 'All' and 'None' are supplied for you.
    """
    @functools.total_ordering
    class _Handler(object):
        def __init__(self, name):
            self.name = name

        def __str__(self):
            return self.name

        def __eq__(self, other):
            return self.name == other.name

        def __lt__(self, other):
            return self.name < other.name

        def __hash__(self):
            return hash(self.name)

        @property
        def attrs(self):
            schema = copy.copy(const.DEFAULT_SCHEMA_ATTR)
            schema['group'] = self.name
            return schema

    def __init__(self, **kwargs):
        self.NONE = self._Handler('None')
        self.ALL = self._Handler('All')
        for key, val in kwargs.items():
            setattr(self, key, self._Handler(val))


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
            self.element.append(c.element)
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
        one_children = one.getchildren()
        two_children = two.getchildren()
        if len(one_children) != len(two_children):
            return False

        # If there are no children, different set of tests
        if len(one_children) == 0:
            if one.text != two.text:
                return False

            if one.tag != two.tag:
                return False
        else:
            # Recursively validate
            for one_child in one_children:
                found = util.find_equivalent(one_child, two_children)
                if found is None:
                    return False

                # Found a match, remove it as it is no longer a valid match.
                # Its equivalence was validated by the upper block.
                two_children.remove(found)

        return True

    def getchildren(self):
        """Returns the children as a list of Elements."""
        return [Element.wrapelement(i, self.adapter)
                for i in self.element.getchildren()]

    @classmethod
    def wrapelement(cls, element, adapter):
        if element is None:
            return None
        # create with minimum inputs
        e = cls('element', adapter)
        # assign element over the one __init__ creates
        e.element = element
        return e

    def toxmlstring(self):
        return etree.tostring(self.element)

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
        """Adds subelement to the end of this element's list of subelements."""
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
