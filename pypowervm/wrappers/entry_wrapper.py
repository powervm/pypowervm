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

import abc
import logging

from pypowervm import adapter as adpt
import pypowervm.const as pc
from pypowervm.i18n import _
from pypowervm import util
import pypowervm.wrappers.constants as wc

import six

LOG = logging.getLogger(__name__)

_UUID = 'id'


@six.add_metaclass(abc.ABCMeta)
class Wrapper(object):
    """Base wrapper object that subclasses should extend.

    Provides base support for operations.  Will define a few methods that need
    to be overridden by subclasses.
    """

    # See pvm_type decorator
    schema_type = None
    default_attrib = None
    schema_ns = None
    has_metadata = False

    # Registers PowerVM object wrappers by their schema type.
    # { schema_type_string: wrapper_class, ... }
    # E.g. { 'SharedEthernetAdapter': pypowervm.wrappers.network.SEA, ... }
    _pvm_object_registry = {}

    @classmethod
    def pvm_type(cls, schema_type, has_metadata=None, ns=pc.UOM_NS,
                 attrib=wc.DEFAULT_SCHEMA_ATTR, child_order=None):
        """Decorator for {Entry|Element}Wrappers of PowerVM objects.

        Sets foundational fields used for construction of new wrapper instances
        and pieces thereof.

        Registers the decorated class, keyed by its schema_type,  This enables
        the wrap method to return the correct subclass even if invoked directly
        from ElementWrapper or EntryWrapper.

        :param schema_type: PowerVM REST API Schema type of the subclass (str).
        :param has_metadata: Indicates whether, when creating and wrapping a
                             fresh adapter.Element, it should have a
                             <Metadata/> child element.
        :param ns: PowerVM REST API Schema namespace of the subclass.
        :param attrib: Default attributes for fresh Element when factory
                       constructor is used.
        :param child_order: Ordered list of the element names of the first-
                            level children of this element/entry.  Used for
                            order-agnostic construction/setting of values.
        """
        def inner(class_):
            class_.schema_type = schema_type
            if has_metadata is not None:
                class_.has_metadata = has_metadata
            if ns is not None:
                class_.schema_ns = ns
            if attrib is not None:
                class_.default_attrib = attrib
            if child_order:
                co = list(child_order)
                if class_.has_metadata and co[0] != 'Metadata':
                    co.insert(0, 'Metadata')
                class_._child_order = tuple(co)
            Wrapper._pvm_object_registry[schema_type] = class_
            return class_
        return inner

    @property
    def child_order(self):
        return getattr(self, '_child_order', ())

    def inject(self, subelement, replace=True):
        """Injects subelement as a child element, possibly replacing it.

        This is pypowervm.adapter.Element.inject, with ordering_list always set
        to self.child_order.
        """
        self.element.inject(subelement, self.child_order, replace=replace)

    def _find(self, property_name, use_find_all=False):
        """Will find a given element within the object.

        :param property_name: The property to search within the tree for.
        :param use_find_all: If set to true, will use the find_all method for
                             queries.
        """
        element = self.element
        if use_find_all:
            found_value = element.findall(property_name)
        else:
            found_value = element.find(property_name)

        return found_value  # May be None

    def _find_or_seed(self, prop_name, attrib=wc.DEFAULT_SCHEMA_ATTR):
        """Will find the existing element, or create if needed.

        If the element is not found, it will be added to the child list
        of this element.
        :param prop_name: The property name to replace with the new value.
        :param attrib: The attributes to use for the property.  Defaults to
                       the DEFAULT_SCHEM_ATTR.
        :returns: The existing element, or a newly created one if not found.
        """
        root_elem = self.element

        # Find existing
        existing = root_elem.find(prop_name)
        if existing:
            return existing
        else:
            new_elem = adpt.Element(prop_name, attrib=attrib,
                                    children=[])
            self.inject(new_elem)
            return new_elem

    def replace_list(self, prop_name, prop_children,
                     attrib=wc.DEFAULT_SCHEMA_ATTR):
        """Replaces a property on this Entry that contains a children list.

        The prop_children represent the new elements for the property.

        If the property does not already exist, this will simply append the
        new children.

        :param prop_name: The property name to replace with the new value.
        :param prop_children: A list of ElementWrapper objects that represent
                              the new children for the property list.
        :param attrib: The attributes to use if the property.  Defaults to
                       the DEFAULT_SCHEM_ATTR.
        """
        new_elem = adpt.Element(prop_name,
                                attrib=attrib,
                                children=[x.element for
                                          x in prop_children])

        self.inject(new_elem)

    @property
    @abc.abstractmethod
    def type_and_uuid(self):
        """Return the type and uuid of this entry together in one string.

        This is useful for error messages, logging, etc.
        """
        pass

    def set_parm_value(self, property_name, value, create=True, attrib=None):
        """Set a child element value, possibly creating the child.

        :param property_name: The schema name of the property to set.
        :param value: The (string) value to assign to the property's 'text'.
        :param create: If True, and the property is not found, it will be
        created.  Otherwise this method will throw an exception.
        :param attrib: The element attribute to use if the element is created.
        """
        element_value = self._find(property_name)
        if element_value is None:
            self.log_missing_value(property_name)
            if create:
                element_value = adpt.Element(property_name, ns=self.schema_ns,
                                             attrib=attrib, text=str(value))
                self.inject(element_value)

        element_value.text = str(value)

    def set_float_gb_value(self, property_name, value, create=True):
        """Special case of set_parm_value for floats of Gigabyte.Type.

        o Gigabyte.Type can't handle more than 6dp.
        o Floating point representation issues can mean that e.g. 0.1 + 0.2
        yields 0.30000000000000004.
        o str() rounds to 12dp.

        So this method converts a float (or float string) to a string with
        exactly 6dp before storing it in the property.

        :param property_name: The schema name of the property to set (see
                              set_parm_value).
        :param value: The floating point number or floating point string to be
                      set.
        :param create: If True, and the property is not found, it will be
                       created.  Otherwise this method will throw an exception.
                       (See set_parm_value.)
        """
        self.set_parm_value(property_name,
                            util.sanitize_float_for_api(value, precision=6),
                            create=create)

    def __get_val(self, property_name, default=None, converter=None):
        """Retrieve the value of an element within this wrapper's ElementTree.

        This is the baseline for all the _get_val_{type} methods.
        :param property_name: The name (XPath) of the property to find.
        :param default: The default value to return if the property is not
                        found OR if type conversion fails.
        :param converter: Optional callable accepting a single string parameter
                          and returning a value of some other type.  The
                          converter callable should raise ValueError if
                          conversion fails.
        :return: The (possibly converted) value corresponding to the identified
                 property.
        """
        element_value = self._find(property_name)
        if element_value is None:
            self.log_missing_value(property_name)
            return default

        text = element_value.text
        if text is None:
            return default

        if type(text) is str:
            text = text.strip()

        if callable(converter):
            try:
                return converter(text)
            except ValueError:
                message = (
                    _("Cannot convert %(property_name)s='%(value)s' "
                      "in object %(pvmobject)s") % {
                        "property_name": property_name,
                        "value": text,
                        "pvmobject": self.type_and_uuid})

                LOG.error(message)
                return default
        return text

    def _get_vals(self, property_name):
        """Gets a list of values from PowerVM.

        :param property_name: property to return
        :returns: List of strings containing property values.  No type
                  conversion is done.  If no elements are found, the empty list
                  is returned (as opposed to None).
        """
        values = []
        elements = self._find(property_name, use_find_all=True)
        if elements is not None:
            for element in elements:
                values.append(element.text)
        return values

    def _get_val_bool(self, property_name, default=False):
        """Gets the boolean value of a PowerVM property.

        :param property_name: property to return
        :param default: The value to return if the property is not found
            in the data
        :return: If the property exists in the data and has the value
            'true' or 'false' (case-insensitive), then the corresponding
            boolean value will be returned.
            If the property does not exist, then the default value will be
            returned if specified, otherwise False will be returned.
        """
        def str2bool(bool_str):
            return str(bool_str).lower() == 'true'
        return self.__get_val(property_name, default=default,
                              converter=str2bool)

    def _get_val_int(self, property_name, default=None):
        """Gets the integer value of a PowerVM property.

        :param property_name: property to find
        :param default: Value to return if property is not found.  Defaults to
                        None (which is not an int - plan accordingly).
        :return: Integer (int) value of the property if it is found and it is a
                 valid integer.
        :raise ValueError: If the value cannot be converted.
        """
        return self.__get_val(property_name, default=default, converter=int)

    def _get_val_float(self, property_name, default=None):
        """Gets the float value of a PowerVM property.

        :param property_name: property to find
        :param default: Value to return if property is not found.  Defaults to
                        None (which is not a float - plan accordingly).
        :return: float value of the property if it is found and it is a
                 valid float.
        :raise ValueError: If the value cannot be converted.
        """
        return self.__get_val(property_name, default=default, converter=float)

    def _get_val_str(self, property_name, default=None):
        """Gets the string value of a PowerVM property.

        :param property_name: property to find
        :param default: Value to return if property is not found.  Defaults to
                        None (which is not a str - plan accordingly).
        :return: str value of the property if it is found.  May be the empty
                 string.
        """
        return self.__get_val(property_name, default=default, converter=None)

    def log_missing_value(self, param):
        error_message = (
            _('The expected parameter of %(param)s was not found in '
              '%(identifier)s') % {
                "param": param,
                "identifier": self.type_and_uuid})
        LOG.debug(error_message)

    def get_href(self, propname, one_result=False):
        """Returns the hrefs from AtomLink elements.

        :param propname: The name of the schema element containing the 'href'
                         attribute.
        :param one_result: If True, we are expecting exactly one result, and
                           will return that one (string) result, or None.  If
                           False (the default), we will return a tuple of
                           strings which may be empty.
        """
        ret_links = []
        elements = self._find(propname, use_find_all=True)

        # Loop through what was found, if anything
        if elements:
            for atomlink in elements:
                # If the element doesn't have an href, ignore it.
                try:
                    ret_links.append(atomlink.attrib['href'])
                except KeyError:
                    pass

        if one_result:
            if len(ret_links) == 1:
                return ret_links[0]
            else:
                return None
        # Otherwise return a (possibly empty) tuple of the results
        return tuple(ret_links)

    def set_href(self, propname, href):
        """Finds or creates the (single) named property and sets its href.

        If the indicated element does not exist, it (and any necessary interim
        parent elements) will be created.  If any intervening path is non-
        unique, any new element paths will be created under the first one.

        :param propname: XPath to the property.
        :param href: The URI value to assign to the href attribute.
                     rel=related is automatically assigned.
        """
        links = self._find(propname, use_find_all=True)
        if len(links) > 1:
            msg = _('Refusing set href over multiple links.\nPath: %{path}s\n'
                    'Number of links found: %{nlinks}d')
            raise ValueError(msg % {'path': propname, 'nlinks': len(links)})
        if len(links) == 1:
            link = links[0]
        else:
            # Not found - create the property
            l = propname.split(wc.DELIM)
            append_point = self
            while len(l) > 1:
                next_prop = l.pop(0)
                new_el = append_point._find(next_prop)
                if new_el is None:
                    new_el = adpt.Element(next_prop)
                    append_point.element.inject(
                        new_el, ordering_list=self.child_order)
                append_point = ElementWrapper.wrap(new_el)
            link = adpt.Element(l[-1])
            append_point.element.inject(link, ordering_list=self.child_order)
        # At this point we have found or created the propname element.  Its
        # handle is in the link var.
        link.attrib['href'] = href
        link.attrib['rel'] = 'related'

    def toxmlstring(self):
        return self.element.toxmlstring()

    @classmethod
    def _bld_element(cls, tag=None, has_metadata=has_metadata, ns=schema_ns,
                     attrib=default_attrib):
        """Create a fresh adapter.Element, usually for immediate wrapping.

        :param tag: Property name of the new Element.
        :param has_metadata: If True, a <Metadata/> child will be created.
        :param ns: Namespace to use.
        :param attrib: XML attributes to use in the outer Element.
        :return: A fresh adapter.Element.
        """
        tag = cls.schema_type if tag is None else tag
        # Make sure the call was either through a legal wrapper or explicitly
        # specified a tag name
        if tag is None:
            raise TypeError(_("Refusing to construct and wrap an Element"
                              "without a tag."))
        has_metadata = (cls.has_metadata
                        if has_metadata is None
                        else has_metadata)
        ns = cls.schema_ns if ns is None else ns
        attrib = cls.default_attrib if attrib is None else attrib
        children = []
        if has_metadata:
            children.append(
                adpt.Element('Metadata', ns=ns, children=[
                    adpt.Element('Atom', ns=ns)]))
        return adpt.Element(tag, ns=ns, attrib=attrib, children=children)

    @classmethod
    def _class_for_element(cls, element):
        """Discover and return an appropriate *Wrapper subclass for element.

        :param element: An adapter.Element to introspect
        :return: A Wrapper subclass (the class, not an instance).  If element
                 represents a known subclass, it is returned; else the invoking
                 class is returned.
        """
        # Extract tag.  Let this raise AttributeError - means the Element is
        # invalid.
        schema_type = element.tag
        # Is it a registered wrapper class?
        try:
            return Wrapper._pvm_object_registry[schema_type]
        except KeyError:
            return cls


