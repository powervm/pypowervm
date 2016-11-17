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

"""Base classes for all wrapper classes in the pypowervm.wrappers package."""

import abc
from oslo_log import log as logging
import re
import six
import urllib


from pypowervm import adapter as adpt
import pypowervm.const as pc
import pypowervm.entities as ent
from pypowervm.i18n import _
from pypowervm import util
import pypowervm.utils.uuid as pvm_uuid

LOG = logging.getLogger(__name__)


def _indirect_child_elem(wrap, indirect):
    if indirect is None:
        return wrap.element
    else:
        return ent.Element(indirect, wrap.adapter, children=[wrap.element])


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
    # {schema_type_string:
    #     {'entry': entry_wrapper_class,
    #      'element': element_wrapper_class},
    #  ...}
    # E.g. {'SharedEthernetAdapter':
    #          {'entry': pypowervm.wrappers.network.SEA},
    #       'LogicalUnit':
    #          {'entry': pypowervm.wrappers.storage.LUEnt,
    #           'element': pypowervm.wrappers.storage.LU},
    #       ...}
    # Some schema types double as a ROOT/CHILD object and a DETAIL within a
    # ROOT/CHILD).  Such schema types will have both 'entry' and 'element' keys
    # in the sub-dict.  Otherwise, only one key will exist accordingly.
    _pvm_object_registry = {}

    # Maps a property name to its extended attribute group.  Should be sparse -
    # if a property is not associated with a xag, it can (should) be absent
    # from this dict.
    _xag_registry = {}

    # Allows us to ensure that all Wrapper classes are properly registered via
    # @[base_]pvm_type.
    _registered = False

    @classmethod
    def base_pvm_type(cls, cls_):
        """Decorator/method to register a PowerVM base class.

        Use this instead of @pvm_type on Wrapper subclasses which are not to be
        instantiated, but are themselves bases for real Wrappers.  For example,
        use @base_pvm_type for BasePartition; and @pvm_type for
        LogicalPartition and VirtualIOServer.

        Use as a decorator with no arguments:

        @Wrapper.base_pvm_type
        class SomeBaseClass(Wrapper):
            ...

        Or use as a method to register a base class explicitly after it has
        been defined:

        Wrapper.base_pvm_type(SomeBaseClass)

        :param cls_: The Wrapper subclass to be decorated/registered.
        :return: cls_
        """
        # @xag_property registers with Wrapper._xag_registry because
        # cls_ hasn't been created yet.  Transfer the created registry to the
        # cls_, merging with any already registered by its bases, and clear
        # Wrapper's registry so it doesn't pollute the next cls_.
        cls_._xag_registry = dict(cls_._xag_registry, **Wrapper._xag_registry)
        cls_._registered = True
        Wrapper._xag_registry = {}
        return cls_

    @classmethod
    def _register_schema_type(cls, schema_type, class_):
        """Register this class according to its schema_type.

        The registry is used to identify the appropriate wrapper class to apply
        to an XML object we receive from the REST server.

        :param schema_type: String schema type of the REST element to register.
        :param class_: Concrete {Entry|Element}Wrapper subclass to associate
                       with the schema_type.
        """
        ent_or_el = 'entry' if issubclass(class_, EntryWrapper) else 'element'
        if schema_type not in Wrapper._pvm_object_registry:
            Wrapper._pvm_object_registry[schema_type] = {}
        Wrapper._pvm_object_registry[schema_type][ent_or_el] = class_

    @classmethod
    def pvm_type(cls, schema_type, has_metadata=None, ns=pc.UOM_NS,
                 attrib=pc.DEFAULT_SCHEMA_ATTR, child_order=None):
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
            # Base stuff first (e.g. register extended attribute groups).
            cls.base_pvm_type(class_)
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
            cls._register_schema_type(schema_type, class_)
            return class_
        return inner

    @classmethod
    def xag_property(cls, xag):
        """Decorator to tag a @property with an extended attribute group.

        Use this decorator in place of (not in addition to) @property.  Within
        class Foo:

            @xag_property('bar')
            def some_prop(self):
                ...

        confers the same property-ness on 'some_prop' as would

            @property
            def some_prop(self):
                ...

        but it also associates some_prop with extended attribute group name
        'bar' such that Foo.get_xag_for_prop('some_prop') returns the value
        'bar'.

        :param xag: String name of the extended attribute group with which the
                    decorated property is associated.  May either be one of the
                    pypowervm.const.XAG enum values; or a member of one of the
                    pypowervm.entities.*XAGs collections (for example, see
                    pypowervm.wrappers.virtual_io_server.phys_vols).
        """
        def wrap(func):
            cls._xag_registry[func.__name__] = str(xag)
            return property(func)
        return wrap

    @classmethod
    def get_xag_for_prop(cls, propname):
        """The extended attribute group name for a property of this Wrapper.

        :param propname: Short (unqualified) name of a property of this
                         Wrapper, as a string.
        :return: String indicating the name of the extended attribute group for
                 the given property.  Should be a pypowervm.const.XAG enum
                 value.  None (not 'None') if there is no xag associated with
                 the specified property.
        """
        return cls._xag_registry.get(propname, None)

    @property
    def child_order(self):
        return getattr(self, '_child_order', ())

    @property
    def adapter(self):
        return self.element.adapter

    @property
    def traits(self):
        return self.adapter.traits

    @property
    def uuid(self):
        """Returns the uuid of the entry or element."""
        # The following should only apply to EntryWrappers
        if getattr(self, 'entry', None) is not None:
            return self.entry.uuid

        # Anything with Metadata may have a UUID.  Could do has_metadata check,
        # but that doesn't really add anything.  This will return None if not
        # found.
        return self._get_val_str(pc.UUID_XPATH)

    @uuid.setter
    def uuid(self, value):
        """Sets the UUID (if supported).

        :param value: A valid PowerVM UUID value in either uuid format
                      or string format
        """
        if isinstance(self, WrapperSetUUIDMixin):
            self.set_uuid(value)
        else:
            raise AttributeError(_('Cannot set uuid.'))

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
        if element is None:
            return None
        if use_find_all:
            found_value = element.findall(property_name)
        else:
            found_value = element.find(property_name)

        return found_value  # May be None

    def _find_or_seed(self, prop_name, attrib=pc.DEFAULT_SCHEMA_ATTR):
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
            new_elem = ent.Element(prop_name, self.adapter, attrib=attrib,
                                   children=[])
            self.inject(new_elem)
            return new_elem

    def _get_elem_list(self, tag):
        """An entities.ElementList for a given tag from within this wrapper.

        :param tag: The string XML tag of the values to find.
        :return: An entities.ElementList for the specified tag.
        """
        return ent.ElementList(
            self.element, tag, ordering_list=self.child_order)

    def _set_elem_list(self, tag, val_iter):
        """Set (or replace) the contents of an entities.ElementList.

        :param tag: The string XML tag of the ElementList to assign.
        :param val_iter: Iterable of raw (string) values to set.
        """
        ellist = self._get_elem_list(tag)
        ellist.clear()
        ellist.extend(val_iter)

    def replace_list(self, prop_name, prop_children,
                     attrib=pc.DEFAULT_SCHEMA_ATTR, indirect=None):
        """Replaces a property on this Entry that contains a children list.

        The prop_children represent the new elements for the property.

        If the property does not already exist, this will simply append the
        new children.

        :param prop_name: The property name to replace with the new value.
        :param prop_children: A list of ElementWrapper objects that represent
                              the new children for the property list.
        :param attrib: The attributes to use if the property.  Defaults to
                       the DEFAULT_SCHEM_ATTR.
        :param indirect: Name of a schema element which should wrap each of the
                         prop_children.  For example, VNIC backing devices look
                         like:
                            <AssociatedBackingDevices>
                                <Metadata>...</Metadata>
                                <VirtualNICBackingDeviceChoice>
                                    <VirtualNICSRIOVBackingDevice>
                                        ...
                                    </VirtualNICSRIOVBackingDevice>
                                </VirtualNICBackingDeviceChoice>
                                <VirtualNICBackingDeviceChoice>
                                    <VirtualNICSRIOVBackingDevice>
                                        ...
                                    </VirtualNICSRIOVBackingDevice>
                                </VirtualNICBackingDeviceChoice>
                                ...
                            </AssociatedBackingDevices>
                         In this case, invoke this method as:
                         replace_list(
                             'AssociatedBackingDevices',
                             [<list of VirtualNICSRIOVBackingDevice wrappers>],
                             indirect='VirtualNICBackingDeviceChoice')
        """
        new_elem = ent.Element(prop_name, self.adapter, attrib=attrib,
                               children=[_indirect_child_elem(child, indirect)
                                         for child in prop_children])

        self.inject(new_elem)

    @abc.abstractproperty
    def _type_and_uuid(self):
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
        :param attrib: The element attributes to use if the element is created.
        """
        element_value = self._find(property_name)
        if element_value is None:
            self.log_missing_value(property_name)
            if create:
                element_value = ent.Element(
                    property_name, self.adapter, ns=self.schema_ns,
                    attrib=attrib, text=str(value))
                self.inject(element_value)

        element_value.text = str(value)

    def set_float_gb_value(self, property_name, value, create=True):
        """Special case of set_parm_value for floats of Gigabyte.Type.

        - Gigabyte.Type can't handle more than 6dp.
        - Floating point representation issues can mean that e.g. 0.1 + 0.2
        produces 0.30000000000000004.
        - str() rounds to 12dp.

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
                message = (_(
                    "Cannot convert %(property_name)s='%(value)s' in object "
                    "%(pvmobject)s") % {"property_name": property_name,
                                        "value": text,
                                        "pvmobject": self._type_and_uuid})

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

    def _get_val_percent(self, property_name, default=None):
        """Gets the value in float-percentage format of a PowerVM property.

        :param property_name: property to find
        :param default: Value to return if property is not found. Defaults to
                        None (which is not a float - plan accordingly).
        :return: If the property is say "2.45%", a value of .0245 will be
                 returned. % in the property is optional.
        """
        def str2percent(percent_str):
            if percent_str:
                percent_str = re.findall(r"\d*\.?\d+", percent_str)[0]
                return (float(percent_str))/100
            else:
                return None
        return self.__get_val(property_name, default=default,
                              converter=str2percent)

    def log_missing_value(self, param):
        LOG.trace('The expected parameter of %(param)s was not found in '
                  '%(identifier)s' % {"param": param,
                                      "identifier": self._type_and_uuid})

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
            pathtoks = propname.split(util.XPATH_DELIM)
            append_point = self
            while len(pathtoks) > 1:
                next_prop = pathtoks.pop(0)
                new_el = append_point._find(next_prop)
                if new_el is None:
                    new_el = ent.Element(next_prop, self.adapter)
                    append_point.element.inject(
                        new_el, ordering_list=self.child_order)
                append_point = ElementWrapper.wrap(new_el)
            link = ent.Element(pathtoks[-1], self.adapter)
            append_point.element.inject(link, ordering_list=self.child_order)
        # At this point we have found or created the propname element.  Its
        # handle is in the link var.
        link.attrib['href'] = href
        link.attrib['rel'] = 'related'

    def toxmlstring(self, pretty=False):
        """Produce an XML dump of this Wrapper's Element.

        :param pretty: If True, format the XML in a visually-pleasing manner.
        :return: An XML string representing this Element.
        """
        return self.element.toxmlstring(pretty=pretty)

    @classmethod
    def _bld_element(cls, adapter, tag=None, has_metadata=has_metadata,
                     ns=schema_ns, attrib=default_attrib):
        """Create a fresh entities.Element, usually for immediate wrapping.

        :param adapter: The entities.Adapter to be consulted for traits, etc.
        :param tag: Property name of the new Element.
        :param has_metadata: If True, a <Metadata/> child will be created.
        :param ns: Namespace to use.
        :param attrib: XML attributes to use in the outer Element.
        :return: A fresh adapter.Element.
        """
        # TODO(efried): Get rid of this method - fold it into Element._bld()
        tag = cls.schema_type if tag is None else tag
        # Make sure the call was either through a legal wrapper or explicitly
        # specified a tag name
        if tag is None:
            raise TypeError(_("Refusing to construct and wrap an Element "
                              "without a tag."))
        has_metadata = (cls.has_metadata
                        if has_metadata is None
                        else has_metadata)
        ns = cls.schema_ns if ns is None else ns
        attrib = cls.default_attrib if attrib is None else attrib
        children = []
        if has_metadata:
            children.append(
                ent.Element('Metadata', adapter, ns=ns, children=[
                    ent.Element('Atom', adapter, ns=ns)]))
        return ent.Element(tag, adapter, ns=ns, attrib=attrib,
                           children=children)

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
            return Wrapper._pvm_object_registry[schema_type][
                'entry' if issubclass(cls, EntryWrapper) else 'element']
        except KeyError:
            return cls

    def _bld_link_list(self, container_type, links):
        """Creates an element with a list of <link> children.

        :param container_type: The element that will contain the elements.
        :param links: The set of strings which are link elements.
        """
        new_elems = []
        for item in links:
            new_elems.append(ent.Element('link', self.adapter, attrib={
                'href': item, 'rel': 'related'}))
        return ent.Element(container_type, self.adapter, children=new_elems)


