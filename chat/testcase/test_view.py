# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.test import TestCase


class WatchTest(TestCase):
    def setUp(self):
        pass

    def test_watch(self):
        data = {'Event': 'ClusterIM', 'GroupId': '171277102', 'GroupName': '老婆怪的老婆巢', 'Sender': '371634316',
                'SenderName': '叮当猫', 'SendTime': '1510915158', 'Message': 'roll 100', 'RobotQQ': '2234743854',
                'Key': 'bilibili201714', 'Port': "8964'"}

        response = self.client.post("/receiver/", data=data)
        self.assertEqual(response.status_code,200)