class EntryWrapper(Wrapper):
    """Base Wrapper for the Entry object types."""
    # If it's an Entry, it must be a ROOT or CHILD
    has_metadata = True

    def __init__(self, entry, etag=None):
        self.entry = entry
        self._etag = etag

    @classmethod
    def _bld(cls, tag=None, has_metadata=None, ns=None, attrib=None):
        element = cls._bld_element(
            tag, has_metadata=has_metadata, ns=ns, attrib=attrib)
        return cls(adpt.Entry({'title': element.tag}, element.element))

    @classmethod
    def wrap(cls, response_or_entry, etag=None):
        """Creates an entry (or list) from an adapter.Response or Entry.

        If response is specified and is a feed, a list of EntryWrapper will be
        returned.  The entries within the feed are not guaranteed to have etags
        (e.g. from non-uom elements).

        Otherwise, a single EntryWrapper will be returned.  This is NOT a list.

        This method should usually be invoked from an EntryWrapper subclass
        decorated by Wrapper.pvm_type, and an instance of that subclass will be
        returned.

        If invoked directly from EntryWrapper, we attempt to detect whether an
        appropriate subclass exists based on the Entry's Element's tag.  If so,
        that subclass is used; otherwise a generic EntryWrapper is used.

        :param response_or_entry: The Response from an adapter.Adapter.read
                                  request, or an existing adapter.Entry to
                                  wrap.
        :returns: A list of wrappers if response_or_entry is a Response with a
                  Feed.  A single wrapper if response_or_entry is an Entry or a
                  Response with an Entry.
        """
        # Process Response if specified.  This recursively calls this method
        # with the entry(s) within the Response.
        if isinstance(response_or_entry, adpt.Response):
            if response_or_entry.entry is not None:
                return cls.wrap(
                    response_or_entry.entry,
                    etag=response_or_entry.etag)
            elif response_or_entry.feed is not None:
                return [cls.wrap(ent, etag=ent.etag)
                        for ent in response_or_entry.feed.entries]
            else:
                raise KeyError(_("Response is missing 'entry' property."))

        # Else process Entry if specified
        if isinstance(response_or_entry, adpt.Entry):
            # If schema_type is set, cls represents a legal subclass - use it.
            # Otherwise, try to discover an appropriate subclass based on the
            # element.  If that fails, it will default to the invoking class,
            # which will usually just be EntryWrapper.
            wcls = (cls._class_for_element(response_or_entry.element)
                    if cls.schema_type is None
                    else cls)
            return wcls(response_or_entry, etag)

        # response_or_entry is neither a Response nor an Entry
        fmt = _("Must supply a Response or Entry to wrap.  Got %s")
        raise TypeError(fmt % str(type(response_or_entry)))

    def refresh(self, adapter):
        """Fetch the latest version of the entry from the REST API server.

        If the entry has not been updated on the server, self is returned
        unchanged.  Otherwise a new, fresh wrapper instance is returned.
        Generally, this should be used as:

        wrapper_instance = wrapper_instance.refresh(adapter)

        :param adapter: The pypowervm.adapter.Adapter instance through which to
                        perform the refresh.
        :return: EntryWrapper representing the latest data from the REST API
                 server.  If the input wrapper contains etag information and
                 the server responds 304 (Not Modified), the original wrapper
                 is returned.  Otherwise, a fresh EntryWrapper of the
                 appropriate type is returned.
        """
        resp = adapter.read_by_href(self.href, etag=self.etag)
        if resp.status == 304:
            return self
        return self.wrap(resp)

    @classmethod
    def search(cls, adapter, negate=False, **kwargs):
        """Performs a REST API search.

        Searches for object(s) of the type indicated by wrap_cls having (or not
        having) the key/value indicated by the (single) kwarg.

        Regular expressions and comparators are not supported.

        Currently, only ROOT objects are supported.  (TODO(IBM): Support CHILD)

        :param cls: A subclass of EntryWrapper.  The wrapper class must
                         define a search_keys member, which is a dictionary
                         mapping a convenient kwarg key to a search key
                         supported by the REST API for that object type.  To
                         retrieve an XML report of the supported search keys
                         for object Foo, perform:
                         read('Foo', suffix_type='search')
        :param adapter: The pypowervm.adapter.Adapter instance through which to
                        perform the search.
        :param negate: If True, the search is negated - we find all objects of
                       the indicated type where the search key does *not* equal
                       the search value.
        :param kwargs: Exactly one key=value.  The key must correspond to a key
                       in cls.search_keys.  The value is the value to search
                       for.
        :return: A list of instances of the cls.  The list may be empty
                 (no results were found).  It may contain more than one
                 instance (e.g. for a negated search, or for one where the key
                 does not represent a unique property of the object).
        """
        if len(kwargs) != 1:
            raise ValueError('The search() method requires exactly one'
                             'key=value argument.')
        key = list(kwargs)[0]
        val = str(kwargs[key])
        op = '!=' if negate else '=='
        try:
            search_key = cls.search_keys[key]
        # TODO(IBM) Support fallback search by [GET feed] + loop
        except AttributeError:
            raise ValueError('Wrapper class %s does not support search.' %
                             cls.__name__)
        except KeyError:
            raise ValueError("Wrapper class %s does not support search key "
                             "'%s'." % (cls.__name__, key))
        search_parm = "(%s%s'%s')" % (search_key, op, val)
        # Let this throw HttpError if the caller got it wrong
        resp = adapter.read(cls.schema_type, suffix_type='search',
                            suffix_parm=search_parm)
        return cls.wrap(resp)

    def update(self, adapter, xag=None):
        """Performs adapter.update of this wrapper.

        :param adapter: The pypowervm.adapter.Adapter through which to perform
                        the update.
        :param xag: List of extended attribute group names.
        :return: The updated wrapper, per the response from the Adapter.update.
        """
        # adapter.update_by_path expects the path (e.g.
        # '/rest/api/uom/Object/UUID'), not the whole href.
        path = util.path_from_href(self.href)
        # No-op if xag is empty/None
        path = adapter.extend_path(path, xag=xag)
        return self.wrap(adapter.update_by_path(self, self.etag, path))

    @property
    def element(self):
        return self.entry.element

    @property
    def etag(self):
        return self._etag

    @property
    def href(self):
        """Finds the reference to the entity.

        Assumes that the entity has a link element that references self.  If
        it does not, returns None.
        """
        val = self.entry.properties.get('links', {}).get('SELF', None)
        if val is not None and len(val) > 0:
            return val[0]
        else:
            return None

    @property
    def uuid(self):
        """Returns the uuid of the entry."""
        if self.entry is None:
            return None

        try:
            uuid = self.entry.properties[_UUID]
            return uuid
        except KeyError:
            return None

    @property
    def type_and_uuid(self):
        """Return the type and uuid of this entry together in one string.

        This is useful for error messages, logging, etc.
        """
        entry_type = self.schema_type
        uuid = self.uuid

        if entry_type is None:
            entry_type = "UnknownType"

        if uuid is None:
            uuid = "UnknownUUID"

        return entry_type + ":" + uuid