class EntryWrapper(Wrapper):
    """Base Wrapper for the Entry object types."""
    # If it's an Entry, it must be a ROOT or CHILD
    has_metadata = True

    def __init__(self, entry, etag=None):
        self.entry = entry
        self._etag = etag

    @classmethod
    def getter(cls, adapter, entry_uuid=None, parent_class=None,
               parent_uuid=None, xag=None, parent=None):
        """Return EntryWrapperGetter or FeedGetter for this EntryWrapper type.

        Parameters are the same as described by EntryWrapperGetter.__init__
        If entry_uuid is None, a FeedGetter is returned.  Otherwise, an
        EntryWrapperGetter is returned.
        """
        if entry_uuid is None:
            return FeedGetter(
                adapter, cls, parent=parent, parent_class=parent_class,
                parent_uuid=parent_uuid, xag=xag)
        else:
            return EntryWrapperGetter(
                adapter, cls, entry_uuid, parent=parent,
                parent_class=parent_class, parent_uuid=parent_uuid, xag=xag)

    @classmethod
    def _bld(cls, adapter, tag=None, has_metadata=None, ns=None, attrib=None):
        """Create a fresh EntryWrapper.

        :param adapter: A pypowervm.adapter.Adapter (for traits, etc.)
        :param tag: XML tag for the EntryWrapper's Entry's root Element.
        :param has_metadata: If True, a basic <Metadata/> child is created
                             under the root element.
        :param ns: XML namespace for the contents.
        :param attrib: XML attributes for the root element.
        """
        element = cls._bld_element(
            adapter, tag, has_metadata=has_metadata, ns=ns, attrib=attrib)
        return cls(ent.Entry({'title': element.tag}, element.element, adapter))

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
                return [cls.wrap(entry, etag=entry.etag)
                        for entry in response_or_entry.feed.entries]
            else:
                raise KeyError(_("Response is missing 'entry' property."))

        # Else process Entry if specified
        if isinstance(response_or_entry, ent.Entry):
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

    def refresh(self, use_etag=True):
        """Fetch the latest version of the entry from the REST API server.

        If the entry has not been updated on the server, self is returned
        unchanged.  Otherwise a new, fresh wrapper instance is returned.
        Generally, this should be used as:

        wrapper_instance = wrapper_instance.refresh()

        :param use_etag: (Optional) If False, the object's etag will not be
                         sent with the request, ensuring that the object is
                         retrieved afresh from the server.
        :return: EntryWrapper representing the latest data from the REST API
                 server.  If the input wrapper contains etag information and
                 the server responds 304 (Not Modified), the original wrapper
                 is returned.  Otherwise, a fresh EntryWrapper of the
                 appropriate type is returned.
        """
        etag = self.etag if use_etag else None
        resp = self.adapter.read_by_href(self.href, etag=etag)
        if resp.status == pc.HTTPStatus.NO_CHANGE:
            return self
        return self.wrap(resp)

    @classmethod
    def get(cls, adapter, uuid=None, parent_type=None, parent_uuid=None,
            parent=None, **read_kwargs):
        """GET and wrap an entry or feed of this type.

        Shortcut to EntryWrapper.wrap(adapter.read(...)).
        For example, retrieving a ROOT object:
            resp = adapter.read(VIOS.schema_type, root_id=v_uuid, xag=xags)
            vwrap = VIOS.wrap(resp)
        Becomes:
            vwrap = VIOS.get(adapter, uuid=v_uuid, xag=xags)

        Or retrieving a CHILD feed:
            resp = adapter.read(System.schema_type, root_id=sys_uuid,
                                child_type=VSwitch.schema_type)
            vswfeed = VSwitch.wrap(resp)
        Becomes:
            vswfeed = VSwitch.get(adapter, parent=sys)
        Or:
            vswfeed = VSwitch.get(adapter, parent_type=System,
                                  parent_uuid=sys_uuid)

        :param cls: A subclass of EntryWrapper.  Its schema_type will be used
                    as the first argument to adapter.read()
        :param adapter: The pypowervm.adapter.Adapter instance through which to
                        perform the GET.
        :param uuid: If retrieving a single entry, specify its string UUID.
                     For ROOT objects, you may specify either uuid or root_id;
                     for CHILD objects, you may specify either uuid or
                     child_id.
        :param parent_type: If the invoking class represents a CHILD, specify
                            either the parent parameter or BOTH parent_type and
                            parent_uuid. This parameter may be either the
                            schema_type or the EntryWrapper subclass of the
                            parent ROOT object.
        :param parent_uuid: If the invoking class represents a CHILD, specify
                            either the parent parameter or BOTH parent_type and
                            parent_uuid. This parameter indicates the UUID of
                            the parent ROOT object. Do not use the root_id
                            parameter.
        :param parent: If the invoking class represents a CHILD, specify either
                       the parent parameter or BOTH parent_type and
                       parent_uuid.  This parameter is an EntryWrapper
                       representing the parent ROOT object of the CHILD to be
                       retrieved.
        :param read_kwargs: Any arguments to be passed directly through to
                            Adapter.read().
        :return: An EntryWrapper (or list thereof) around the requested REST
                 object.  (Note that this may not be of the type from which the
                 method was invoked, e.g. if the child_type parameter is used.)
        """
        parent_type, parent_uuid = util.parent_spec(parent, parent_type,
                                                    parent_uuid)
        if parent_type is not None:
            # CHILD mode
            resp = cls._read_child(adapter, parent_type, parent_uuid, uuid,
                                   read_kwargs)
        else:
            # ROOT mode
            if any(k in read_kwargs for k in ('child_type', 'child_id')):
                raise ValueError(_("Developer error: specify 'parent' or "
                                   "('parent_type' and 'parent_uuid') to "
                                   "retrieve a CHILD object."))
            if uuid is not None:
                if 'root_id' in read_kwargs:
                    raise ValueError(_("Specify either 'uuid' or 'root_id' "
                                       "when requesting a ROOT object."))
                read_kwargs['root_id'] = uuid
            resp = adapter.read(cls.schema_type, **read_kwargs)
        return cls.wrap(resp)

    @classmethod
    def _read_child(cls, adapter, parent_type, parent_uuid, uuid, read_kwargs):
        """Helper method for 'get' to read CHILD feed or entry Response.

        Params are as described in the 'get' method.
        """
        if parent_uuid is None:
            raise ValueError(_("Both parent_type and parent_uuid are required "
                               "when retrieving a CHILD feed or entry."))
        if 'root_id' in read_kwargs:
            raise ValueError(_("Specify the parent's UUID via the parent_uuid "
                               "parameter."))
        if uuid is not None:
            if 'child_id' in read_kwargs:
                raise ValueError(_("Specify either 'uuid' or 'child_id' when "
                                   "requesting a CHILD object."))
            read_kwargs['child_id'] = uuid
        # Accept parent_type as either EntryWrapper subclass or string
        if not isinstance(parent_type, str):
            parent_type = parent_type.schema_type
        return adapter.read(parent_type, root_id=parent_uuid,
                            child_type=cls.schema_type, **read_kwargs)

    @classmethod
    def get_by_href(cls, adapter, href, **rbh_kwargs):
        """Get a wrapper or feed given a URI.

        This can be useful for retrieving wrappers "associated" with other
        wrappers, where the association is provided via an atom link.  Some
        examples are TrunkAdapter.associated_vswitch_uri and
        VNICBackDev.vios_href.

        :param adapter: A pypowervm.adapter.Adapter instance for REST API
                        communication.
        :param href: The string URI (including scheme://host:port/) of the
                     entry or feed to retrieve.
        :param rbh_kwargs: Keyword arguments to be passed directly to Adapter's
                           read_by_href method.
        :return: EntryWrapper subclass of the appropriate type, or a list
                 thereof, representing the entry/feed associated with the href
                 parameter.
        """
        return cls.wrap(adapter.read_by_href(href, **rbh_kwargs))

    @classmethod
    def search(cls, adapter, negate=False, xag=None, parent_type=None,
               parent_uuid=None, one_result=False, parent=None, **kwargs):
        """Performs a REST API search.

        Searches for object(s) of the type indicated by cls having (or not
        having) the key/value indicated by the (single) kwarg.

        Regular expressions, comparators, and logical operators are not
        supported.

        :param cls: A subclass of EntryWrapper.  The wrapper class may define
                    a search_keys member, which is a dictionary mapping a
                    @property getter method name to a search key supported by
                    the REST API for that object type.  To retrieve an XML
                    report of the supported search keys for object Foo,
                    perform: read('Foo', suffix_type='search').
                    If the wrapper class does not define a search_keys member,
                    OR if xag is None, the fallback search algorithm performs a
                    GET of the entire feed of the object type and loops through
                    it looking for (mis)matches on the @property indicated by
                    the search key.
        :param adapter: The pypowervm.adapter.Adapter instance through which to
                        perform the search.
        :param negate: If True, the search is negated - we find all objects of
                       the indicated type where the search key does *not* equal
                       the search value.
        :param xag: List of extended attribute group names.
        :param parent_type: If searching for CHILD objects, specify either
                            the parent parameter or BOTH parent_type and
                            parent_uuid.  This parameter indicates the parent
                            ROOT object.  It may be either the string schema
                            type or the corresponding EntryWrapper subclass.
        :param parent_uuid: If searching for CHILD objects, specify either
                            the parent parameter or BOTH parent_type and
                            parent_uuid.  This parameter specifies the UUID of
                            the parent ROOT object.  If parent_type is
                            specified, but parent_uuid is None, all parents of
                            the ROOT type will be searched. This may result in
                            a slow response time.
        :param one_result: Use when expecting (at most) one search result.  If
                           True, this method will return the first element of
                           the search result list, or None if the search
                           produced no results.
        :param parent: If searching for CHILD objects, specify either the
                       parent parameter or BOTH parent_type and parent_uuid.
                       This parameter is an EntryWrapper instance indicating
                       the parent ROOT object.
        :param kwargs: Exactly one key=value.  The key must correspond to a key
                       in cls.search_keys and/or the name of a getter @property
                       on the EntryWrapper subclass.  Due to limitations of
                       the REST API, if specifying xags or searching for a
                       CHILD, the key must be the name of a getter @property.
                       The value is the value to match.
        :return: If one_result=False (the default), a list of instances of the
                 cls.  The list may be empty (no results were found).  It may
                 contain more than one instance (e.g. for a negated search, or
                 for one where the key does not represent a unique property of
                 the object).  If one_result=True, returns a single instance of
                 cls, or None if the search produced no results.
        """
        def list_or_single(results, single):
            """Returns either the results list or its first entry.

            :param results: The list of results from the search.  May be empty.
                            Must not be None.
            :param single: If False, return results unchanged.  If True, return
                           only the first entry in the results list, or None if
                           results is empty.
            """
            if not single:
                return results
            return results[0] if results else None

        try:
            parent_type, parent_uuid = util.parent_spec(parent, parent_type,
                                                        parent_uuid)
        except ValueError:
            # Special case where we allow parent_type without parent_uuid.  The
            # reverse is caught by the check below.
            if parent_type is not None and type(parent_type) is not str:
                parent_type = parent_type.schema_type

        # parent_uuid makes no sense without parent_type
        if parent_type is None and parent_uuid is not None:
            raise ValueError(_('Parent UUID specified without parent type.'))

        if len(kwargs) != 1:
            raise ValueError(_('The search() method requires exactly one '
                               'key=value argument.'))

        key, val = kwargs.popitem()
        try:
            # search API does not support xag or CHILD
            if xag is not None or parent_type is not None:
                # Cheater's way to cause _search_by_feed to be invoked
                raise AttributeError()
            search_key = cls.search_keys[key]
        except (AttributeError, KeyError):
            # Fallback search by [GET feed] + loop
            return list_or_single(
                cls._search_by_feed(adapter, cls.schema_type, negate, key, val,
                                    xag, parent_type, parent_uuid), one_result)

        op = '!=' if negate else '=='
        quote = urllib.parse.quote if six.PY3 else urllib.quote
        search_parm = "(%s%s'%s')" % (search_key, op, quote(str(val), safe=''))
        # Let this throw HttpError if the caller got it wrong.
        # Note that this path will only be hit for ROOTs.
        return list_or_single(
            cls.wrap(cls._read_parent_or_child(
                adapter, cls.schema_type, parent_type, parent_uuid,
                suffix_type='search', suffix_parm=search_parm)),
            one_result)

    @classmethod
    def _search_by_feed(cls, adapter, target_type, negate, key, val, xag,
                        parent_type, parent_uuid):
        if not hasattr(cls, key):
            raise ValueError(_("Wrapper class %(class)s does not support "
                               "search key '%(key)s'.") %
                             {'class': cls.__name__, 'key': key})
        feedwrap = cls.wrap(cls._read_parent_or_child(adapter, target_type,
                                                      parent_type, parent_uuid,
                                                      xag=xag))
        retlist = []
        val = str(val)
        for entry in feedwrap:
            entval = str(getattr(entry, key, None))
            include = (entval != val) if negate else (entval == val)
            if include:
                retlist.append(entry)
        return retlist

    @staticmethod
    def _read_parent_or_child(adapter, target_type, parent_type, parent_uuid,
                              **kwargs):
        if parent_type is None:
            # ROOT feed search
            return adapter.read(target_type, **kwargs)
        if parent_uuid is not None:
            # CHILD of a specific ROOT
            return adapter.read(parent_type, root_id=parent_uuid,
                                child_type=target_type, **kwargs)
        # Search all ROOTs of the specified type.
        ret = None
        # Wishing there was a quick URI to get all UUIDs.
        # Let EntryWrapper.wrap figure out the wrapper type.  Whatever it
        # is, the uuid @property is available.
        for parent in EntryWrapper.wrap(adapter.read(parent_type)):
            resp = adapter.read(
                parent_type, root_id=parent.uuid, child_type=target_type,
                **kwargs)
            # This is a bit of a cheat.  Technically extending the feed of
            # a Response doesn't result in a legal Response (the rest of
            # the metadata won't accurately reflect the feed).  However
            # this is guaranteed only to be used immediately by wrap() to
            # extract the Entrys.
            if ret is None:
                ret = resp
            else:
                ret.feed.entries.extend(resp.feed.entries)
        return ret

    def create(self, parent_type=None, parent_uuid=None, timeout=-1,
               parent=None):
        """Performs an adapter.create (REST API PUT) with this wrapper.

        :param parent_type: If creating a CHILD, specify either the parent
                            parameter or BOTH parent_type and parent_uuid.
                            This parameter may be either the schema_type or the
                            EntryWrapper subclass of the parent ROOT object.
        :param parent_uuid: If creating a CHILD, specify either the parent
                            parameter or BOTH parent_type and parent_uuid.
                            This parameter indicates the UUID of the parent
                            ROOT object.
        :param timeout: (Optional) Integer number of seconds after which to
                        time out the PUT request.  -1, the default, causes the
                        request to use the timeout value configured on the
                        Session belonging to the Adapter.
        :param parent: If creating a CHILD, specify either the parent parameter
                       or BOTH parent_type and parent_uuid.  This parameter is
                       an EntryWrapper representing the parent ROOT object of
                       the CHILD to be created.
        :return: New EntryWrapper of the invoking class representing the PUT
                 response.
        """
        service = pc.SERVICE_BY_NS[self.schema_ns]
        parent_type, parent_uuid = util.parent_spec(parent, parent_type,
                                                    parent_uuid)
        if parent_type is None and parent_uuid is None:
            # ROOT
            resp = self.adapter.create(self, self.schema_type, service=service,
                                       timeout=timeout)
        else:
            # CHILD
            resp = self.adapter.create(
                self, parent_type, root_id=parent_uuid,
                child_type=self.schema_type, service=service, timeout=timeout)
        return self.wrap(resp)

    def delete(self):
        """Performs an adapter.delete (REST API DELETE) with this wrapper."""
        self.adapter.delete_by_href(self.href, etag=self.etag)

    # TODO(IBM): Remove deprecated xag parameter
    def update(self, xag='__DEPRECATED__', timeout=-1):
        """Performs adapter.update of this wrapper.

        :param xag: DEPRECATED - do not use.
        :param timeout: (Optional) Integer number of seconds after which to
                        time out the POST request.  -1, the default, causes the
                        request to use the timeout value configured on the
                        Session belonging to the Adapter.
        :return: The updated wrapper, per the response from the Adapter.update.
        """
        if xag != '__DEPRECATED__':
            import warnings
            warnings.warn(
                _("The 'xag' parameter to EntryWrapper.update is deprecated!  "
                  "At best, using it will result in a no-op.  At worst, it "
                  "will give you incurable etag mismatch errors."),
                DeprecationWarning)
        if timeout == -1:
            # Override default timeout to 60 minutes unless the Session is
            # configured for longer already.
            timeout = max(60 * 60, self.adapter.session.timeout)

        # adapter.update_by_path expects the path (e.g.
        # '/rest/api/uom/Object/UUID'), not the whole href.
        path = util.dice_href(self.href, include_fragment=False)
        return self.wrap(self.adapter.update_by_path(self, self.etag, path,
                                                     timeout=timeout))

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
        return self.entry.self_link

    @property
    def related_href(self):
        """Returns the URI to be used for references in other elements.

        This will return a root URI (no extended attributes, no fragments).
        This should be used as needed to support entries/elements that have
        relationships to others.
        """
        temp_href = self.href
        return util.dice_href(temp_href, include_scheme_netloc=True,
                              include_query=False, include_fragment=False)

    @property
    def _type_and_uuid(self):
        """Return the type and uuid of this entry together in one string.

        This is useful for error messages, logging, etc.
        """
        entry_type = self.schema_type
        uuid = self.uuid

        if entry_type is None:
            entry_type = self.__class__.__name__

        if uuid is None:
            uuid = "UnknownUUID"

        return entry_type + ":" + uuid


