import unittest
import json
from app import app
import database

class TestCheckpoint2Integrity(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        self.clean_test_data()
        self.seed_test_data()

    def tearDown(self):
        self.clean_test_data()

    def clean_test_data(self):
        conn = database.get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM CHARGING_SESSIONS WHERE BATTERY_ID IN (998, 999)")
        cursor.execute("DELETE FROM BATTERIES WHERE BATTERY_ID IN (998, 999)")
        cursor.execute("DELETE FROM MAINTENACE WHERE MAINTENANCE_ID IN (998, 999)")
        cursor.execute("DELETE FROM MISSIONS WHERE MISSION_ID >= 7000")
        cursor.execute("DELETE FROM PACKAGES WHERE PACKAGE_ID >= 7000")
        cursor.execute("DELETE FROM PILOTS WHERE PILOT_ID >= 700")
        cursor.execute("DELETE FROM DRONES WHERE DRONE_ID >= 700")
        conn.commit()
        database.close_db_connection(conn, cursor)

    def seed_test_data(self):
        conn = database.get_db_connection()
        cursor = conn.cursor()

        # Drones
        cursor.execute("""
            INSERT INTO DRONES (DRONE_ID, PAYLOAD_CAP, CURR_LOCATION, PURCHASE_DATE, LAST_DELIVERY)
            VALUES (701, 20, 'Warehouse A', '2026-01-01', '2026-01-01 00:00:00'),
                   (702, 5,  'Warehouse B', '2026-01-01', '2026-01-01 00:00:00')
        """)

        # Batteries
        cursor.execute("""
            INSERT INTO BATTERIES (BATTERY_ID, DRONE_ID, CAPACITY, CYCLES, STATUS)
            VALUES (998, 701, 5000, 10, 'GOOD'),
                   (999, 702, 5000, 10, 'GOOD')
        """)

        # Pilots
        cursor.execute("""
            INSERT INTO PILOTS (PILOT_ID, PILOT_NAME, LICENSE_NUMBER, PHONE_NO, STATUS)
            VALUES (701, 'Test Maverick', 'LIC-TEST-701', '9870000701', 'AVAILABLE'),
                   (702, 'Test OffDuty',  'LIC-TEST-702', '9870000702', 'OFF_DUTY')
        """)

        # Packages
        cursor.execute("""
            INSERT INTO PACKAGES (PACKAGE_ID, USER_ID, VENDOR_ID, PRODUCT_ID, WEIGHT, PRIORITY, STATUS)
            VALUES (7001, 1, 4, 7001, 8,  1, 'AVAILABLE'),
                   (7002, 1, 4, 7002, 12, 1, 'AVAILABLE'),
                   (7003, 1, 5, 7003, 6,  1, 'AVAILABLE')
        """)

        conn.commit()
        database.close_db_connection(conn, cursor)

    def login_vendor(self, vendor_id=4):
        with self.client.session_transaction() as sess:
            sess['user_id'] = vendor_id
            sess['role'] = 'VENDOR'
            sess['email'] = f'vendor{vendor_id}@test.com'
            sess['first_name'] = f'Vendor{vendor_id}'

    # -----------------------------------------------------------------
    # Positive Integration Tests
    # -----------------------------------------------------------------
    def test_01_full_delivery_lifecycle_success(self):
        """Tests complete valid lifecycle: Create -> Start -> Complete -> Location/Status updates"""
        self.login_vendor(vendor_id=4)

        # 1. Create Mission (Drone 701, Pilot 701, Package 7001, Route 1 [Zone A])
        res = self.client.post('/api/missions', json={
            'mission_id': 7101,
            'drone_id': 701,
            'pilot_id': 701,
            'package_id': 7001,
            'route_id': 1
        })
        self.assertEqual(res.status_code, 201)
        data = res.get_json()
        self.assertTrue(data['success'])

        # Verify Package was reserved (NOT AVAILABLE)
        conn = database.get_db_connection()
        c = conn.cursor(dictionary=True)
        c.execute("SELECT STATUS FROM PACKAGES WHERE PACKAGE_ID = 7001")
        self.assertEqual(c.fetchone()['STATUS'], 'NOT AVAILABLE')
        database.close_db_connection(conn, c)

        # 2. Start Mission
        res = self.client.post('/api/missions/7101/start')
        self.assertEqual(res.status_code, 200)

        # Verify Mission is ONGOING and Pilot is ON_MISSION
        conn = database.get_db_connection()
        c = conn.cursor(dictionary=True)
        c.execute("SELECT MISSION_STATUS FROM MISSIONS WHERE MISSION_ID = 7101")
        self.assertEqual(c.fetchone()['MISSION_STATUS'], 'ONGOING')
        c.execute("SELECT STATUS FROM PILOTS WHERE PILOT_ID = 701")
        self.assertEqual(c.fetchone()['STATUS'], 'ON_MISSION')
        database.close_db_connection(conn, c)

        # 3. Complete Mission
        res = self.client.post('/api/missions/7101/complete')
        self.assertEqual(res.status_code, 200)

        # Verify Mission is OVER, Pilot is AVAILABLE, Drone location is Zone A (Route 1 destination)
        conn = database.get_db_connection()
        c = conn.cursor(dictionary=True)
        c.execute("SELECT MISSION_STATUS, END_TIME FROM MISSIONS WHERE MISSION_ID = 7101")
        m_rec = c.fetchone()
        self.assertEqual(m_rec['MISSION_STATUS'], 'OVER')
        self.assertIsNotNone(m_rec['END_TIME'])

        c.execute("SELECT STATUS FROM PILOTS WHERE PILOT_ID = 701")
        self.assertEqual(c.fetchone()['STATUS'], 'AVAILABLE')

        c.execute("SELECT CURR_LOCATION, LAST_DELIVERY FROM DRONES WHERE DRONE_ID = 701")
        d_rec = c.fetchone()
        self.assertEqual(d_rec['CURR_LOCATION'], 'Zone A')
        self.assertIsNotNone(d_rec['LAST_DELIVERY'])
        database.close_db_connection(conn, c)

    def test_02_mission_cancellation(self):
        """Tests that IDLE mission can be cancelled and restores package to AVAILABLE"""
        self.login_vendor(vendor_id=4)

        # Create Mission 7102
        res = self.client.post('/api/missions', json={
            'mission_id': 7102,
            'drone_id': 701,
            'pilot_id': 701,
            'package_id': 7001,
            'route_id': 1
        })
        self.assertEqual(res.status_code, 201)

        # Cancel Mission
        res = self.client.post('/api/missions/7102/cancel')
        self.assertEqual(res.status_code, 200)

        # Verify mission is CANCELLED and package restored to AVAILABLE
        conn = database.get_db_connection()
        c = conn.cursor(dictionary=True)
        c.execute("SELECT MISSION_STATUS FROM MISSIONS WHERE MISSION_ID = 7102")
        self.assertEqual(c.fetchone()['MISSION_STATUS'], 'CANCELLED')
        c.execute("SELECT STATUS FROM PACKAGES WHERE PACKAGE_ID = 7001")
        self.assertEqual(c.fetchone()['STATUS'], 'AVAILABLE')
        database.close_db_connection(conn, c)

    def test_03_charging_session_lifecycle(self):
        """Tests that a drone not in flight can start and end charging sessions successfully"""
        self.login_vendor(vendor_id=4)

        # Start charging session on Battery 998 (Drone 701 is currently not flying)
        res = self.client.post('/api/charging-sessions/start', json={'battery_id': 998})
        self.assertEqual(res.status_code, 201)

        # End charging session
        res = self.client.post('/api/charging-sessions/end', json={'battery_id': 998})
        self.assertEqual(res.status_code, 200)

    # -----------------------------------------------------------------
    # Negative Integrity Tests
    # -----------------------------------------------------------------
    def test_04_overweight_drone_assignment_rejected(self):
        """Tests that assigning a 12kg package to a 5kg drone is rejected"""
        self.login_vendor(vendor_id=4)
        res = self.client.post('/api/missions', json={
            'mission_id': 7103,
            'drone_id': 702,      # 5kg capacity
            'pilot_id': 701,
            'package_id': 7002,   # 12kg weight
            'route_id': 1
        })
        self.assertEqual(res.status_code, 400)
        self.assertIn('exceeds drone payload capacity', res.get_json()['message'].lower())

    def test_05_cross_vendor_package_dispatch_rejected(self):
        """Tests that Vendor 4 cannot dispatch Package 7003 belonging to Vendor 5"""
        self.login_vendor(vendor_id=4)
        res = self.client.post('/api/missions', json={
            'mission_id': 7104,
            'drone_id': 701,
            'pilot_id': 701,
            'package_id': 7003,   # Vendor 5's package
            'route_id': 1
        })
        self.assertEqual(res.status_code, 403)
        self.assertIn('another vendor', res.get_json()['message'].lower())

    def test_06_off_duty_pilot_assignment_rejected(self):
        """Tests that assigning an OFF_DUTY pilot is rejected"""
        self.login_vendor(vendor_id=4)
        res = self.client.post('/api/missions', json={
            'mission_id': 7105,
            'drone_id': 701,
            'pilot_id': 702,      # OFF_DUTY pilot
            'package_id': 7001,
            'route_id': 1
        })
        self.assertEqual(res.status_code, 400)
        self.assertIn('off_duty', res.get_json()['message'].lower())

    def test_07_drone_charging_prevents_mission_start(self):
        """Tests that a drone whose battery is currently charging cannot start a mission"""
        self.login_vendor(vendor_id=4)

        # Create Mission 7106 (IDLE)
        res = self.client.post('/api/missions', json={
            'mission_id': 7106,
            'drone_id': 701,
            'pilot_id': 701,
            'package_id': 7001,
            'route_id': 1
        })
        self.assertEqual(res.status_code, 201)

        # Now start charging Battery 998 (Drone 701's battery)
        res_charge = self.client.post('/api/charging-sessions/start', json={'battery_id': 998})
        self.assertEqual(res_charge.status_code, 201)

        # Attempt to start mission while charging
        res_start = self.client.post('/api/missions/7106/start')
        self.assertEqual(res_start.status_code, 400)
        self.assertIn('charging', res_start.get_json()['message'].lower())

    def test_08_charging_prevented_while_drone_flying(self):
        """Tests that charging cannot be initiated while a drone is on an ONGOING mission"""
        self.login_vendor(vendor_id=4)

        # Create and Start Mission 7107
        res_create = self.client.post('/api/missions', json={
            'mission_id': 7107,
            'drone_id': 701,
            'pilot_id': 701,
            'package_id': 7001,
            'route_id': 1
        })
        self.assertEqual(res_create.status_code, 201)

        res_start = self.client.post('/api/missions/7107/start')
        self.assertEqual(res_start.status_code, 200)

        # Attempt to initiate charging while flying
        res_charge = self.client.post('/api/charging-sessions/start', json={'battery_id': 998})
        self.assertEqual(res_charge.status_code, 400)
        self.assertIn('ongoing mission', res_charge.get_json()['message'].lower())

    def test_09_illegal_mission_transition_rejected(self):
        """Tests that illegal direct transition (e.g. from OVER to ONGOING or IDLE) is rejected by trigger"""
        conn = database.get_db_connection()
        c = conn.cursor()
        c.execute("""
            INSERT INTO MISSIONS (MISSION_ID, DRONE_ID, PILOT_ID, PACKAGE_ID, ROUTE_ID, MISSION_STATUS)
            VALUES (7109, 701, 701, 7001, 1, 'OVER')
        """)
        conn.commit()

        # Attempt illegal update on finished mission
        with self.assertRaises(Exception) as ctx:
            c.execute("UPDATE MISSIONS SET MISSION_STATUS='ONGOING' WHERE MISSION_ID = 7109")
        self.assertIn('completed (over) missions cannot be altered', str(ctx.exception).lower())
        conn.rollback()
        database.close_db_connection(conn, c)

    def test_10_unauthorized_user_access_blocked(self):
        """Tests that Customer role receives 403 when attempting to create/start/complete/cancel missions"""
        with self.client.session_transaction() as sess:
            sess['user_id'] = 99
            sess['role'] = 'CUSTOMER'

        for endpoint in ['/api/missions', '/api/missions/7101/start', '/api/missions/7101/complete', '/api/missions/7101/cancel']:
            res = self.client.post(endpoint, json={})
            self.assertEqual(res.status_code, 403)

    # -----------------------------------------------------------------
    # Rollback & Transaction Consistency Tests
    # -----------------------------------------------------------------
    def test_11_rollback_on_failed_mission_creation(self):
        """Forces an error during sp_create_mission (overweight) and verifies zero tentative changes persist"""
        self.login_vendor(vendor_id=4)

        # Package 7002 is 12kg; Drone 702 is 5kg
        res = self.client.post('/api/missions', json={
            'mission_id': 7111,
            'drone_id': 702,
            'pilot_id': 701,
            'package_id': 7002,
            'route_id': 1
        })
        self.assertEqual(res.status_code, 400)

        conn = database.get_db_connection()
        c = conn.cursor(dictionary=True)
        # Verify no mission record was created
        c.execute("SELECT * FROM MISSIONS WHERE MISSION_ID = 7111")
        self.assertIsNone(c.fetchone())

        # Verify package remains AVAILABLE (not reserved)
        c.execute("SELECT STATUS FROM PACKAGES WHERE PACKAGE_ID = 7002")
        self.assertEqual(c.fetchone()['STATUS'], 'AVAILABLE')

        # Verify pilot remains AVAILABLE
        c.execute("SELECT STATUS FROM PILOTS WHERE PILOT_ID = 701")
        self.assertEqual(c.fetchone()['STATUS'], 'AVAILABLE')
        database.close_db_connection(conn, c)

    def test_12_rollback_on_failed_mission_start(self):
        """Forces an error during sp_start_mission (drone is charging) and verifies pilot is not stuck ON_MISSION"""
        self.login_vendor(vendor_id=4)

        # Create Mission 7112
        res = self.client.post('/api/missions', json={
            'mission_id': 7112,
            'drone_id': 701,
            'pilot_id': 701,
            'package_id': 7001,
            'route_id': 1
        })
        self.assertEqual(res.status_code, 201)

        # Start charging session
        self.client.post('/api/charging-sessions/start', json={'battery_id': 998})

        # Try starting mission while charging (should fail)
        res = self.client.post('/api/missions/7112/start')
        self.assertEqual(res.status_code, 400)

        # Verify transaction rolled back: Pilot must NOT be ON_MISSION; Mission must remain IDLE
        conn = database.get_db_connection()
        c = conn.cursor(dictionary=True)
        c.execute("SELECT MISSION_STATUS FROM MISSIONS WHERE MISSION_ID = 7112")
        self.assertEqual(c.fetchone()['MISSION_STATUS'], 'IDLE')

        c.execute("SELECT STATUS FROM PILOTS WHERE PILOT_ID = 701")
        self.assertEqual(c.fetchone()['STATUS'], 'AVAILABLE')
        database.close_db_connection(conn, c)

if __name__ == '__main__':
    unittest.main()
