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

# TODO(efried): Remove these (unused)


def msg_in_pvm_err(pvmerr, msg):
    """Check whether the Error contains the specified msg.

    :param pvmerr: pypowervm.exceptions.Error
    :param msg: error message
    :return Boolean indicating whether the Error contains the message
    """
    if hasattr(pvmerr, 'response'):
        err_resp = pvmerr.response
        if (err_resp is not None and err_resp.body is not None
                and msg in str(err_resp.body)):
            return True
    return False


def msgs_in_pvm_err(pvmerr, msgs):
    """Check whether the Error contains the one of the messages.

    :param pvmerr: pypowervm.exceptions.Error
    :param msgs: error messages
    :return Boolean indicating whether the Error contains the message
    """
    if hasattr(pvmerr, 'response'):
        err_resp = pvmerr.response
        if (err_resp is not None and err_resp.body is not None
                and any(msg in str(err_resp.body)
                        for msg in msgs)):
            return True
    return False
