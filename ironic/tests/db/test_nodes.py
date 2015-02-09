# Copyright 2013 Hewlett-Packard Development Company, L.P.
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

"""Tests for manipulating Nodes via the DB API"""

import datetime

import mock
from oslo.utils import timeutils
import six

from ironic.common import exception
from ironic.common import states
from ironic.common import utils as ironic_utils
from ironic.tests.db import base
from ironic.tests.db import utils


class DbNodeTestCase(base.DbTestCase):

    def test_create_node(self):
        utils.create_test_node()

    def test_create_node_nullable_chassis_id(self):
        utils.create_test_node(chassis_id=None)

    def test_create_node_already_exists(self):
        utils.create_test_node()
        self.assertRaises(exception.NodeAlreadyExists,
                          utils.create_test_node)

    def test_create_node_instance_already_associated(self):
        instance = ironic_utils.generate_uuid()
        utils.create_test_node(uuid=ironic_utils.generate_uuid(),
                               instance_uuid=instance)
        self.assertRaises(exception.InstanceAssociated,
                          utils.create_test_node,
                          uuid=ironic_utils.generate_uuid(),
                          instance_uuid=instance)

    def test_create_node_name_duplicate(self):
        node = utils.create_test_node(name='spam')
        self.assertRaises(exception.DuplicateName,
                          utils.create_test_node,
                          name=node.name)

    def test_get_node_by_id(self):
        node = utils.create_test_node()
        res = self.dbapi.get_node_by_id(node.id)
        self.assertEqual(node.id, res.id)
        self.assertEqual(node.uuid, res.uuid)

    def test_get_node_by_uuid(self):
        node = utils.create_test_node()
        res = self.dbapi.get_node_by_uuid(node.uuid)
        self.assertEqual(node.id, res.id)
        self.assertEqual(node.uuid, res.uuid)

    def test_get_node_by_name(self):
        node = utils.create_test_node()
        res = self.dbapi.get_node_by_name(node.name)
        self.assertEqual(node.id, res.id)
        self.assertEqual(node.uuid, res.uuid)
        self.assertEqual(node.name, res.name)

    def test_get_node_that_does_not_exist(self):
        self.assertRaises(exception.NodeNotFound,
                          self.dbapi.get_node_by_id, 99)
        self.assertRaises(exception.NodeNotFound,
                          self.dbapi.get_node_by_uuid,
                          '12345678-9999-0000-aaaa-123456789012')
        self.assertRaises(exception.NodeNotFound,
                          self.dbapi.get_node_by_name,
                          'spam-eggs-bacon-spam')

    def test_get_nodeinfo_list_defaults(self):
        node_id_list = []
        for i in range(1, 6):
            node = utils.create_test_node(uuid=ironic_utils.generate_uuid())
            node_id_list.append(node.id)
        res = [i[0] for i in self.dbapi.get_nodeinfo_list()]
        self.assertEqual(sorted(res), sorted(node_id_list))

    def test_get_nodeinfo_list_with_cols(self):
        uuids = {}
        extras = {}
        for i in range(1, 6):
            uuid = ironic_utils.generate_uuid()
            extra = {'foo': i}
            node = utils.create_test_node(extra=extra, uuid=uuid)
            uuids[node.id] = uuid
            extras[node.id] = extra
        res = self.dbapi.get_nodeinfo_list(columns=['id', 'extra', 'uuid'])
        self.assertEqual(extras, dict((r[0], r[1]) for r in res))
        self.assertEqual(uuids, dict((r[0], r[2]) for r in res))

    def test_get_nodeinfo_list_with_filters(self):
        node1 = utils.create_test_node(driver='driver-one',
            instance_uuid=ironic_utils.generate_uuid(),
            reservation='fake-host',
            uuid=ironic_utils.generate_uuid())
        node2 = utils.create_test_node(driver='driver-two',
            uuid=ironic_utils.generate_uuid(),
            maintenance=True)

        res = self.dbapi.get_nodeinfo_list(filters={'driver': 'driver-one'})
        self.assertEqual([node1.id], [r[0] for r in res])

        res = self.dbapi.get_nodeinfo_list(filters={'driver': 'bad-driver'})
        self.assertEqual([], [r[0] for r in res])

        res = self.dbapi.get_nodeinfo_list(filters={'associated': True})
        self.assertEqual([node1.id], [r[0] for r in res])

        res = self.dbapi.get_nodeinfo_list(filters={'associated': False})
        self.assertEqual([node2.id], [r[0] for r in res])

        res = self.dbapi.get_nodeinfo_list(filters={'reserved': True})
        self.assertEqual([node1.id], [r[0] for r in res])

        res = self.dbapi.get_nodeinfo_list(filters={'reserved': False})
        self.assertEqual([node2.id], [r[0] for r in res])

        res = self.dbapi.get_node_list(filters={'maintenance': True})
        self.assertEqual([node2.id], [r.id for r in res])

        res = self.dbapi.get_node_list(filters={'maintenance': False})
        self.assertEqual([node1.id], [r.id for r in res])

    @mock.patch.object(timeutils, 'utcnow')
    def test_get_nodeinfo_list_provision(self, mock_utcnow):
        past = datetime.datetime(2000, 1, 1, 0, 0)
        next = past + datetime.timedelta(minutes=8)
        present = past + datetime.timedelta(minutes=10)
        mock_utcnow.return_value = past

        # node with provision_updated timeout
        node1 = utils.create_test_node(uuid=ironic_utils.generate_uuid(),
                                       provision_updated_at=past)
        # node with None in provision_updated_at
        node2 = utils.create_test_node(uuid=ironic_utils.generate_uuid(),
                                       provision_state=states.DEPLOYWAIT)
        # node without timeout
        utils.create_test_node(uuid=ironic_utils.generate_uuid(),
                            provision_updated_at=next)

        mock_utcnow.return_value = present
        res = self.dbapi.get_nodeinfo_list(filters={'provisioned_before': 300})
        self.assertEqual([node1.id], [r[0] for r in res])

        res = self.dbapi.get_nodeinfo_list(filters={'provision_state':
                                                    states.DEPLOYWAIT})
        self.assertEqual([node2.id], [r[0] for r in res])

    def test_get_node_list(self):
        uuids = []
        for i in range(1, 6):
            node = utils.create_test_node(uuid=ironic_utils.generate_uuid())
            uuids.append(six.text_type(node['uuid']))
        res = self.dbapi.get_node_list()
        res_uuids = [r.uuid for r in res]
        self.assertEqual(uuids.sort(), res_uuids.sort())

    def test_get_node_list_with_filters(self):
        ch1 = utils.get_test_chassis(id=1, uuid=ironic_utils.generate_uuid())
        ch2 = utils.get_test_chassis(id=2, uuid=ironic_utils.generate_uuid())
        self.dbapi.create_chassis(ch1)
        self.dbapi.create_chassis(ch2)

        node1 = utils.create_test_node(driver='driver-one',
            instance_uuid=ironic_utils.generate_uuid(),
            reservation='fake-host',
            uuid=ironic_utils.generate_uuid(),
            chassis_id=ch1['id'])
        node2 = utils.create_test_node(driver='driver-two',
            uuid=ironic_utils.generate_uuid(),
            chassis_id=ch2['id'],
            maintenance=True)

        res = self.dbapi.get_node_list(filters={'chassis_uuid': ch1['uuid']})
        self.assertEqual([node1.id], [r.id for r in res])

        res = self.dbapi.get_node_list(filters={'chassis_uuid': ch2['uuid']})
        self.assertEqual([node2.id], [r.id for r in res])

        res = self.dbapi.get_node_list(filters={'driver': 'driver-one'})
        self.assertEqual([node1.id], [r.id for r in res])

        res = self.dbapi.get_node_list(filters={'driver': 'bad-driver'})
        self.assertEqual([], [r.id for r in res])

        res = self.dbapi.get_node_list(filters={'associated': True})
        self.assertEqual([node1.id], [r.id for r in res])

        res = self.dbapi.get_node_list(filters={'associated': False})
        self.assertEqual([node2.id], [r.id for r in res])

        res = self.dbapi.get_node_list(filters={'reserved': True})
        self.assertEqual([node1.id], [r.id for r in res])

        res = self.dbapi.get_node_list(filters={'reserved': False})
        self.assertEqual([node2.id], [r.id for r in res])

        res = self.dbapi.get_node_list(filters={'maintenance': True})
        self.assertEqual([node2.id], [r.id for r in res])

        res = self.dbapi.get_node_list(filters={'maintenance': False})
        self.assertEqual([node1.id], [r.id for r in res])

    def test_get_node_list_chassis_not_found(self):
        self.assertRaises(exception.ChassisNotFound,
                          self.dbapi.get_node_list,
                          {'chassis_uuid': ironic_utils.generate_uuid()})

    def test_get_node_by_instance(self):
        node = utils.create_test_node(
                instance_uuid='12345678-9999-0000-aaaa-123456789012')

        res = self.dbapi.get_node_by_instance(node.instance_uuid)
        self.assertEqual(node.uuid, res.uuid)

    def test_get_node_by_instance_wrong_uuid(self):
        utils.create_test_node(
                instance_uuid='12345678-9999-0000-aaaa-123456789012')

        self.assertRaises(exception.InstanceNotFound,
                          self.dbapi.get_node_by_instance,
                          '12345678-9999-0000-bbbb-123456789012')

    def test_get_node_by_instance_invalid_uuid(self):
        self.assertRaises(exception.InvalidUUID,
                          self.dbapi.get_node_by_instance,
                          'fake_uuid')

    def test_destroy_node(self):
        node = utils.create_test_node()

        self.dbapi.destroy_node(node.id)
        self.assertRaises(exception.NodeNotFound,
                          self.dbapi.get_node_by_id, node.id)

    def test_destroy_node_by_uuid(self):
        node = utils.create_test_node()

        self.dbapi.destroy_node(node.uuid)
        self.assertRaises(exception.NodeNotFound,
                          self.dbapi.get_node_by_uuid, node.uuid)

    def test_destroy_node_that_does_not_exist(self):
        self.assertRaises(exception.NodeNotFound,
                          self.dbapi.destroy_node,
                          '12345678-9999-0000-aaaa-123456789012')

    def test_ports_get_destroyed_after_destroying_a_node(self):
        node = utils.create_test_node()

        port = utils.create_test_port(node_id=node.id)

        self.dbapi.destroy_node(node.id)

        self.assertRaises(exception.PortNotFound,
                          self.dbapi.get_port_by_id, port.id)

    def test_ports_get_destroyed_after_destroying_a_node_by_uuid(self):
        node = utils.create_test_node()

        port = utils.create_test_port(node_id=node.id)

        self.dbapi.destroy_node(node.uuid)

        self.assertRaises(exception.PortNotFound,
                          self.dbapi.get_port_by_id, port.id)

    def test_update_node(self):
        node = utils.create_test_node()

        old_extra = node.extra
        new_extra = {'foo': 'bar'}
        self.assertNotEqual(old_extra, new_extra)

        res = self.dbapi.update_node(node.id, {'extra': new_extra})
        self.assertEqual(new_extra, res.extra)

    def test_update_node_not_found(self):
        node_uuid = ironic_utils.generate_uuid()
        new_extra = {'foo': 'bar'}
        self.assertRaises(exception.NodeNotFound, self.dbapi.update_node,
                          node_uuid, {'extra': new_extra})

    def test_update_node_uuid(self):
        node = utils.create_test_node()
        self.assertRaises(exception.InvalidParameterValue,
                          self.dbapi.update_node, node.id,
                          {'uuid': ''})

    def test_update_node_associate_and_disassociate(self):
        node = utils.create_test_node()
        new_i_uuid = ironic_utils.generate_uuid()
        res = self.dbapi.update_node(node.id, {'instance_uuid': new_i_uuid})
        self.assertEqual(new_i_uuid, res.instance_uuid)
        res = self.dbapi.update_node(node.id, {'instance_uuid': None})
        self.assertIsNone(res.instance_uuid)

    def test_update_node_already_associated(self):
        node = utils.create_test_node()
        new_i_uuid_one = ironic_utils.generate_uuid()
        self.dbapi.update_node(node.id, {'instance_uuid': new_i_uuid_one})
        new_i_uuid_two = ironic_utils.generate_uuid()
        self.assertRaises(exception.NodeAssociated,
                          self.dbapi.update_node,
                          node.id,
                          {'instance_uuid': new_i_uuid_two})

    def test_update_node_instance_already_associated(self):
        node1 = utils.create_test_node(uuid=ironic_utils.generate_uuid())
        new_i_uuid = ironic_utils.generate_uuid()
        self.dbapi.update_node(node1.id, {'instance_uuid': new_i_uuid})
        node2 = utils.create_test_node(uuid=ironic_utils.generate_uuid())
        self.assertRaises(exception.InstanceAssociated,
                          self.dbapi.update_node,
                          node2.id,
                          {'instance_uuid': new_i_uuid})

    @mock.patch.object(timeutils, 'utcnow')
    def test_update_node_provision(self, mock_utcnow):
        mocked_time = datetime.datetime(2000, 1, 1, 0, 0)
        mock_utcnow.return_value = mocked_time
        node = utils.create_test_node()
        res = self.dbapi.update_node(node.id, {'provision_state': 'fake'})
        self.assertEqual(mocked_time,
                         timeutils.normalize_time(res['provision_updated_at']))

    def test_update_node_name_duplicate(self):
        node1 = utils.create_test_node(uuid=ironic_utils.generate_uuid(),
                                       name='spam')
        node2 = utils.create_test_node(uuid=ironic_utils.generate_uuid())
        self.assertRaises(exception.DuplicateName,
                          self.dbapi.update_node,
                          node2.id,
                          {'name': node1.name})

    def test_update_node_no_provision(self):
        node = utils.create_test_node()
        res = self.dbapi.update_node(node.id, {'extra': {'foo': 'bar'}})
        self.assertIsNone(res['provision_updated_at'])

    def test_reserve_node(self):
        node = utils.create_test_node()
        uuid = node.uuid

        r1 = 'fake-reservation'

        # reserve the node
        self.dbapi.reserve_node(r1, uuid)

        # check reservation
        res = self.dbapi.get_node_by_uuid(uuid)
        self.assertEqual(r1, res.reservation)

    def test_release_reservation(self):
        node = utils.create_test_node()
        uuid = node.uuid

        r1 = 'fake-reservation'
        self.dbapi.reserve_node(r1, uuid)

        # release reservation
        self.dbapi.release_node(r1, uuid)
        res = self.dbapi.get_node_by_uuid(uuid)
        self.assertIsNone(res.reservation)

    def test_reservation_of_reserved_node_fails(self):
        node = utils.create_test_node()
        uuid = node.uuid

        r1 = 'fake-reservation'
        r2 = 'another-reservation'

        # reserve the node
        self.dbapi.reserve_node(r1, uuid)

        # another host fails to reserve or release
        self.assertRaises(exception.NodeLocked,
                          self.dbapi.reserve_node,
                          r2, uuid)
        self.assertRaises(exception.NodeLocked,
                          self.dbapi.release_node,
                          r2, uuid)

    def test_reservation_after_release(self):
        node = utils.create_test_node()
        uuid = node.uuid

        r1 = 'fake-reservation'
        r2 = 'another-reservation'

        self.dbapi.reserve_node(r1, uuid)
        self.dbapi.release_node(r1, uuid)

        # another host succeeds
        self.dbapi.reserve_node(r2, uuid)
        res = self.dbapi.get_node_by_uuid(uuid)
        self.assertEqual(r2, res.reservation)

    def test_reservation_in_exception_message(self):
        node = utils.create_test_node()
        uuid = node.uuid

        r = 'fake-reservation'
        self.dbapi.reserve_node(r, uuid)
        try:
            self.dbapi.reserve_node('another', uuid)
        except exception.NodeLocked as e:
            self.assertIn(r, str(e))

    def test_reservation_non_existent_node(self):
        node = utils.create_test_node()
        self.dbapi.destroy_node(node.id)

        self.assertRaises(exception.NodeNotFound,
                          self.dbapi.reserve_node, 'fake', node.id)
        self.assertRaises(exception.NodeNotFound,
                          self.dbapi.reserve_node, 'fake', node.uuid)

    def test_release_non_existent_node(self):
        node = utils.create_test_node()
        self.dbapi.destroy_node(node.id)

        self.assertRaises(exception.NodeNotFound,
                          self.dbapi.release_node, 'fake', node.id)
        self.assertRaises(exception.NodeNotFound,
                          self.dbapi.release_node, 'fake', node.uuid)

    def test_release_non_locked_node(self):
        node = utils.create_test_node()

        self.assertEqual(None, node.reservation)
        self.assertRaises(exception.NodeNotLocked,
                          self.dbapi.release_node, 'fake', node.id)
        self.assertRaises(exception.NodeNotLocked,
                          self.dbapi.release_node, 'fake', node.uuid)
