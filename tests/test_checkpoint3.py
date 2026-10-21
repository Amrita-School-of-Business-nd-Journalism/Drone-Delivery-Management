import unittest
import json
import datetime
from app import app, calculate_mission_billing
import database

class TestCheckpoint3Comprehensive(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        self.clean_test_data()
        self.seed_test_data()

    def tearDown(self):
        self.clean_test_data()

    def clean_test_data(self):
        conn = database.get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM PAYMENTS WHERE MISSION_ID >= 8800")
        cursor.execute("DELETE FROM MISSIONS WHERE MISSION_ID >= 8800")
        cursor.execute("DELETE FROM PACKAGES WHERE PACKAGE_ID >= 8800")
        cursor.execute("DELETE FROM MAINTENACE WHERE DRONE_ID >= 8800 OR MAINTENANCE_ID >= 8800")
        cursor.execute("DELETE FROM CHARGING_SESSIONS WHERE BATTERY_ID >= 8800")
        cursor.execute("DELETE FROM BATTERIES WHERE BATTERY_ID >= 8800")
        cursor.execute("DELETE FROM PILOTS WHERE PILOT_ID >= 8800")
        cursor.execute("DELETE FROM DRONES WHERE DRONE_ID >= 8800")
        conn.commit()
        database.close_db_connection(conn, cursor)

    def seed_test_data(self):
        conn = database.get_db_connection()
        cursor = conn.cursor()

        # Isolated Test Drone
        cursor.execute("""
            INSERT INTO DRONES (DRONE_ID, PAYLOAD_CAP, CURR_LOCATION, PURCHASE_DATE, LAST_DELIVERY)
            VALUES (8801, 20, 'Warehouse A', '2026-01-01', '2026-01-01 00:00:00')
        """)

        # Isolated Test Battery
        cursor.execute("""
            INSERT INTO BATTERIES (BATTERY_ID, DRONE_ID, CAPACITY, CYCLES, STATUS)
            VALUES (8801, 8801, 5000, 10, 'GOOD')
        """)

        # Isolated Test Pilot
        cursor.execute("""
            INSERT INTO PILOTS (PILOT_ID, PILOT_NAME, LICENSE_NUMBER, PHONE_NO, STATUS)
            VALUES (8801, 'Test Pilot 8801', 'LIC-TEST-8801', '9888888801', 'AVAILABLE')
        """)

        # Seed packages: 8801 for Customer 1 (User 1), 8802 for Customer 2 (User 2), both with Vendor 4
        cursor.execute("""
            INSERT INTO PACKAGES (PACKAGE_ID, USER_ID, VENDOR_ID, PRODUCT_ID, WEIGHT, PRIORITY, STATUS)
            VALUES (8801, 1, 4, 8881, 4, 1, 'AVAILABLE'),
                   (8802, 2, 4, 8882, 3, 1, 'AVAILABLE')
        """)

        conn.commit()
        database.close_db_connection(conn, cursor)

    def login_vendor(self, vendor_id=4):
        with self.client.session_transaction() as sess:
            sess['user_id'] = vendor_id
            sess['role'] = 'VENDOR'
            sess['email'] = f'vendor{vendor_id}@test.com'
            sess['first_name'] = f'Vendor{vendor_id}'

    def login_customer(self, user_id=1):
        with self.client.session_transaction() as sess:
            sess['user_id'] = user_id
            sess['role'] = 'CUSTOMER'
            sess['email'] = f'customer{user_id}@test.com'
            sess['first_name'] = f'Customer{user_id}'

    # =========================================================================
    # A. Static Checks
    # =========================================================================
    def test_01_static_routes_and_schema_objects(self):
        """Verifies Checkpoint 3 Flask routes and MariaDB objects are registered."""
        # 1. Flask routes
        rules = [r.rule for r in app.url_map.iter_rules()]
        self.assertIn('/api/customer/billing/<int:mission_id>', rules)
        self.assertIn('/api/customer/payments', rules)
        self.assertIn('/api/maintenance', rules)
        self.assertIn('/api/maintenance/drones-summary', rules)

        # 2. Database Objects
        conn = database.get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SHOW PROCEDURE STATUS WHERE Db = 'DRONEDELIVERY'")
        procs = [p['Name'] for p in cursor.fetchall()]
        self.assertIn('sp_process_payment', procs)
        self.assertIn('sp_record_maintenance', procs)

        cursor.execute("SHOW TRIGGERS")
        triggers = [t['Trigger'] for t in cursor.fetchall()]
        self.assertIn('trg_check_payment_mission_status', triggers)
        self.assertIn('trg_check_maintenance_validity', triggers)
        database.close_db_connection(conn, cursor)

    # =========================================================================
    # B. Billing & Payment Tests
    # =========================================================================
    def test_02_billing_calculation_formula(self):
        """Tests deterministic academic billing formula calculation."""
        # Route 1: distance = 8.5 km, Package weight = 4.0 kg
        # Formula: round(50 + (10 * 8.5) + (15 * 4)) = round(50 + 85 + 60) = 195 INR
        amt = calculate_mission_billing(8.5, 4.0)
        self.assertEqual(amt, 195)

        # Base fee lower bound
        self.assertEqual(calculate_mission_billing(0, 0), 50)

    def test_03_payment_workflow_for_completed_mission(self):
        """Tests successful billing calculation and payment creation for completed mission."""
        conn = database.get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO MISSIONS (MISSION_ID, DRONE_ID, PILOT_ID, PACKAGE_ID, ROUTE_ID, MISSION_STATUS, START_TIME, END_TIME)
            VALUES (8801, 8801, 8801, 8801, 1, 'OVER', NOW() - INTERVAL 1 HOUR, NOW())
        """)
        conn.commit()
        database.close_db_connection(conn, cursor)

        # Login as Customer 1 (owner of package 8801)
        self.login_customer(user_id=1)

        # 1. Inspect billing details
        resp = self.client.get('/api/customer/billing/8801')
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data['success'])
        billing = data['billing']
        self.assertEqual(billing['mission_status'], 'OVER')
        self.assertEqual(billing['total_amount'], 195)
        self.assertTrue(billing['eligible_for_payment'])
        self.assertFalse(billing['is_paid'])

        # 2. Process payment via ONLINE mode
        pay_resp = self.client.post('/api/customer/payments', json={
            'mission_id': 8801,
            'mode': 'ONLINE'
        })
        self.assertEqual(pay_resp.status_code, 200)
        pay_data = pay_resp.get_json()
        self.assertTrue(pay_data['success'])
        self.assertEqual(pay_data['status'], 'COMPLETED')
        self.assertEqual(pay_data['amount'], 195)

        # 3. Verify record in database
        conn = database.get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM PAYMENTS WHERE MISSION_ID = 8801")
        rec = cursor.fetchone()
        self.assertIsNotNone(rec)
        self.assertEqual(rec['AMOUNT'], 195)
        self.assertEqual(rec['MODE'], 'ONLINE')
        self.assertEqual(rec['STATUS'], 'COMPLETED')
        database.close_db_connection(conn, cursor)

        # 4. Prevent duplicate successful payment
        dup_resp = self.client.post('/api/customer/payments', json={
            'mission_id': 8801,
            'mode': 'ONLINE'
        })
        self.assertEqual(dup_resp.status_code, 409)

    def test_04_reject_payment_for_incomplete_mission(self):
        """Verifies that paying for an IDLE or ONGOING mission is rejected."""
        conn = database.get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO MISSIONS (MISSION_ID, DRONE_ID, PILOT_ID, PACKAGE_ID, ROUTE_ID, MISSION_STATUS, START_TIME, END_TIME)
            VALUES (8802, 8801, 8801, 8801, 1, 'ONGOING', NOW(), NULL)
        """)
        conn.commit()
        database.close_db_connection(conn, cursor)

        self.login_customer(user_id=1)
        resp = self.client.post('/api/customer/payments', json={
            'mission_id': 8802,
            'mode': 'ONLINE'
        })
        self.assertEqual(resp.status_code, 400)
        self.assertIn('must be completed', resp.get_json()['message'])

    def test_05_reject_cross_customer_payment_access(self):
        """Verifies Customer 1 cannot view or pay for Customer 2's package/mission."""
        conn = database.get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO MISSIONS (MISSION_ID, DRONE_ID, PILOT_ID, PACKAGE_ID, ROUTE_ID, MISSION_STATUS, START_TIME, END_TIME)
            VALUES (8803, 8801, 8801, 8802, 1, 'OVER', NOW(), NOW())
        """)
        conn.commit()
        database.close_db_connection(conn, cursor)

        # Customer 1 attempts to access mission 8803 belonging to Customer 2
        self.login_customer(user_id=1)

        resp_view = self.client.get('/api/customer/billing/8803')
        self.assertEqual(resp_view.status_code, 403)

        resp_pay = self.client.post('/api/customer/payments', json={
            'mission_id': 8803,
            'mode': 'ONLINE'
        })
        self.assertEqual(resp_pay.status_code, 403)

    def test_06_reject_unsupported_payment_mode(self):
        """Verifies invalid payment modes are rejected."""
        conn = database.get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO MISSIONS (MISSION_ID, DRONE_ID, PILOT_ID, PACKAGE_ID, ROUTE_ID, MISSION_STATUS, START_TIME, END_TIME)
            VALUES (8804, 8801, 8801, 8801, 1, 'OVER', NOW(), NOW())
        """)
        conn.commit()
        database.close_db_connection(conn, cursor)

        self.login_customer(user_id=1)
        resp = self.client.post('/api/customer/payments', json={
            'mission_id': 8804,
            'mode': 'BITCOIN'
        })
        self.assertEqual(resp.status_code, 400)

    # =========================================================================
    # C. Maintenance Management Tests
    # =========================================================================
    def test_07_maintenance_record_creation_and_history(self):
        """Tests that a vendor can log a maintenance event and view history."""
        self.login_vendor(vendor_id=4)

        resp = self.client.post('/api/maintenance', json={
            'drone_id': 8801,
            'status': 'GOOD',
            'cost': 250,
            'reason': 'Routine motor inspection passed'
        })
        self.assertEqual(resp.status_code, 201)
        data = resp.get_json()
        self.assertTrue(data['success'])
        maint_id = data['maintenance_id']

        # View history
        get_resp = self.client.get('/api/maintenance')
        self.assertEqual(get_resp.status_code, 200)
        records = get_resp.get_json()['maintenance_records']
        ids = [r['MAINTENANCE_ID'] for r in records]
        self.assertIn(maint_id, ids)

    def test_08_grounded_drone_blocks_mission_and_clearance_restores(self):
        """Tests that BAD maintenance grounds a drone, and GOOD clearance restores it."""
        self.login_vendor(vendor_id=4)

        # 1. Ground Drone 8801 with BAD status
        resp_ground = self.client.post('/api/maintenance', json={
            'drone_id': 8801,
            'status': 'BAD',
            'cost': 400,
            'reason': 'Motor overheating detected'
        })
        self.assertEqual(resp_ground.status_code, 201)

        # 2. Attempt to create mission with Drone 8801 -> Must be rejected (400)
        resp_m = self.client.post('/api/missions', json={
            'mission_id': 8805,
            'drone_id': 8801,
            'pilot_id': 8801,
            'package_id': 8801,
            'route_id': 1
        })
        self.assertEqual(resp_m.status_code, 400)
        self.assertIn('grounded under active maintenance', resp_m.get_json()['message'])

        # 3. Log clearance inspection record with GOOD status
        resp_clear = self.client.post('/api/maintenance', json={
            'drone_id': 8801,
            'status': 'GOOD',
            'cost': 150,
            'reason': 'Motor cooling system serviced and verified'
        })
        self.assertEqual(resp_clear.status_code, 201)

        # 4. Attempt to create mission again -> Should now succeed!
        resp_m_ok = self.client.post('/api/missions', json={
            'mission_id': 8805,
            'drone_id': 8801,
            'pilot_id': 8801,
            'package_id': 8801,
            'route_id': 1
        })
        self.assertEqual(resp_m_ok.status_code, 201)

    def test_09_maintenance_validation_guards(self):
        """Tests that invalid cost (<=0) or invalid status are rejected."""
        self.login_vendor(vendor_id=4)

        # Cost <= 0
        resp_cost = self.client.post('/api/maintenance', json={
            'drone_id': 8801,
            'status': 'GOOD',
            'cost': -50,
            'reason': 'Invalid cost test'
        })
        self.assertEqual(resp_cost.status_code, 400)

        # Invalid Status
        resp_stat = self.client.post('/api/maintenance', json={
            'drone_id': 8801,
            'status': 'EXCELLENT',
            'cost': 100,
            'reason': 'Invalid status test'
        })
        self.assertEqual(resp_stat.status_code, 400)

        # Nonexistent drone
        resp_drone = self.client.post('/api/maintenance', json={
            'drone_id': 99999,
            'status': 'GOOD',
            'cost': 100,
            'reason': 'Nonexistent drone test'
        })
        self.assertEqual(resp_drone.status_code, 404)

    def test_10_customer_forbidden_from_maintenance(self):
        """Customer role must receive 403 Forbidden on maintenance endpoints."""
        self.login_customer(user_id=1)

        resp_get = self.client.get('/api/maintenance')
        self.assertEqual(resp_get.status_code, 403)

        resp_post = self.client.post('/api/maintenance', json={
            'drone_id': 8801,
            'status': 'GOOD',
            'cost': 100
        })
        self.assertEqual(resp_post.status_code, 403)

    # =========================================================================
    # D. Transaction Rollback & Invariant Tests
    # =========================================================================
    def test_11_payment_rollback_on_failure(self):
        """Verifies that an aborted payment rolls back completely."""
        conn = database.get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO MISSIONS (MISSION_ID, DRONE_ID, PILOT_ID, PACKAGE_ID, ROUTE_ID, MISSION_STATUS)
            VALUES (8806, 8801, 8801, 8801, 1, 'IDLE')
        """)
        conn.commit()
        database.close_db_connection(conn, cursor)

        self.login_customer(user_id=1)
        resp = self.client.post('/api/customer/payments', json={
            'mission_id': 8806,
            'mode': 'ONLINE'
        })
        self.assertEqual(resp.status_code, 400)

        # Confirm zero records inserted in PAYMENTS
        conn = database.get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT COUNT(*) AS c FROM PAYMENTS WHERE MISSION_ID = 8806")
        self.assertEqual(cursor.fetchone()['c'], 0)
        database.close_db_connection(conn, cursor)

    # =========================================================================
    # E. Full Regression (Checkpoints 1, 2 & 3)
    # =========================================================================
    def test_12_full_end_to_end_delivery_and_settlement_regression(self):
        """End-to-end regression: Create Mission -> Start -> Complete -> Bill & Pay -> Check History."""
        # Step 1: Vendor creates mission
        self.login_vendor(vendor_id=4)
        create_resp = self.client.post('/api/missions', json={
            'mission_id': 8807,
            'drone_id': 8801,
            'pilot_id': 8801,
            'package_id': 8801,
            'route_id': 1
        })
        self.assertEqual(create_resp.status_code, 201)

        # Step 2: Vendor starts mission (sets pilot ON_MISSION)
        start_resp = self.client.post('/api/missions/8807/start')
        self.assertEqual(start_resp.status_code, 200)

        # Step 3: Vendor completes mission (frees pilot, updates drone location, moves to OVER)
        complete_resp = self.client.post('/api/missions/8807/complete')
        self.assertEqual(complete_resp.status_code, 200)

        # Step 4: Customer views billing breakdown and pays
        self.login_customer(user_id=1)
        bill_resp = self.client.get('/api/customer/billing/8807')
        self.assertEqual(bill_resp.status_code, 200)
        self.assertEqual(bill_resp.get_json()['billing']['total_amount'], 195)

        pay_resp = self.client.post('/api/customer/payments', json={
            'mission_id': 8807,
            'mode': 'ONLINE'
        })
        self.assertEqual(pay_resp.status_code, 200)

        # Step 5: Customer views payments history
        hist_resp = self.client.get('/api/customer/payments')
        self.assertEqual(hist_resp.status_code, 200)
        pay_list = hist_resp.get_json()['payments']
        mission_ids = [p['MISSION_ID'] for p in pay_list]
        self.assertIn(8807, mission_ids)

if __name__ == '__main__':
    unittest.main()
