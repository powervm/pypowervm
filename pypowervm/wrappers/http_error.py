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

"""HttpError, the EntryWrapper for HttpErrorResponse ('web' namespace)."""

from oslo_log import log as logging

import pypowervm.const as pc
import pypowervm.wrappers.entry_wrapper as ewrap

LOG = logging.getLogger(__name__)

_REASON_CODE = 'ReasonCode'
_MESSAGE = 'Message'
_HTTP_STATUS = 'HTTPStatus'

# Error codes that indicate the VIOS is busy
_VIOS_BUSY_ERR_CODES = ['HSCL3205']


@ewrap.EntryWrapper.pvm_type('HttpErrorResponse', ns=pc.WEB_NS)
class HttpError(ewrap.EntryWrapper):

    @property
    def status(self):
        return self._get_val_int(_HTTP_STATUS)

    @property
    def reason_code(self):
        return self._get_val_str(_REASON_CODE)

    @property
    def message(self):
        return self._get_val_str(_MESSAGE)

    def is_vios_busy(self):
        try:
            msg = self.message
            return (self.status == pc.HTTPStatus.INTERNAL_ERROR and
                    ('VIOS' in msg and
                     'is busy processing some other request' in msg)
                    or any(code in msg for code in _VIOS_BUSY_ERR_CODES))
        except Exception:
            return False
