# Copyright 2014 Red Hat, Inc.
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
import mock
import time

from oslo.config import cfg

from ironic.nova.tests.virt.ironic import utils as ironic_utils
from ironic.nova.virt.ironic import client_wrapper
from ironicclient import client as ironic_client

from nova.openstack.common import timeutils

from nova import test

CONF = cfg.CONF

FAKE_CLIENT = ironic_utils.FakeClient()


class IronicClientWrapperTestCase(test.NoDBTestCase):

    def setUp(self):
        super(IronicClientWrapperTestCase, self).setUp()
        self.icli = client_wrapper.IronicClientWrapper()
        # make sure the client's not cached
        client_wrapper.IronicClientWrapper._cli = None
        self.future_date = timeutils.strtime(
            timeutils.utcnow() + datetime.timedelta(days=5))

    @mock.patch.object(client_wrapper.IronicClientWrapper, '_multi_getattr')
    @mock.patch.object(client_wrapper.IronicClientWrapper, '_get_client')
    def test_call_good_no_args(self, mock_get_client, mock_multi_getattr):
        mock_get_client.return_value = FAKE_CLIENT
        self.icli.call("node.list")
        mock_get_client.assert_called_once_with()
        mock_multi_getattr.assert_called_once_with(FAKE_CLIENT, "node.list")
        mock_multi_getattr.return_value.assert_called_once_with()

    @mock.patch.object(client_wrapper.IronicClientWrapper, '_multi_getattr')
    @mock.patch.object(client_wrapper.IronicClientWrapper, '_get_client')
    def test_call_good_with_args(self, mock_get_client, mock_multi_getattr):
        mock_get_client.return_value = FAKE_CLIENT
        self.icli.call("node.list", 'test', associated=True)
        mock_get_client.assert_called_once_with()
        mock_multi_getattr.assert_called_once_with(FAKE_CLIENT, "node.list")
        mock_multi_getattr.return_value.assert_called_once_with('test',
                                                               associated=True)

    @mock.patch.object(ironic_client, 'get_client')
    def test__get_client_no_auth_token(self, mock_ir_cli):
        self.flags(admin_auth_token=None, group='ironic')
        # dummy call to have _get_client() called
        self.icli.call("node.list")
        expected = {'os_username': CONF.ironic.admin_username,
                    'os_password': CONF.ironic.admin_password,
                    'os_auth_url': CONF.ironic.admin_url,
                    'os_tenant_name': CONF.ironic.admin_tenant_name,
                    'os_service_type': 'baremetal',
                    'os_endpoint_type': 'public'}
        mock_ir_cli.assert_called_once_with(CONF.ironic.api_version,
                                            **expected)

    @mock.patch.object(ironic_client, 'get_client')
    def test__get_client_with_auth_token(self, mock_ir_cli):
        self.flags(admin_auth_token='fake-token', group='ironic')
        # dummy call to have _get_client() called
        self.icli.call("node.list")
        expected = {'os_auth_token': 'fake-token',
                    'ironic_url': CONF.ironic.api_endpoint}
        mock_ir_cli.assert_called_once_with(CONF.ironic.api_version,
                                            **expected)

    @mock.patch.object(client_wrapper.IronicClientWrapper,
                       '_multi_getattr')
    @mock.patch.object(ironic_client, 'get_client')
    def test__get_client_token_cached(self, mock_get_client,
                                      mock_multi_getattr):
        self.flags(admin_auth_token=None, group='ironic')
        mock_get_client.return_value = {
            'token': {'expires': self.future_date,
                      'id': 'd1a54131174b262ac87ce82870742235'}
        }
        self.assertEquals(0, mock_get_client.call_count)
        # dummy call to have _get_client() called
        self.icli.call("node.list")
        self.assertEquals(1, mock_get_client.call_count)
        # call again, but now verify that the cached token is used
        self.icli.call("node.list")
        self.assertEquals(1, mock_get_client.call_count)
        # and again, just to make sure
        self.icli.call("node.list")
        self.assertEquals(1, mock_get_client.call_count)

    @mock.patch.object(client_wrapper.IronicClientWrapper,
                       '_multi_getattr')
    @mock.patch.object(ironic_client, 'get_client')
    def test__get_client_token_expires(self, mock_get_client,
                                         mock_multi_getattr):
        self.flags(admin_auth_token=None, group='ironic')
        mock_get_client.return_value = {
            'token': {'expires': self.future_date,
                      'id': 'd1a54131174b262ac87ce82870742235'}
        }
        self.assertEquals(0, mock_get_client.call_count)
        # dummy call to have _get_client() called
        self.icli.call("node.list")
        self.assertEquals(1, mock_get_client.call_count)
        # call again, but now verify that the cached token is used
        self.icli.call("node.list")
        self.assertEquals(1, mock_get_client.call_count)
        # now change the expiry on the token to right now
        mock_get_client.return_value['token']['expires'] = \
            timeutils.strtime()
        self.icli.call("node.list")
        self.assertEquals(2, mock_get_client.call_count)