class ElementWrapper(Wrapper):
    """Base wrapper for Elements."""
    # If it's an Element, it's *probably* a DETAIL.  (Redundant assignment,
    # but prefer to be explicit.)
    has_metadata = False

    @classmethod
    def _bld(cls, tag=None, has_metadata=None, ns=None, attrib=None):
        ret = cls()
        ret.element = cls._bld_element(
            tag, has_metadata=has_metadata, ns=ns, attrib=attrib)
        return ret

    @classmethod
    def wrap(cls, element, **kwargs):
        """Wrap an existing adapter.Element OR construct a fresh one.

        This method should usually be invoked from an ElementWrapper subclass
        decorated by Wrapper.pvm_type, and an instance of that subclass will be
        returned.

        If invoked directly from ElementWrapper, we attempt to detect whether
        an appropriate subclass exists based on the Element's tag.  If so, that
        subclass is used; otherwise a generic ElementWrapper is used.

        :param element: An existing adapter.Element to wrap.
        :returns: An ElementWrapper (subclass) instance containing the element.
        """
        wcls = (cls._class_for_element(element)
                if cls.schema_type is None
                else cls)
        wrap = wcls()
        wrap.element = element
        return wrap

    @property
    def type_and_uuid(self):
        """Return the type and uuid of this entry together in one string.

        This is useful for error messages, logging, etc.
        """
        entry_type = self.schema_type

        if entry_type is None:
            entry_type = "UnknownType"

        return entry_type

    def __eq__(self, other):
        """Tests equality."""
        return self.element == other.element