class ElementWrapper(Wrapper):
    """Base wrapper for Elements."""
    # If it's an Element, it's *probably* a DETAIL.  (Redundant assignment,
    # but prefer to be explicit.)
    has_metadata = False

    @classmethod
    def _bld(cls, adapter, tag=None, has_metadata=None, ns=None, attrib=None):
        """Create a fresh ElementWrapper.

        :param adapter: A pypowervm.adapter.Adapter (for traits, etc.)
        :param tag: XML tag for the ElementWrapper's root Element.
        :param has_metadata: If True, a basic <Metadata/> child is created
                             under the root element.
        :param ns: XML namespace for the contents.
        :param attrib: XML attributes for the root element.
        """
        ret = cls()
        ret.element = cls._bld_element(
            adapter, tag=tag, has_metadata=has_metadata, ns=ns, attrib=attrib)
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
        :param **kwargs: Arbitrary attributes to set on the new ElementWrapper.
        :returns: An ElementWrapper (subclass) instance containing the element.
        """
        wcls = (cls._class_for_element(element)
                if cls.schema_type is None
                else cls)
        wrap = wcls()
        wrap.element = element
        for key, val in kwargs.items():
            setattr(wrap, key, val)
        return wrap

    @property
    def _type_and_uuid(self):
        """Return the type of this element.

        This is useful for error messages, logging, etc.
        """
        entry_type = self.schema_type

        if entry_type is None:
            entry_type = self.__class__.__name__

        return entry_type

    def __eq__(self, other):
        """Tests equality."""
        return self.element == other.element

    def __hash__(self):
        """Hash value.

        Necessary to be overwritten because of the side effect in Python 3.x
        of overwriting the __eq__ method causing an object to be unhashable.
        """
        return super(ElementWrapper, self).__hash__()


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

    def __init__(self, root_elem, child_class=None, indirect=None, **kwargs):
        """Creates a new list backed by an Element anchor and child type.

        :param root_elem: The container element.  Should be the backing
                          element, not a wrapper.
                          Ex. The element for 'SharedEthernetAdapters'.
        :param child_class: The child class (subclass of ElementWrapper).
                            This is optional.  If not specified, will wrap
                            all children elements.
        :param indirect: Name of schema layer to ignore between root_elem and
                         the target child_class.  This is for schema structures
                         such as:
                            <IOAdapters>
                                <IOAdapterChoice>
                                    <IOAdapter>...</IOAdapter>
                                </IOAdapterChoice>
                                <IOAdapterChoice>
                                    <SRIOVAdapter>...</SRIOVAdapter>
                                </IOAdapterChoice>
                                ...
                          </IOAdapters>
                         In this case, we want WrapperElemList to return
                            [IOAdapter, SRIOVAdapter, ...]
                         ...ignoring the intervening <IOAdapterChoice/>
                         layer, so we would set indirect='IOAdapterChoice'.
                         Note that we rely upon the intervening layer (in this
                         example, IOAdapterChoice) to contain nothing but the
                         target element type - not even <Metadata/>.
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
        self.indirect = indirect
        self.injects = kwargs

    def __find_elems(self):
        root_elems = self.root_elem.findall(
            self.indirect) if self.indirect else [self.root_elem]
        found = []
        for root_elem in root_elems:
            if (self.child_class is not None and
                    self.child_class is not ElementWrapper):
                found.extend(root_elem.findall(self.child_class.schema_type))
            else:
                found.extend(list(root_elem))
        return found

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
        return '[' + ', '.join([str(self.child_class.wrap(
            elem, **self.injects)) for elem in self.__find_elems()]) + ']'

    def __repr__(self):
        return '[' + ', '.join([repr(self.child_class.wrap(
            elem, **self.injects)) for elem in self.__find_elems()]) + ']'

    def __contains__(self, item):
        elems = self.__find_elems()
        return item.element in elems

    def extend(self, seq):
        for elem in seq:
            self.append(elem)

    def append(self, elem):
        self.root_elem.element.append(
            _indirect_child_elem(elem, self.indirect).element)

    def remove(self, elem):
        find_elem = _indirect_child_elem(elem, self.indirect)
        # Try this way first...if there is a value error, that means
        # that the identical element isn't here...need to try 'functionally
        # equivalent' -> slower...
        try:
            self.root_elem.remove(find_elem)
            return
        except ValueError:
            pass

        # Onto the slower path.  Get children and see if any are equivalent
        children = list(self.root_elem)
        equiv = util.find_equivalent(find_elem, children)
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


