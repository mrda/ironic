# coding=utf-8
#
# Copyright 2014 Hewlett-Packard Development Company, L.P.
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

import datetime
import time

from ironicclient import client as ironic_client
from ironicclient import exc as ironic_exception

from nova import exception
from nova.openstack.common.gettextutils import _
from nova.openstack.common import log as logging
from nova.openstack.common import timeutils
from oslo.config import cfg

LOG = logging.getLogger(__name__)
CONF = cfg.CONF


class IronicClientWrapper(object):
    """Ironic client wrapper class that encapsulates retry logic."""

    # Note(mrda): Before using this cached client, you should check the
    # expiry time in the token.
    _cli = None

    def _is_token_valid(self, token):
        """Check the supplied token's expiry date.

        If the supplied token's expiry date is more than 30 seconds in the future
        then it's deemed to be valid.

        :param token: The token to check

        :returns: True of the token is valid, False otherwise
        """
        if 'expires' in token:
            tz_expiry = timeutils.parse_isotime(token['expires'])
            expiry = timeutils.normalize_time(tz_expiry)
            return (expiry > (timeutils.utcnow() + datetime.timedelta(seconds=30)))
        else:
            return False

    def _get_client(self):
        auth_token = CONF.ironic.admin_auth_token
        if auth_token is None:
            kwargs = {'os_username': CONF.ironic.admin_username,
                      'os_password': CONF.ironic.admin_password,
                      'os_auth_url': CONF.ironic.admin_url,
                      'os_tenant_name': CONF.ironic.admin_tenant_name,
                      'os_service_type': 'baremetal',
                      'os_endpoint_type': 'public'}
        else:
            kwargs = {'os_auth_token': auth_token,
                      'ironic_url': CONF.ironic.api_endpoint}

        get_token = True

        # Check to see if the token is still valid
        if IronicClientWrapper._cli is not None:
            if 'token' in IronicClientWrapper._cli:
                if self._is_token_valid(IronicClientWrapper._cli['token']):
                    LOG.debug("Using existing authentication token")
                    get_token = False

        if get_token:
            LOG.debug("Requesting new authentication token")
            try:
                IronicClientWrapper._cli = ironic_client.get_client(
                    CONF.ironic.api_version, **kwargs)
            except ironic_exception.Unauthorized:
                msg = (_("Unable to authenticate Ironic client."))
                LOG.error(msg)
                raise exception.NovaException(msg)

        return IronicClientWrapper._cli

    def _multi_getattr(self, obj, attr):
        """Support nested attribute path for getattr().

        :param obj: Root object.
        :param attr: Path of final attribute to get. E.g., "a.b.c.d"

        :returns: The value of the final named attribute.
        :raises: AttributeError will be raised if the path is invalid.
        """
        for attribute in attr.split("."):
            obj = getattr(obj, attribute)
        return obj

    def call(self, method, *args, **kwargs):
        """Call an Ironic client method and retry on errors.

        :param method: Name of the client method to call as a string.
        :param args: Client method arguments.
        :param kwargs: Client method keyword arguments.

        :raises: NovaException if all retries failed.
        """
        retry_excs = (ironic_exception.ServiceUnavailable,
                      ironic_exception.ConnectionRefused,
                      ironic_exception.Conflict)
        num_attempts = CONF.ironic.api_max_retries

        for attempt in range(1, num_attempts + 1):
            client = self._get_client()
            try:
                return self._multi_getattr(client, method)(*args, **kwargs)
            except retry_excs:
                msg = (_("Error contacting Ironic server for '%(method)s'. "
                         "Attempt %(attempt)d of %(total)d")
                       % {'method': method,
                          'attempt': attempt,
                          'total': num_attempts})
                if attempt == num_attempts:
                    LOG.error(msg)
                    raise exception.NovaException(msg)
                LOG.warning(msg)
                time.sleep(CONF.ironic.api_retry_interval)
