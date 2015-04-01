#
# Copyright 2015 Rackspace, Inc
# All Rights Reserved
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
import wsmeext.pecan as wsme_pecan

_orig_wsexpose_decorator = wsme_pecan.wsexpose


def _ironic_wsexpose(*args, **kwargs):
    """Ensure that only JSON, and not XML, is supported."""
    kwargs['rest_content_types'] = "('json',)"
    return _orig_wsexpose_decorator(*args, **kwargs)


def patch_wsexpose():
    """Patch the @wsexpose decorator for Ironic."""
    wsme_pecan.wsexpose = _ironic_wsexpose