@six.add_metaclass(abc.ABCMeta)
class WrapperSetUUIDMixin(object):
    """Abstract mixin to enable a Wrapper instance to set its UUID.

    USE WITH CAUTION.  Caveats:
    This will only work on Wrappers with has_metadata=True.
    Not all elements accept a consumer-set UUID.  Of those that do, some
    only accept it at creation, not on update.
    """

    def set_uuid(self, new_uuid):
        """Set the UUID of the XML entity represented by this Wrapper.

        :param new_uuid: The UUID to set.  Must valid uuid type or string
                         properly formatted (e.g. 8-4-4-4-12)
        """
        if not self.has_metadata:
            raise AttributeError(
                _('Cannot set UUID on Wrapper with no Metadata.'))

        # Step 1: sanitize uuid value
        s_uuid = str(new_uuid)
        if s_uuid != pvm_uuid.convert_uuid_to_pvm(s_uuid):
            raise ValueError(_('uuid value not valid: %s') % new_uuid)

        # Step 2: (vivify and) set Metadata/Atom/AtomID
        atom = self._find('Metadata/Atom')
        atomid = atom.find('AtomID')
        if atomid is None:
            atomid = ent.Element('AtomID', self.adapter)
            atom.append(atomid)
        atomid.text = s_uuid

        # Step 3: if an Atom, update the properties['id'] to match
        try:
            self.entry.properties['id'] = s_uuid
        except AttributeError:
            # No entry (this is an ElementWrapper) - nothing to do.
            # Note: we don't trap KeyError: if entry.properties is there, but
            # doesn't have an 'id' key, something is wrong.
            pass


