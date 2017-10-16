# Copyright 2014, 2017 IBM Corp.
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

from oslo_log import log as logging
from pypowervm.tasks.monitor import util as pcm_util


LOG = logging.getLogger(__name__)


class HostCPUMetricCache(pcm_util.MetricCache):
    """Collects the PowerVM CPU metrics.

    PowerVM only gathers the CPU statistics once every 30 seconds.  It does
    this to reduce overhead.  There is a function to gather statistics quicker,
    but that can be very expensive.  Therefore, to ensure that the client's
    workload is not impacted, these 'longer term' metrics will be used.

    This class builds off of a base pypowervm function where it can obtain
    the samples through a PCM 'cache'.  If a new sample is available, the cache
    pulls the sample.  If it is not, the existing sample is used.

    This can result in multiple, quickly successive calls to the host stats
    returning the same data (because a new sample may not be available yet).

    The class analyzes the data and keeps running counts of total, user, and
    firmware cycles.
    """

    def __init__(self, adapter, host_uuid):
        """Creates an instance of the HostCPUMetricCache.

        :param adapter: The pypowervm Adapter.
        :param host_uuid: The UUID of the host CEC to maintain a metrics
                          cache for.
        """
        # Running counts for total, firmware, and user cycles
        self.total_cycles = 0
        self.total_fw_cycles = 0
        self.total_user_cycles = 0
        self.cpu_freq = self._get_cpu_freq()

        # Invoke the parent to seed the metrics.  Don't include VIO - will
        # result in quicker calls.
        super(HostCPUMetricCache, self).__init__(adapter, host_uuid,
                                                 include_vio=False)

    def refresh(self):
        """Updates the host-level CPU metrics if needed."""
        self._refresh_if_needed()

    def _update_internal_metric(self):
        """Updates cycle totals using the latest stats from the cache.

        This method is invoked by the parent class after the raw metrics are
        updated.
        """

        # If there is no 'new' data (perhaps sampling is not turned on) then
        # return no data.
        if self.cur_phyp is None:
            return

        # Compute the cycles spent in FW since last collection.
        fw_cycles_delta = self._get_fw_cycles_delta()

        # Compute the cycles the system spent since last run.
        tot_cycles_delta = self._get_total_cycles_delta()

        # Get the user cycles since last run
        user_cycles_delta = self._gather_user_cycles_delta()

        # Make sure that the total cycles is higher than the user/fw cycles.
        # Should not happen, but just in case there is any precision loss from
        # CPU data back to system.
        if user_cycles_delta + fw_cycles_delta > tot_cycles_delta:
            LOG.warning(
                "Host CPU Metrics determined that the total cycles reported "
                "was less than the used cycles.  This indicates an issue with "
                "the PCM data.  Please investigate the results.\n"
                "Total Delta Cycles: %(tot_cycles)d\n"
                "User Delta Cycles: %(user_cycles)d\n"
                "Firmware Delta Cycles: %(fw_cycles)d",
                {'tot_cycles': tot_cycles_delta, 'fw_cycles': fw_cycles_delta,
                 'user_cycles': user_cycles_delta})
            tot_cycles_delta = user_cycles_delta + fw_cycles_delta

        self.total_cycles += tot_cycles_delta
        self.total_user_cycles += user_cycles_delta
        self.total_fw_cycles += fw_cycles_delta

    def _gather_user_cycles_delta(self):
        """The estimated user cycles of all VMs/VIOSes since last run.

        The sample data includes information about how much CPU has been used
        by workloads and the Virtual I/O Servers.  There is not one global
        counter that can be used to obtain the CPU spent cycles.

        This method will calculate the delta of workload (and I/O Server)
        cycles between the previous sample and the current sample.

        There are edge cases for this however.  If a VM is deleted or migrated
        its cycles will no longer be taken into account.  The algorithm takes
        this into account by building on top of the previous sample's user
        cycles.

        :return: Estimated cycles spent on workload (including VMs and Virtual
                 I/O Server).  This represents the entire server's current
                 'user' load.
        """
        # Current samples should be guaranteed to be there.
        vm_cur_samples = self.cur_phyp.sample.lpars
        vios_cur_samples = self.cur_phyp.sample.vioses

        # The previous samples may not have been there.
        vm_prev_samples, vios_prev_samples = None, None
        if self.prev_phyp is not None:
            vm_prev_samples = self.prev_phyp.sample.lpars
            vios_prev_samples = self.prev_phyp.sample.vioses

        # Gather the delta cycles between the previous and current data sets
        vm_delta_cycles = self._delta_proc_cycles(vm_cur_samples,
                                                  vm_prev_samples)
        vios_delta_cycles = self._delta_proc_cycles(vios_cur_samples,
                                                    vios_prev_samples)

        return vm_delta_cycles + vios_delta_cycles

    @staticmethod
    def _get_cpu_freq():
        # The output will be similar to '4116.000000MHz' on a POWER system.
        with open('/proc/cpuinfo') as cpuinfo:
            for line in cpuinfo:
                if line.startswith('clock'):
                    return int(float(line.split()[-1].rstrip('MHz')))

    def _delta_proc_cycles(self, samples, prev_samples):
        """Sums all the processor delta cycles for a set of VM/VIOS samples.

        This sum is the difference from the last sample to the current sample.

        :param samples: A set of PhypVMSample or PhypViosSample samples.
        :param prev_samples: The set of the previous samples.  May be None.
        :return: The cycles spent on workload across all of the samples.
        """
        # Determine the user cycles spent between the last sample and the
        # current.
        user_cycles = 0
        for lpar_sample in samples:
            prev_sample = self._find_prev_sample(lpar_sample, prev_samples)
            user_cycles += self._delta_user_cycles(lpar_sample, prev_sample)
        return user_cycles

    @staticmethod
    def _delta_user_cycles(cur_sample, prev_sample):
        """Determines the delta of user cycles from the cur and prev sample.

        :param cur_sample: The current sample.
        :param prev_sample: The previous sample.  May be None.
        :return: The difference in cycles between the two samples.  If the data
                 only exists in the current sample (indicates a new workload),
                 then all of the cycles from the current sample will be
                 considered the delta.
        """
        # If the previous sample for this VM is None it could be one of two
        # conditions.  It could be a new spawn or a live migration.  The cycles
        # from a live migrate are brought over from the previous host.  That
        # can disorient the calculation because all of a sudden you could get
        # months of cycles.  Since we can not discern between the two
        # scenarios, we return 0 (effectively throwing the sample out).
        # The next pass through will have the previous sample and will be
        # included.
        if prev_sample is None:
            return 0
        # If the previous sample values are all 0 (happens when VM is just
        # migrated, phyp creates entry for VM with 0 values), then ignore the
        # sample.
        if (prev_sample.processor.util_cap_proc_cycles ==
                prev_sample.processor.util_uncap_proc_cycles ==
                prev_sample.processor.idle_proc_cycles == 0):
            return 0
        # The VM utilization on host is its capped + uncapped - idle cycles.
        # Donated proc cycles should not be considered as these are
        # not guaranteed to be getting utilized by any other lpar on the host.
        prev_amount = (prev_sample.processor.util_cap_proc_cycles +
                       prev_sample.processor.util_uncap_proc_cycles -
                       prev_sample.processor.idle_proc_cycles)
        cur_amount = (cur_sample.processor.util_cap_proc_cycles +
                      cur_sample.processor.util_uncap_proc_cycles -
                      cur_sample.processor.idle_proc_cycles)
        return cur_amount - prev_amount

    @staticmethod
    def _find_prev_sample(sample, prev_samples):
        """Finds the previous VM Sample for a given current sample.

        :param sample: The current sample.
        :param prev_samples: The previous samples to search through.
        :return: The previous sample, if it exists.  None otherwise.
        """
        # Will occur if there are no previous samples.
        if prev_samples is None:
            return None
        for prev_sample in prev_samples:
            if prev_sample.id == sample.id and prev_sample.name == sample.name:
                return prev_sample
        return None

    def _get_total_cycles_delta(self):
        """Returns the 'total cycles' on the system since last sample.

        :return: The total delta cycles since the last run.
        """
        sample = self.cur_phyp.sample
        cur_cores = sample.processor.configurable_proc_units
        cur_cycles_per_core = sample.time_based_cycles

        if self.prev_phyp:
            prev_cycles_per_core = self.prev_phyp.sample.time_based_cycles
        else:
            prev_cycles_per_core = 0

        # Get the delta cycles between the cores.
        delta_cycles_per_core = cur_cycles_per_core - prev_cycles_per_core

        # Total cycles since last sample is the 'per cpu' cycles spent
        # times the number of active cores.
        return delta_cycles_per_core * cur_cores

    def _get_fw_cycles_delta(self):
        """Returns the number of cycles spent on firmware since last sample."""
        cur_fw = self.cur_phyp.sample.system_firmware.utilized_proc_cycles
        prev_fw = (self.prev_phyp.sample.system_firmware.utilized_proc_cycles
                   if self.prev_phyp else 0)
        return cur_fw - prev_fw