class WrapperElemList(list):
    """The wrappers can create complex Lists (from a Group from the response).

    The lists that they wrap tend to be generated on each 'get' from the
    property.  This list allows for modification of the 'wrappers' that
    get returned, which update the backing elements.

    This is not a full implementation of a list.  Only the 'common use' methods
    are supported

    Functions that are provided:
     - Getting via index (ex. list[1])
     - Obtaining the length (ex. len(list))
     - Extending the list (ex. list.extend(other_list))
     - Appending to the list (ex. list.append(other_elem))
     - Removing from the list (ex. list.remove(other_elem))
    """

    def __init__(self, root_elem, child_class=None, **kwargs):
        """Creates a new list backed by an Element anchor and child type.

        :param root_elem: The container element.  Should be the backing
                          element, not a wrapper.
                          Ex. The element for 'SharedEthernetAdapters'.
        :param child_class: The child class (subclass of ElementWrapper).
                            This is optional.  If not specified, will wrap
                            all children elements.
        :param kwargs: Optional additional named arguments that may be passed
                       into the wrapper on creation.
        """
        self.root_elem = root_elem
        if child_class is not None:
            self.child_class = child_class
        else:
            # Default to the ElementWrapper, which should resolve to the
            # appropriate class type.
            self.child_class = ElementWrapper
        self.injects = kwargs

    def __find_elems(self):
        if (self.child_class is not None and
                self.child_class is not ElementWrapper):
            return self.root_elem.findall(self.child_class.schema_type)
        else:
            return self.root_elem.getchildren()

    def __getitem__(self, idx):
        if isinstance(idx, slice):
            all_elems = self.__find_elems()
            all_elems = all_elems[idx.start:idx.stop:idx.step]
            return [self.child_class.wrap(x, **self.injects)
                    for x in all_elems]

        elem = self.__find_elems()[idx]
        return self.child_class.wrap(elem, **self.injects)

    def index(self, value):
        elems = self.__find_elems()
        return elems.index(value.element)

    def __getslice__(self, i, j):
        elems = self.__find_elems()
        return [self.child_class.wrap(x, **self.injects)
                for x in elems[i:j]]

    def __len__(self, *args, **kwargs):
        return len(self.__find_elems())

    def __iter__(self):
        elems = self.__find_elems()
        for elem in elems:
            yield self.child_class.wrap(elem, **self.injects)

    def __str__(self):
        elems = self.__find_elems()
        string = '['
        for elem in elems:
            string += str(elem)
            if elem != elems[len(elems) - 1]:
                string += ', '
        string += ']'
        return string

    def __contains__(self, item):
        elems = self.__find_elems()
        return item.element in elems

    def extend(self, seq):
        for elem in seq:
            self.append(elem)

    def append(self, elem):
        self.root_elem.element.append(elem.element.element)

    def remove(self, elem):
        # Try this way first...if there is a value error, that means
        # that the identical element isn't here...need to try 'functionally
        # equivalent' -> slower...
        try:
            self.root_elem.remove(elem.element)
            return
        except ValueError:
            pass

        # Onto the slower path.  Get children and see if any are equivalent
        children = self.root_elem.getchildren()
        equiv = util.find_equivalent(elem.element, children)
        if equiv is None:
            raise ValueError(_('No such child element.'))
        self.root_elem.remove(equiv)


class ActionableList(list):
    """Provides a List that will call back to a function on modification.

    Does not support lower level modifications (ex. list[5] = other_elem),
    but does support extend, append, remove, insert and pop.
    """

    def __init__(self, list_data, action):
        """Creations the action list.

        :param list_data: The list data
        :param action: The action to call back to.  Should take in a list
                       as a parameter (this is then list post modification).
        """
        super(ActionableList, self).__init__(list_data)
        self.action = action

    def extend(self, seq):
        super(ActionableList, self).extend(seq)
        self.action(self)

    def append(self, elem):
        super(ActionableList, self).append(elem)
        self.action(self)

    def remove(self, elem):
        super(ActionableList, self).remove(elem)
        self.action(self)

    def insert(self, index, obj):
        super(ActionableList, self).insert(index, obj)
        self.action(self)

    def pop(self, index=-1):
        elem = super(ActionableList, self).pop(index)
        self.action(self)
        return elem