class EntryWrapperGetter(object):
    """Attribute container with enough information to GET an EntryWrapper.

    An instance of this class can be used to defer the REST call which fetches
    a PowerVM object.  This will typically be used to initialize a
    pypowervm.utils.transaction.WrapperTask, or as the first parameter to a
    method decorated as pypowervm.utils.transaction.entry_transaction, allowing
    that method to acquire a lock before performing the GET, thus minimizing
    the probability of out-of-band changes resulting in etag mismatch and
    requiring a retry.
    """
    def __init__(self, adapter, entry_class, entry_uuid, parent_class=None,
                 parent_uuid=None, xag=None, parent=None):
        """Create a GET specification for an EntryWrapper.

        :param adapter: A pypowervm.adapter.Adapter instance through which the
                        GET can be performed.
        :param entry_class: An EntryWrapper subclass indicating the type of the
                            entry to GET.
        :param entry_uuid: The string UUID of the entry to GET.
        :param parent_class: If the target object type is CHILD, specify either
                             the parent parameter or BOTH parent_class and
                             parent_uuid.  This param is the EntryWrapper
                             subclass of the ROOT parent object type.
        :param parent_uuid: If the target object type is CHILD, specify either
                            the parent parameter or BOTH parent_class and
                            parent_uuid.this param is the UUID of the ROOT
                            parent object.
        :param xag: List of extended attribute groups to request on the object.
        :param parent: If the target object type is CHILD, specify either the
                       parent parameter or BOTH parent_class and parent_uuid.
                       This parameter represents the ROOT parent object.
        """
        def validate_wrapper_type(var):
            if not issubclass(type(var), type) or not issubclass(var, Wrapper):
                raise ValueError(_("Must specify a Wrapper subclass."))
        self.adapter = adapter
        validate_wrapper_type(entry_class)
        self.entry_class = entry_class
        self.entry_uuid = entry_uuid
        parent_class, parent_uuid = util.parent_spec(parent, parent_class,
                                                     parent_uuid)
        if (parent_class and not parent_uuid) or (
                parent_uuid and not parent_class):
            raise ValueError(_("Must specify both parent class and parent "
                               "UUID, or neither."))
        self.parent_class = parent_class
        self.parent_uuid = parent_uuid
        self.xag = xag
        self.cache = None

    def get(self, refresh=False):
        """Return the EntryWrapper indicated by this instance.

        If the EntryWrapper has not yet been retrieved, it is fetched via GET
        from the REST API.  Thereafter, it is cached.  Subsequent calls to this
        method will return the cached copy unless refresh=True, in which case
        the cached copy is refreshed before returning.

        :param refresh: (Optional) If True, and the specified EntryWrapper was
                        previously retrieved, it is refreshed before being
                        returned.  If False (the default), it is returned
                        without refreshing.  If the specified EntryWrapper had
                        not yet been retrieved, this parameter has no effect.
        :return: The EntryWrapper specified by this EntryWrapperGetter
                 instance.
        """
        if self.cache is None:
            if self.parent_class:
                root_type = self.parent_class
                root_id = self.parent_uuid
                child_type = self.entry_class.schema_type
                child_id = self.entry_uuid
            else:
                root_type = self.entry_class.schema_type
                root_id = self.entry_uuid
                child_type = None
                child_id = None
            self.cache = self.entry_class.wrap(self.adapter.read(
                root_type, root_id, child_type=child_type, child_id=child_id,
                xag=self.xag))
        elif refresh:
            self.cache = self.cache.refresh()
        return self.cache

    @property
    def uuid(self):
        """Return the UUID of the entry for which this spec was created.

        This mainly exists so we can ask for wrapper_or_spec.uuid.
        """
        return self.entry_uuid


