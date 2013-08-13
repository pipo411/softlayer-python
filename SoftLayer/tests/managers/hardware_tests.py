"""
    SoftLayer.tests.managers.hardware_tests
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    :copyright: (c) 2013, SoftLayer Technologies, Inc. All rights reserved.
    :license: BSD, see LICENSE for more details.
"""
from SoftLayer import HardwareManager
from SoftLayer.managers.hardware import get_default_value
from SoftLayer.tests import unittest

from mock import MagicMock, ANY, call, patch


class HardwareTests(unittest.TestCase):

    def setUp(self):
        self.client = MagicMock()
        self.hardware = HardwareManager(self.client)

    def test_list_hardware(self):
        mcall = call(mask=ANY, filter={})
        service = self.client.__getitem__()

        self.hardware.list_hardware()
        service.getHardware.assert_has_calls(mcall)

    def test_list_hardware_with_filters(self):
        self.hardware.list_hardware(
            tags=['tag1', 'tag2'],
            cpus=2,
            memory=1,
            hostname='hostname',
            domain='example.com',
            datacenter='dal05',
            nic_speed=100,
            public_ip='1.2.3.4',
            private_ip='4.3.2.1',
        )
        service = self.client.__getitem__()
        service.getHardware.assert_has_calls(call(
            filter={
                'hardware': {
                    'datacenter': {'name': {'operation': '_= dal05'}},
                    'domain': {'operation': '_= example.com'},
                    'tagReferences': {
                        'tag': {'name': {
                            'operation': 'in',
                            'options': [
                                {'name': 'data', 'value': ['tag1', 'tag2']}]
                        }}
                    },
                    'memoryCapacity': {'operation': 1},
                    'processorCoreAmount': {'operation': 2},
                    'hostname': {'operation': '_= hostname'},
                    'primaryIpAddress': {'operation': '_= 1.2.3.4'},
                    'networkComponents': {'maxSpeed': {'operation': 100}},
                    'primaryBackendIpAddress': {'operation': '_= 4.3.2.1'}}
            },
            mask=ANY,
        ))

    def test_resolve_ids_ip(self):
        self.client.__getitem__().getHardware.return_value = [{'id': '1234'}]
        _id = self.hardware._get_ids_from_ip('1.2.3.4')
        self.assertEqual(_id, ['1234'])

        self.client.__getitem__().getHardware.side_effect = \
            [[], [{'id': '4321'}]]
        _id = self.hardware._get_ids_from_ip('4.3.2.1')
        self.assertEqual(_id, ['4321'])

        _id = self.hardware._get_ids_from_ip('nope')
        self.assertEqual(_id, [])

    def test_resolve_ids_hostname(self):
        self.client.__getitem__().getHardware.return_value = [{'id': '1234'}]
        _id = self.hardware._get_ids_from_hostname('hostname')
        self.assertEqual(_id, ['1234'])

    def test_get_hardware(self):
        self.client.__getitem__().getObject.return_value = {
            'hourlyVirtualGuests': "this is unique"}
        self.hardware.get_hardware(1)
        self.client.__getitem__().getObject.assert_called_once_with(
            id=1, mask=ANY)

    def test_reload(self):
        post_uri = 'http://test.sftlyr.ws/test.sh'
        self.hardware.reload(id=1, post_uri=post_uri)
        f = self.client.__getitem__().reloadOperatingSystem
        f.assert_called_once_with('FORCE',
                                  {'customProvisionScriptUri': post_uri}, id=1)

    def test_get_bare_metal_create_options_returns_none_on_error(self):
        self.client['Product_Package'].getAllObjects.return_value = [
            {'name': 'No Matching Instances', 'id': 0}]

        self.assertIsNone(self.hardware.get_bare_metal_create_options())

    def test_get_bare_metal_create_options(self):
        package_id = 50

        self._setup_package_mocks(package_id)

        self.hardware.get_bare_metal_create_options()

        f1 = self.client['Product_Package'].getRegions
        f1.assert_called_once_with(id=package_id)

        f2 = self.client['Product_Package'].getConfiguration
        f2.assert_called_once_with(id=package_id,
                                   mask='mask[itemCategory[group]]')

        f3 = self.client['Product_Package'].getCategories
        f3.assert_called_once_with(id=package_id)

    def test_generate_create_dict_with_all_bare_metal_options(self):
        package_id = 50

        self._setup_package_mocks(package_id)

        args = {
            'server': 100,
            'hostname': 'unicorn',
            'domain': 'giggles.woo',
            'disks': [500],
            'location': 'Wyrmshire',
            'os': 200,
            'port_speed': 600,
            'bare_metal': True,
            'hourly': True,
        }

        expected = {
            'hardware': [
                {'domain': 'giggles.woo',
                 'bareMetalInstanceFlag': True,
                 'hostname': 'unicorn'}],
            'prices': [
                {'id': 100},
                {'id': 500},
                {'id': 200},
                {'id': 600},
                {'id': 12000}
            ],
            'hourlyBillingFlag': True,
            'location': 'Wyrmshire', 'packageId': 50
        }

        data = self.hardware._generate_create_dict(**args)

        self.assertEqual(expected, data)

    def test_generate_create_dict_with_all_dedicated_server_options(self):
        package_id = 13

        self._setup_package_mocks(package_id)

        args = {
            'server': 100,
            'hostname': 'unicorn',
            'domain': 'giggles.woo',
            'disks': [1000, 1000, 1000, 1000],
            'location': 'Wyrmshire',
            'os': 200,
            'port_speed': 600,
            'bare_metal': False,
            'package_id': 13,
            'ram': 1400,
            'disk_controller': 1500,
            'ssh_key': 3000,
        }

        expected = {
            'hardware': [
                {'domain': 'giggles.woo',
                 'bareMetalInstanceFlag': False,
                 'hostname':
                 'unicorn'}],
            'prices': [
                {'id': 100},
                {'id': 1000},
                {'id': 1000},
                {'id': 1000},
                {'id': 1000},
                {'id': 200},
                {'id': 600},
                {'id': 1400},
                {'id': 1500}],
            'sshKeys': [{'sshKeyIds': [3000]}],
            'location': 'Wyrmshire', 'packageId': 13
        }

        data = self.hardware._generate_create_dict(**args)
        self.assertEqual(expected, data)

    @patch('SoftLayer.managers.hardware.HardwareManager._generate_create_dict')
    def test_verify_order(self, create_dict):
        create_dict.return_value = {'test': 1, 'verify': 1}
        self.hardware.verify_order(test=1, verify=1)
        create_dict.assert_called_once_with(test=1, verify=1)
        f = self.client['Product_Order'].verifyOrder
        f.assert_called_once_with({'test': 1, 'verify': 1})

    @patch('SoftLayer.managers.hardware.HardwareManager._generate_create_dict')
    def test_place_order(self, create_dict):
        create_dict.return_value = {'test': 1, 'verify': 1}
        self.hardware.place_order(test=1, verify=1)
        create_dict.assert_called_once_with(test=1, verify=1)
        f = self.client['Product_Order'].placeOrder
        f.assert_called_once_with({'test': 1, 'verify': 1})

    def test_cancel_metal_immediately(self):
        b_id = 5678
        self.client.__getitem__().getObject.return_value = {'id': '1234',
                                                            'billingItem': {
                                                                'id': b_id,
                                                            }}
        self.hardware.cancel_metal(b_id, True)
        f = self.client['Billing_Item'].cancelService
        f.assert_called_once_with(id=b_id)

    def test_cancel_metal_on_anniversary(self):
        b_id = 5678
        self.client.__getitem__().getObject.return_value = {'id': '1234',
                                                            'billingItem': {
                                                                'id': b_id,
                                                            }}
        self.hardware.cancel_metal(b_id, False)
        f = self.client['Billing_Item'].cancelServiceOnAnniversaryDate
        f.assert_called_once_with(id=b_id)

    def test_cancel_hardware_without_reason(self):
        hw_id = 987

        self.hardware.cancel_hardware(hw_id)

        reasons = self.hardware.get_cancellation_reasons()

        f = self.client['Ticket'].createCancelServerTicket
        f.assert_called_once_with(hw_id, reasons['unneeded'], '', True,
                                  'HARDWARE')

    def test_cancel_hardware_with_reason_and_comment(self):
        hw_id = 987
        reason = 'sales'
        comment = 'Test Comment'

        self.hardware.cancel_hardware(hw_id, reason, comment)

        reasons = self.hardware.get_cancellation_reasons()

        f = self.client['Ticket'].createCancelServerTicket
        f.assert_called_once_with(hw_id, reasons[reason], comment, True,
                                  'HARDWARE')

    def test_change_port_speed_public(self):
        hw_id = 1
        speed = 100
        self.hardware.change_port_speed(hw_id, True, speed)

        service = self.client['Hardware_Server']
        f = service.setPublicNetworkInterfaceSpeed
        f.assert_called_once_with(speed, id=hw_id)

    def test_change_port_speed_private(self):
        hw_id = 2
        speed = 10
        self.hardware.change_port_speed(hw_id, False, speed)

        service = self.client['Hardware_Server']
        f = service.setPrivateNetworkInterfaceSpeed
        f.assert_called_once_with(speed, id=hw_id)

    def test_get_available_dedicated_server_packages(self):
        self.hardware.get_available_dedicated_server_packages()

        service = self.client['Product_Package']
        f = service.getObject
        f.assert_has_calls([call(id=13, mask='mask[id, name, description]')])

    def test_get_dedicated_server_options(self):
        package_id = 13

        self._setup_package_mocks(package_id)

        self.hardware.get_dedicated_server_create_options(package_id)

        f1 = self.client['Product_Package'].getRegions
        f1.assert_called_once_with(id=package_id)

        f2 = self.client['Product_Package'].getConfiguration
        f2.assert_called_once_with(id=package_id,
                                   mask='mask[itemCategory[group]]')

        f3 = self.client['Product_Package'].getCategories
        f3.assert_called_once_with(id=package_id)

    def test_get_default_value_returns_none_for_unknown_category(self):
        package_options = {'categories': ['Cat1', 'Cat2']}

        self.assertEqual(None, get_default_value(package_options,
                                                 'Unknown Category'))

    def test_get_default_value(self):
        price_id = 9876
        package_options = {'categories':
                           {'Cat1': {
                               'items': [{
                                   'prices': [{
                                       'setupFee': 0,
                                       'recurringFee': 0,
                                   }],
                                   'price_id': price_id,
                               }]
                           }}}

        self.assertEqual(price_id, get_default_value(package_options, 'Cat1'))

    def _setup_package_mocks(self, package_id):
        self.client['Product_Package'].getAllObjects.return_value = [
            {'name': 'Bare Metal Instance', 'id': package_id}]

        self.client['Product_Package'].getRegions.return_value = [{
            'location': {
                'locationPackageDetails': [{
                    'deliveryTimeInformation': 'Typically 2-4 hours',
                }],
            },
            'keyname': 'RANDOM_LOCATION',
            'description': 'Random unit testing location',
        }]

        self.client['Product_Package'].getConfiguration.return_value = [
            {
                'itemCategory': {
                    'categoryCode': 'random',
                    'name': 'Random Category',
                },
                'sort': 0,
                'orderStepId': 1,
                'isRequired': 0,
            },
            {
                'itemCategory': {
                    'categoryCode': 'disk0',
                    'name': 'First Disk',
                },
                'sort': 0,
                'orderStepId': 1,
                'isRequired': 1,
            },
            {
                'itemCategory': {
                    'categoryCode': 'disk1',
                    'name': 'Second Disk',
                },
                'sort': 0,
                'orderStepId': 1,
                'isRequired': 1,
            }
        ]

        prices = [{
            'itemId': 888,
            'id': 1888,
            'sort': 0,
            'setupFee': 0,
            'recurringFee': 0,
            'hourlyRecurringFee': 0,
            'oneTimeFee': 0,
            'laborFee': 0,
            'item': {
                'id': 888,
                'description': 'Some item',
                'capacity': 0,
            }
        }]

        disk0_prices = [{
            'itemId': 2000,
            'id': 12000,
            'sort': 0,
            'setupFee': 0,
            'recurringFee': 0,
            'hourlyRecurringFee': 0,
            'oneTimeFee': 0,
            'laborFee': 0,
            'item': {
                'id': 2000,
                'description': '1TB Drive',
                'capacity': 1000,
            }
        }]

        disk1_prices = [{
            'itemId': 2000,
            'id': 12000,
            'sort': 0,
            'setupFee': 0,
            'recurringFee': 25.0,
            'hourlyRecurringFee': 0,
            'oneTimeFee': 0,
            'laborFee': 0,
            'item': {
                'id': 2000,
                'description': '1TB Drive',
                'capacity': 1000,
            }
        }]
        self.client['Product_Package'].getCategories.return_value = [
            {
                'categoryCode': 'random',
                'name': 'Random Category',
                'id': 1000,
                'groups': [{
                    'sort': 0,
                    'prices': prices,
                    'itemCategoryId': 1000,
                    'packageId': package_id,
                }],
            },
            {
                'categoryCode': 'disk0',
                'name': 'First Disk',
                'isRequired': 1,
                'id': 1001,
                'groups': [{
                    'sort': 0,
                    'prices': disk0_prices,
                    'itemCategoryId': 1001,
                    'packageId': package_id,
                }],
            },
            {
                'categoryCode': 'disk1',
                'name': 'Second Disk',
                'isRequired': 1,
                'id': 1002,
                'groups': [{
                    'sort': 0,
                    'prices': disk1_prices,
                    'itemCategoryId': 1002,
                    'packageId': package_id,
                }],
            }
        ]