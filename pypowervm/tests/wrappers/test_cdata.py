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

import unittest

import pypowervm.tests.test_utils.test_wrapper_abc as twrap
import pypowervm.wrappers.job as jwrap

CORRECT_CDATA_PARAMVAL = (
    '<ParameterValue xmlns="http://www.ibm.com/xmlns/systems/power/firmware/'
    'web/mc/2012_10/" xmlns:JobResponse="http://www.ibm.com/xmlns/systems/'
    'power/firmware/web/mc/2012_10/" xmlns:ns2="http://www.w3.org/XML/1998/'
    'namespace/k2" xmlns:ns3="http://www.w3.org/1999/xhtml" kb="CUR" '
    'kxe="false"><![CDATA[<XML_LIST><general><version>1</version></general>'
    '<reliableITL>true</reliableITL><deviceList><device><vendor>IBM</vendor>'
    '<deviceID>6005076802810B0FD00000000000049F042145</deviceID><itlList>'
    '<itl><Iwwpn>21000024FF409CD0</Iwwpn><Twwpn>500507680245CAC0</Twwpn><Lua>'
    '6000000000000</Lua></itl></itlList></device></deviceList></XML_LIST>]]>'
    '</ParameterValue>'
    "\n\n            ").encode("utf-8")

CORRECT_CDATA_CONTENT = (
    '<XML_LIST><general><version>1</version></general><reliableITL>true'
    '</reliableITL><deviceList><device><vendor>IBM</vendor><deviceID>'
    '6005076802810B0FD00000000000049F042145</deviceID><itlList><itl><Iwwpn>'
    '21000024FF409CD0</Iwwpn><Twwpn>500507680245CAC0</Twwpn><Lua>'
    '6000000000000</Lua></itl></itlList></device></deviceList></XML_LIST>')


class TestCDATA(twrap.TestWrapper):

    file = 'cdata.xml'
    wrapper_class_to_test = jwrap.Job

    """Verify CDATA segments survive going into and out of the Adapter."""
    def test_cdata_request(self):
        pval = self.dwrap.entry.element.find(
            'JobRequestInstance/JobParameters/JobParameter/ParameterValue')
        out = pval.toxmlstring()
        self.assertEqual(out, CORRECT_CDATA_PARAMVAL,
                         "CDATA was not preserved in JobRequest!\n%s" % out)

    def test_cdata_results(self):
        resdict = self.dwrap.get_job_results_as_dict()
        out = resdict['inputXML']
        self.assertEqual(out, CORRECT_CDATA_CONTENT,
                         "CDATA was not preserved in Results!\n%s" % out)

if __name__ == '__main__':
    unittest.main()