class FeedGetter(EntryWrapperGetter):
    """Attribute container with enough information to GET an EntryWrapper feed.

    An instance of this class can be used to defer the REST call which fetches
    a feed of PowerVM objects (a list of EntryWrapper).  This will typically be
    used to initialize a pypowervm.utils.transaction.FeedTask, allowing the
    FeedTask to defer the GET as long as possible, thus minimizing the
    probability of out-of-band changes resulting in etag mismatch and requiring
    a retry.
    """
    def __init__(self, adapter, entry_class, parent_class=None,
                 parent_uuid=None, xag=None, parent=None):
        """Create a GET specification for an EntryWrapper feed.

        :param adapter: A pypowervm.adapter.Adapter instance through which the
                        GET can be performed.
        :param entry_class: An EntryWrapper subclass indicating the type of the
                            feed to GET.
        :param parent_class: If the target object type is CHILD, specify either
                             the parent parameter or BOTH parent_class and
                             parent_uuid.  This param is the EntryWrapper
                             subclass of the ROOT parent object type.
        :param parent_uuid: If the target object type is CHILD, specify either
                            the parent parameter or BOTH parent_class and
                            parent_uuid.this param is the UUID of the ROOT
                            parent object.
        :param xag: List of extended attribute groups to request on the feed.
        :param parent: If the target object type is CHILD, specify either the
                       parent parameter or BOTH parent_class and parent_uuid.
                       This parameter represents the ROOT parent object.
        """
        # Using entry_uuid=None will cause the GET to fetch the feed.
        super(FeedGetter, self).__init__(
            adapter, entry_class, None, parent=parent,
            parent_class=parent_class, parent_uuid=parent_uuid, xag=xag)

    def get(self, refresh=False, refetch=False):
        """Return the feed (list of EntryWrappers) indicated by this instance.

        If the feed has not yet been retrieved, it is fetched via GET from the
        REST API.  Thereafter, it is cached.  Subsequent calls to this
        method will return the cached copy unless refresh or refetch is
        specified.

        The refresh option, if True, will cause each entry in the feed to be
        refreshed if previously cached.  The refetch option, if True, will
        cause the feed to be refetched as a whole.

        Note: due to the design of the REST server, refetch will generally
        perform better than refresh.

        :param refresh: (Optional) If True, and the specified feed was
                        previously retrieved, each entry therein is refreshed
                        before the feed is returned.  If the specified feed had
                        not yet been retrieved, this parameter has no effect.
                        If both refresh and refetch are True, refresh takes
                        precedence.
        :param refetch: (Optional) If True, a fresh GET of the entire feed is
                        performed, regardless of whether the feed was fetched
                        and cached previously.
                        If both refresh and refetch are True, refresh takes
                        precedence.
        :return: The feed (list of EntryWrappers) specified by this FeedGetter
                 instance.
        """
        # Note: self.cache is the feed (list of EntryWrapper) in the context of
        # this subclass.  Therefore, the superclass's concept of 'refresh' is
        # no good (it would be trying [ewrap, ...].refresh()).
        if refresh and self.cache is not None:
            # Future: parallelize, for what it's worth.
            new_feed = [ewrap.refresh() for ewrap in self.cache]
            self.cache = new_feed
            return self.cache

        # To refetch, simply wipe the cache before super.get().
        if refetch:
            self.cache = None

        # Never, never call super.get(refresh=True).
        return super(FeedGetter, self).get(refresh=False)


