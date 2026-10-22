-- =====================================================================
-- Drone Delivery Management System - Baseline Seed Data
-- Database Name: DRONEDELIVERY
-- Purpose: Provides reproducible master data for Drones, Pilots, and Routes
-- Note: Designed to be fully idempotent (safe to run repeatedly via ON DUPLICATE KEY UPDATE)
-- =====================================================================

USE DRONEDELIVERY;

-- ---------------------------------------------------------------------
-- 1. DRONES (5 airframes with distinct payload capacities & base locations)
-- Note on LAST_DELIVERY: Set to initial commissioning timestamp for new drones
-- to satisfy the schema NOT NULL requirement without fabricating false deliveries.
-- ---------------------------------------------------------------------
INSERT INTO DRONES (DRONE_ID, PAYLOAD_CAP, CURR_LOCATION, PURCHASE_DATE, LAST_DELIVERY)
VALUES
    (101, 25, 'Warehouse A', '2026-01-10', '2026-01-10 09:00:00'),
    (102, 5,  'Warehouse B', '2026-02-15', '2026-02-15 10:30:00'),
    (103, 20, 'Warehouse C', '2026-03-01', '2026-03-01 11:15:00'),
    (104, 15, 'Warehouse A', '2026-04-12', '2026-04-12 14:00:00'),
    (105, 30, 'Warehouse B', '2026-05-20', '2026-05-20 16:45:00'),
    (106, 20, 'Warehouse A', '2026-06-15', '2026-06-15 08:00:00'),
    (107, 25, 'Warehouse B', '2026-07-01', '2026-07-01 09:30:00'),
    (108, 15, 'Warehouse C', '2026-08-10', '2026-08-10 11:00:00'),
    (109, 30, 'Warehouse A', '2026-09-05', '2026-09-05 14:15:00')
ON DUPLICATE KEY UPDATE
    PAYLOAD_CAP = VALUES(PAYLOAD_CAP),
    CURR_LOCATION = VALUES(CURR_LOCATION),
    PURCHASE_DATE = VALUES(PURCHASE_DATE),
    LAST_DELIVERY = VALUES(LAST_DELIVERY);

-- ---------------------------------------------------------------------
-- 2. PILOTS (5 certified pilots with valid licenses, 10-digit phones, and statuses)
-- Statuses: 4 AVAILABLE, 1 OFF_DUTY
-- ---------------------------------------------------------------------
INSERT INTO PILOTS (PILOT_ID, PILOT_NAME, LICENSE_NUMBER, PHONE_NO, STATUS)
VALUES
    (1, 'Pete Maverick Mitchell', 'LIC-MAV-001', '9876543007', 'AVAILABLE'),
    (2, 'Tom Iceman Kazansky',     'LIC-ICE-001', '9876543008', 'AVAILABLE'),
    (3, 'Nick Goose Bradshaw',     'LIC-GOS-001', '9876543009', 'AVAILABLE'),
    (4, 'Kara Starbuck Thrace',   'LIC-STR-001', '9876543010', 'AVAILABLE'),
    (5, 'Lee Apollo Adama',        'LIC-APO-001', '9876543011', 'OFF_DUTY')
ON DUPLICATE KEY UPDATE
    PILOT_NAME = VALUES(PILOT_NAME),
    LICENSE_NUMBER = VALUES(LICENSE_NUMBER),
    PHONE_NO = VALUES(PHONE_NO),
    STATUS = VALUES(STATUS);

-- ---------------------------------------------------------------------
-- 3. ROUTES (6 corridors connecting drone base warehouses with delivery zones)
-- Distances in km (DECIMAL 10,2), Estimated travel times in minutes (INT)
-- ---------------------------------------------------------------------
INSERT INTO ROUTES (ROUTE_ID, SOURCE, DESTINATION, DISTANCE, ESTIMATED_TIME)
VALUES
    (1, 'Warehouse A', 'Zone A',  8.50, 15),
    (2, 'Warehouse A', 'Zone B', 12.00, 22),
    (3, 'Warehouse B', 'Zone A', 10.00, 18),
    (4, 'Warehouse C', 'Zone C', 15.00, 25),
    (5, 'Warehouse B', 'Zone C', 14.20, 24),
    (6, 'Warehouse C', 'Zone B', 11.80, 20)
ON DUPLICATE KEY UPDATE
    SOURCE = VALUES(SOURCE),
    DESTINATION = VALUES(DESTINATION),
    DISTANCE = VALUES(DISTANCE),
    ESTIMATED_TIME = VALUES(ESTIMATED_TIME);
