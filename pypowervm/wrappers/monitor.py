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

"""Wrappers/helpers for Performance and Capacity Monitoring (PCM) metrics."""

import abc
import datetime
import pytz
import six

from oslo_log import log as logging

from pypowervm import adapter as adpt
import pypowervm.const as pc
import pypowervm.util as u
import pypowervm.wrappers.entry_wrapper as ewrap

# Constants that make up the http path
PREFERENCES = 'preferences'
RAW_METRICS = 'RawMetrics'
LONG_TERM_MONITOR = 'LongTermMonitor'
SHORT_TERM_MONITOR = 'ShortTermMonitor'
PCM_SERVICE = 'pcm'

_SYSTEM_NAME = 'SystemName'
_LTM_ENABLED = 'LongTermMonitorEnabled'
_AGG_ENABLED = 'AggregationEnabled'
_STM_ENABLED = 'ShortTermMonitorEnabled'
_COMP_LTM_ENABLED = 'ComputeLTMEnabled'

_UPDATED = 'updated'
_TITLE = 'title'
_PUBLISHED = 'published'
_CATEGORY = 'category'

_DATETIME_FORMAT = '%Y-%m-%dT%H:%M:%S.%f'

LOG = logging.getLogger(__name__)


@ewrap.EntryWrapper.pvm_type('ManagedSystemPcmPreference', ns=pc.PCM_NS)
class PcmPref(ewrap.EntryWrapper):
    """Wraps the Performance and Capacity Monitoring preferences."""

    @property
    def system_name(self):
        return self._get_val_str(_SYSTEM_NAME)

    @property
    def ltm_enabled(self):
        """Long Term Monitoring."""
        return self._get_val_bool(_LTM_ENABLED)

    @ltm_enabled.setter
    def ltm_enabled(self, value):
        """Long Term Monitoring."""
        self.set_parm_value(_LTM_ENABLED, u.sanitize_bool_for_api(value))

    @property
    def aggregation_enabled(self):
        """Metrics Aggregation."""
        return self._get_val_bool(_AGG_ENABLED)

    @aggregation_enabled.setter
    def aggregation_enabled(self, value):
        """Metrics Aggregation."""
        self.set_parm_value(_AGG_ENABLED, u.sanitize_bool_for_api(value))

    @property
    def stm_enabled(self):
        """Short Term Monitoring."""
        return self._get_val_bool(_STM_ENABLED)

    @stm_enabled.setter
    def stm_enabled(self, value):
        """Short Term Monitoring.

        Short Term metrics can affect the performance of workloads.  Not
        recommended for production workload.
        """
        self.set_parm_value(_STM_ENABLED, u.sanitize_bool_for_api(value))

    @property
    def compute_ltm_enabled(self):
        """Compute Long Term Monitoring."""
        return self._get_val_bool(_COMP_LTM_ENABLED)

    @compute_ltm_enabled.setter
    def compute_ltm_enabled(self, value):
        """Compute Long Term Monitoring."""
        self.set_parm_value(_COMP_LTM_ENABLED, u.sanitize_bool_for_api(value))


@six.add_metaclass(abc.ABCMeta)
class MonitorMetrics(object):
    """A pseudo wrapper for Monitor metrics.

    The standard pattern of wrapping a response or entry and accessing
    properties for the data can be used, even though this isn't a traditional
    EntryWrapper.
    """
    def __init__(self, entry):
        self.entry = entry

    @staticmethod
    def _str_to_datetime(str_date):
        # The format of the string is one of two ways.
        # Current: 2015-04-30T06:11:35.000-05:00
        # Legacy: 2015-04-30T06:11:35.000Z (the Z was meant to be timezone).
        #
        # The formatter will strip any Z's that may be in the string out.
        str_date = str_date.replace('Z', '-00:00')

        # Separate out the timezone.  Datetime doesn't like formatting time
        # zones, so we pull it out for manual parsing.  It is the 6th digit
        # from the right.
        str_date, str_tz = str_date[:-6], str_date[-6:]

        # We now have the date, without the timezone.
        date = (datetime.datetime.strptime(str_date, _DATETIME_FORMAT).
                replace(tzinfo=pytz.utc))

        # Parse out the timezone.
        tz_oper = str_tz[0]
        tz_hr, tz_min = int(str_tz[1:3]), int(str_tz[4:6])
        tz_delta = datetime.timedelta(hours=tz_hr, minutes=tz_min)

        # Return the date plus/minus the timezone delta.
        return (date + tz_delta) if (tz_oper == '+') else (date - tz_delta)

    @classmethod
    def wrap(cls, response_or_entry):
        if isinstance(response_or_entry, adpt.Response):
            return [cls(entry) for entry in response_or_entry.feed.entries]
        else:
            return cls(response_or_entry)

    @property
    def id(self):
        return self.entry.uuid

    @property
    def published(self):
        return self.entry.properties.get(_PUBLISHED)

    @property
    def published_datetime(self):
        return self._str_to_datetime(self.published)

    @property
    def title(self):
        return self.entry.properties.get(_TITLE)

    @property
    def updated(self):
        return self.entry.properties.get(_UPDATED)

    @property
    def updated_datetime(self):
        return self._str_to_datetime(self.updated)

    @property
    def category(self):
        return self.entry.properties.get(_CATEGORY)

    @property
    def link(self):
        return self.entry.links[None][0]


class LTMMetrics(MonitorMetrics):
    """A pseudo wrapper for Long Term Monitor metrics.

    The standard pattern of wrapping a response or entry and accessing
    properties for the data can be used, even though this isn't a traditional
    EntryWrapper.
    """
    pass


class STMMetrics(MonitorMetrics):
    """A pseudo wrapper for Short Term Monitor metrics.

    The standard pattern of wrapping a response or entry and accessing
    properties for the data can be used, even though this isn't a traditional
    EntryWrapper.
    """
    pass