class UUIDFeedGetter(FeedGetter):
    """Quasi-FeedGetter that builds its "feed" based on a list of UUIDs.

    This is expected to be useful for building FeedTasks when, for example:
    - The FeedTask is operating on an SSP (the VIOSes aren't necessarily all in
      the same feed);
    - The operation is only concerned with one REST object, but a WrapperTask
      is not sufficient.
    """
    def __init__(self, adapter, entry_class, uuid_list, parent_class=None,
                 parent_uuid=None, xag=None, parent=None):
        """Create a UUIDFeedGetter.

        :param adapter: See FeedGetter.
        :param entry_class: See FeedGetter.
        :param uuid_list: Iterable of string UUIDs of the objects with which to
                          populate the quasi-feed.
        :param parent_class: See FeedGetter.
        :param parent_uuid: See FeedGetter.
        :param xag: See FeedGetter.
        :param parent: See FeedGetter.
        """
        super(UUIDFeedGetter, self).__init__(
            adapter, entry_class, parent=parent, parent_class=parent_class,
            parent_uuid=parent_uuid, xag=xag)
        self.uuid_list = uuid_list
        self._create_wrapper_getters()

    def _create_wrapper_getters(self):
        self.wrapper_getters = [EntryWrapperGetter(
            self.adapter, self.entry_class, entry_uuid,
            parent_class=self.parent_class, parent_uuid=self.parent_uuid,
            xag=self.xag) for entry_uuid in self.uuid_list]

    def get(self, refresh=False, refetch=False):
        """Get the individual wrappers for each UUID and put them in a 'feed'.

        :param refresh: See FeedGetter.get.
        :param refetch: See FeedGetter.get.
        """
        if refetch:
            # Rebuild the wrapper getters, guaranteeing that we clear anything
            # already fetched
            self._create_wrapper_getters()
        # Populate the quasi-feed from the individual wrapper getters.
        # Future: parallelize, for what it's worth.
        return [wg.get(refresh=refresh) for wg in self.wrapper_getters]
