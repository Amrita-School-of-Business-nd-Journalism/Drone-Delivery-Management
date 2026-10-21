-- =====================================================================
-- Drone Delivery Management System - Checkpoint 3 Script
-- Database Name: DRONEDELIVERY
-- Purpose: Payment Billing Workflow, Maintenance Diagnostics & 
--          Grounding Clearance, Stored Procedures, and Triggers.
-- Repeatability: Idempotent (ALTER with safety checks, DROP IF EXISTS).
-- =====================================================================

USE DRONEDELIVERY;

-- ---------------------------------------------------------------------
-- 0. Schema Adjustments
-- Ensure PAYMENTS.PAYMENT_ID and MAINTENACE.MAINTENANCE_ID use AUTO_INCREMENT
-- ---------------------------------------------------------------------
ALTER TABLE PAYMENTS MODIFY COLUMN PAYMENT_ID INT AUTO_INCREMENT;
ALTER TABLE MAINTENACE MODIFY COLUMN MAINTENANCE_ID INT AUTO_INCREMENT;

-- ---------------------------------------------------------------------
-- 1. Database Triggers
-- ---------------------------------------------------------------------

-- Trigger 1: Payment Mission Completion & Duplicate Guard
-- Enforces:
-- 1. Payment can only be logged for missions that are completed ('OVER').
-- 2. Cannot record duplicate COMPLETED payments for the same mission.
DROP TRIGGER IF EXISTS trg_check_payment_mission_status;

DELIMITER //

CREATE TRIGGER trg_check_payment_mission_status
BEFORE INSERT ON PAYMENTS
FOR EACH ROW
BEGIN
    DECLARE v_m_status VARCHAR(20);
    DECLARE v_completed_count INT DEFAULT 0;

    -- Fetch mission status
    SELECT MISSION_STATUS INTO v_m_status
    FROM MISSIONS
    WHERE MISSION_ID = NEW.MISSION_ID;

    IF v_m_status IS NULL THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Payment Integrity Error: Referenced Mission does not exist.';
    END IF;

    IF v_m_status != 'OVER' THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Payment Integrity Error: Cannot process payment for an incomplete mission. Mission must be OVER.';
    END IF;

    -- Prevent duplicate successful payments
    IF NEW.STATUS = 'COMPLETED' THEN
        SELECT COUNT(*) INTO v_completed_count
        FROM PAYMENTS
        WHERE MISSION_ID = NEW.MISSION_ID AND STATUS = 'COMPLETED';

        IF v_completed_count > 0 THEN
            SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Payment Integrity Error: Mission has already been paid for.';
        END IF;
    END IF;
END//

DELIMITER ;

-- Trigger 2: Maintenance Input Validation Guard
-- Enforces: COST > 0 and REPAIR_DATE cannot be unreasonably in the future.
DROP TRIGGER IF EXISTS trg_check_maintenance_validity;

DELIMITER //

CREATE TRIGGER trg_check_maintenance_validity
BEFORE INSERT ON MAINTENACE
FOR EACH ROW
BEGIN
    IF NEW.COST <= 0 THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Maintenance Error: Repair cost must be a strictly positive integer.';
    END IF;

    IF NEW.STATUS NOT IN ('GOOD', 'BAD') THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Maintenance Error: Maintenance status must be either GOOD or BAD.';
    END IF;

    IF NEW.REPAIR_DATE > DATE_ADD(CURRENT_DATE(), INTERVAL 1 DAY) THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Maintenance Error: Repair date cannot be set in the future.';
    END IF;
END//

DELIMITER ;

-- ---------------------------------------------------------------------
-- 2. Stored Procedures
-- ---------------------------------------------------------------------

-- Stored Procedure 1: sp_process_payment
-- Validates customer package ownership, mission completion, billing
-- amount verification, duplicate prevention, and atomic insertion.
DROP PROCEDURE IF EXISTS sp_process_payment;

DELIMITER //

CREATE PROCEDURE sp_process_payment(
    IN p_user_id INT,
    IN p_mission_id INT,
    IN p_mode VARCHAR(10),
    OUT p_payment_id INT,
    OUT p_final_amount INT,
    OUT p_status_code INT,
    OUT p_status_message VARCHAR(255)
)
proc_label: BEGIN
    DECLARE v_pkg_user_id INT;
    DECLARE v_mission_status VARCHAR(20);
    DECLARE v_weight INT;
    DECLARE v_distance DECIMAL(10,2);
    DECLARE v_calculated_amount INT;
    DECLARE v_completed_count INT DEFAULT 0;
    DECLARE v_target_status VARCHAR(20);

    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        SET p_status_code = 500;
        SET p_status_message = 'Database error during payment transaction.';
        SET p_payment_id = NULL;
        SET p_final_amount = NULL;
    END;

    START TRANSACTION;

    -- 1. Validate payment mode
    IF p_mode NOT IN ('COD', 'ONLINE') THEN
        ROLLBACK;
        SET p_status_code = 400;
        SET p_status_message = 'Invalid payment mode. Supported modes: COD, ONLINE.';
        LEAVE proc_label;
    END IF;

    -- 2. Fetch and lock mission details
    SELECT p.USER_ID, m.MISSION_STATUS, p.WEIGHT, r.DISTANCE
    INTO v_pkg_user_id, v_mission_status, v_weight, v_distance
    FROM MISSIONS m
    JOIN PACKAGES p ON m.PACKAGE_ID = p.PACKAGE_ID
    JOIN ROUTES r ON m.ROUTE_ID = r.ROUTE_ID
    WHERE m.MISSION_ID = p_mission_id
    FOR UPDATE;

    IF v_mission_status IS NULL THEN
        ROLLBACK;
        SET p_status_code = 404;
        SET p_status_message = CONCAT('Mission ID ', p_mission_id, ' not found.');
        LEAVE proc_label;
    END IF;

    -- 3. Verify customer package ownership
    IF v_pkg_user_id != p_user_id THEN
        ROLLBACK;
        SET p_status_code = 403;
        SET p_status_message = 'Access denied: You do not own the package associated with this mission.';
        LEAVE proc_label;
    END IF;

    -- 4. Verify mission is completed ('OVER')
    IF v_mission_status != 'OVER' THEN
        ROLLBACK;
        SET p_status_code = 400;
        SET p_status_message = CONCAT('Cannot process payment: Mission is in status \'', v_mission_status, '\'. Missions must be completed (OVER) to be billed.');
        LEAVE proc_label;
    END IF;

    -- 5. Prevent duplicate COMPLETED payments
    SELECT COUNT(*) INTO v_completed_count
    FROM PAYMENTS
    WHERE MISSION_ID = p_mission_id AND STATUS = 'COMPLETED';

    IF v_completed_count > 0 THEN
        ROLLBACK;
        SET p_status_code = 409;
        SET p_status_message = 'Mission has already been paid for.';
        LEAVE proc_label;
    END IF;

    -- 6. Server-side Deterministic Billing Calculation
    -- Base Fee: 50 INR + Distance Fee (10 INR/km) + Weight Fee (15 INR/kg)
    SET v_calculated_amount = ROUND(50 + (10 * v_distance) + (15 * v_weight));
    IF v_calculated_amount < 50 THEN
        SET v_calculated_amount = 50;
    END IF;

    -- Set status based on mode
    IF p_mode = 'ONLINE' THEN
        SET v_target_status = 'COMPLETED';
    ELSE
        SET v_target_status = 'PROCESSING';
    END IF;

    -- 7. Insert payment record
    INSERT INTO PAYMENTS (USER_ID, MISSION_ID, TIMESTAMP, MODE, AMOUNT, STATUS)
    VALUES (p_user_id, p_mission_id, NOW(), p_mode, v_calculated_amount, v_target_status);

    SET p_payment_id = LAST_INSERT_ID();
    SET p_final_amount = v_calculated_amount;

    COMMIT;

    SET p_status_code = 200;
    SET p_status_message = CONCAT('Payment recorded successfully with status ', v_target_status, '.');
END//

DELIMITER ;

-- Stored Procedure 2: sp_record_maintenance
-- Inserts a maintenance/repair event for a drone, updating its diagnostic history.
DROP PROCEDURE IF EXISTS sp_record_maintenance;

DELIMITER //

CREATE PROCEDURE sp_record_maintenance(
    IN p_drone_id INT,
    IN p_status VARCHAR(10),
    IN p_cost INT,
    IN p_reason VARCHAR(100),
    IN p_repair_date DATE,
    OUT p_maint_id INT,
    OUT p_status_code INT,
    OUT p_status_message VARCHAR(255)
)
proc_label: BEGIN
    DECLARE v_drone_exists INT DEFAULT 0;
    DECLARE v_active_flying INT DEFAULT 0;
    DECLARE v_date DATE;

    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        SET p_status_code = 500;
        SET p_status_message = 'Database error during maintenance recording transaction.';
        SET p_maint_id = NULL;
    END;

    START TRANSACTION;

    -- Validate drone existence
    SELECT COUNT(*) INTO v_drone_exists
    FROM DRONES
    WHERE DRONE_ID = p_drone_id;

    IF v_drone_exists = 0 THEN
        ROLLBACK;
        SET p_status_code = 404;
        SET p_status_message = CONCAT('Drone ID ', p_drone_id, ' does not exist.');
        LEAVE proc_label;
    END IF;

    -- Validate status
    IF p_status NOT IN ('GOOD', 'BAD') THEN
        ROLLBACK;
        SET p_status_code = 400;
        SET p_status_message = 'Invalid maintenance status. Must be GOOD or BAD.';
        LEAVE proc_label;
    END IF;

    -- Validate cost
    IF p_cost <= 0 THEN
        ROLLBACK;
        SET p_status_code = 400;
        SET p_status_message = 'Maintenance cost must be a strictly positive integer.';
        LEAVE proc_label;
    END IF;

    -- Validate reason
    IF p_reason IS NULL OR TRIM(p_reason) = '' THEN
        SET p_reason = IF(p_status = 'GOOD', 'Routine Inspection Passed', 'Maintenance Issue Detected');
    END IF;

    -- Validate date
    IF p_repair_date IS NULL THEN
        SET v_date = CURRENT_DATE();
    ELSE
        SET v_date = p_repair_date;
    END IF;

    -- Insert maintenance record
    INSERT INTO MAINTENACE (DRONE_ID, STATUS, REPAIR_DATE, COST, REASON)
    VALUES (p_drone_id, p_status, v_date, p_cost, p_reason);

    SET p_maint_id = LAST_INSERT_ID();

    COMMIT;

    SET p_status_code = 201;
    SET p_status_message = CONCAT('Maintenance record #', p_maint_id, ' successfully created.');
END//

DELIMITER ;

-- ---------------------------------------------------------------------
-- 3. Refine sp_create_mission and sp_start_mission for Maintenance State
-- Ensure drone maintenance status evaluates the LATEST maintenance record
-- rather than permanently grounding a drone after historical repairs.
-- ---------------------------------------------------------------------

DROP PROCEDURE IF EXISTS sp_create_mission;

DELIMITER //

CREATE PROCEDURE sp_create_mission(
    IN p_drone_id INT,
    IN p_pilot_id INT,
    IN p_package_id INT,
    IN p_route_id INT,
    IN p_vendor_id INT,
    IN p_custom_mission_id INT,
    OUT p_mission_id INT,
    OUT p_status_code INT,
    OUT p_status_message VARCHAR(255)
)
proc_label: BEGIN
    DECLARE v_drone_exists INT DEFAULT 0;
    DECLARE v_pilot_exists INT DEFAULT 0;
    DECLARE v_pkg_exists INT DEFAULT 0;
    DECLARE v_route_exists INT DEFAULT 0;
    DECLARE v_pkg_vendor INT;
    DECLARE v_drone_cap INT;
    DECLARE v_pkg_weight INT;
    DECLARE v_pilot_status VARCHAR(20);
    DECLARE v_good_batteries INT DEFAULT 0;
    DECLARE v_charging_batteries INT DEFAULT 0;
    DECLARE v_latest_maint_status VARCHAR(10) DEFAULT 'GOOD';
    DECLARE v_conflict_count INT DEFAULT 0;
    DECLARE v_target_mission_id INT;

    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        SET p_status_code = 500;
        SET p_status_message = 'Database error during mission creation transaction.';
        SET p_mission_id = NULL;
    END;

    START TRANSACTION;

    -- 1. Validate entity existence
    SELECT COUNT(*), COALESCE(MAX(PAYLOAD_CAP), 0) INTO v_drone_exists, v_drone_cap
    FROM DRONES WHERE DRONE_ID = p_drone_id;

    IF v_drone_exists = 0 THEN
        ROLLBACK;
        SET p_status_code = 404;
        SET p_status_message = CONCAT('Referenced Drone ID ', p_drone_id, ' does not exist.');
        LEAVE proc_label;
    END IF;

    SELECT COUNT(*), COALESCE(MAX(STATUS), '') INTO v_pilot_exists, v_pilot_status
    FROM PILOTS WHERE PILOT_ID = p_pilot_id;

    IF v_pilot_exists = 0 THEN
        ROLLBACK;
        SET p_status_code = 404;
        SET p_status_message = CONCAT('Referenced Pilot ID ', p_pilot_id, ' does not exist.');
        LEAVE proc_label;
    END IF;

    SELECT COUNT(*), COALESCE(MAX(VENDOR_ID), 0), COALESCE(MAX(WEIGHT), 0)
    INTO v_pkg_exists, v_pkg_vendor, v_pkg_weight
    FROM PACKAGES WHERE PACKAGE_ID = p_package_id;

    IF v_pkg_exists = 0 THEN
        ROLLBACK;
        SET p_status_code = 404;
        SET p_status_message = CONCAT('Referenced Package ID ', p_package_id, ' does not exist.');
        LEAVE proc_label;
    END IF;

    SELECT COUNT(*) INTO v_route_exists
    FROM ROUTES WHERE ROUTE_ID = p_route_id;

    IF v_route_exists = 0 THEN
        ROLLBACK;
        SET p_status_code = 404;
        SET p_status_message = CONCAT('Referenced Route ID ', p_route_id, ' does not exist.');
        LEAVE proc_label;
    END IF;

    -- 2. Vendor Ownership Guard
    IF v_pkg_vendor != p_vendor_id THEN
        ROLLBACK;
        SET p_status_code = 403;
        SET p_status_message = 'Forbidden: Package belongs to another vendor.';
        LEAVE proc_label;
    END IF;

    -- 3. Pilot Duty Guard
    IF v_pilot_status = 'OFF_DUTY' THEN
        ROLLBACK;
        SET p_status_code = 400;
        SET p_status_message = 'Cannot assign an OFF_DUTY pilot to a mission.';
        LEAVE proc_label;
    END IF;

    IF v_pilot_status != 'AVAILABLE' THEN
        ROLLBACK;
        SET p_status_code = 400;
        SET p_status_message = CONCAT('Pilot is currently in status \'', v_pilot_status, '\' and not AVAILABLE.');
        LEAVE proc_label;
    END IF;

    -- 4. Payload Capacity Invariant
    IF v_pkg_weight > v_drone_cap THEN
        ROLLBACK;
        SET p_status_code = 400;
        SET p_status_message = CONCAT('Package weight (', v_pkg_weight, ' kg) exceeds drone payload capacity (', v_drone_cap, ' kg).');
        LEAVE proc_label;
    END IF;

    -- 5. Battery Availability & Health Guard
    SELECT COUNT(*) INTO v_good_batteries
    FROM BATTERIES
    WHERE DRONE_ID = p_drone_id AND STATUS = 'GOOD';

    IF v_good_batteries = 0 THEN
        ROLLBACK;
        SET p_status_code = 400;
        SET p_status_message = CONCAT('Drone #', p_drone_id, ' has no healthy battery available (STATUS=\'GOOD\').');
        LEAVE proc_label;
    END IF;

    -- 6. Battery Charging Check
    SELECT COUNT(*) INTO v_charging_batteries
    FROM CHARGING_SESSIONS cs
    JOIN BATTERIES b ON cs.BATTERY_ID = b.BATTERY_ID
    WHERE b.DRONE_ID = p_drone_id AND cs.END_TIME IS NULL;

    IF v_charging_batteries > 0 THEN
        ROLLBACK;
        SET p_status_code = 400;
        SET p_status_message = CONCAT('Drone #', p_drone_id, ' currently has a battery in an active charging session.');
        LEAVE proc_label;
    END IF;

    -- 7. Grounded Maintenance Guard (Latest condition check)
    SELECT STATUS INTO v_latest_maint_status
    FROM MAINTENACE
    WHERE DRONE_ID = p_drone_id
    ORDER BY REPAIR_DATE DESC, MAINTENANCE_ID DESC
    LIMIT 1;

    IF v_latest_maint_status = 'BAD' THEN
        ROLLBACK;
        SET p_status_code = 400;
        SET p_status_message = CONCAT('Drone #', p_drone_id, ' is grounded under active maintenance (latest status is BAD).');
        LEAVE proc_label;
    END IF;

    -- 8. Double-Booking Checks for active (IDLE, ONGOING) missions
    SELECT COUNT(*) INTO v_conflict_count
    FROM MISSIONS
    WHERE DRONE_ID = p_drone_id AND MISSION_STATUS IN ('IDLE', 'ONGOING');

    IF v_conflict_count > 0 THEN
        ROLLBACK;
        SET p_status_code = 400;
        SET p_status_message = CONCAT('Drone ID ', p_drone_id, ' is already assigned to an active mission.');
        LEAVE proc_label;
    END IF;

    SELECT COUNT(*) INTO v_conflict_count
    FROM MISSIONS
    WHERE PILOT_ID = p_pilot_id AND MISSION_STATUS IN ('IDLE', 'ONGOING');

    IF v_conflict_count > 0 THEN
        ROLLBACK;
        SET p_status_code = 400;
        SET p_status_message = CONCAT('Pilot ID ', p_pilot_id, ' is already assigned to an active mission.');
        LEAVE proc_label;
    END IF;

    SELECT COUNT(*) INTO v_conflict_count
    FROM MISSIONS
    WHERE PACKAGE_ID = p_package_id AND MISSION_STATUS IN ('IDLE', 'ONGOING');

    IF v_conflict_count > 0 THEN
        ROLLBACK;
        SET p_status_code = 400;
        SET p_status_message = CONCAT('Package ID ', p_package_id, ' is already assigned to an active mission.');
        LEAVE proc_label;
    END IF;

    -- 9. Determine Mission ID
    IF p_custom_mission_id IS NOT NULL AND p_custom_mission_id > 0 THEN
        SELECT COUNT(*) INTO v_conflict_count
        FROM MISSIONS WHERE MISSION_ID = p_custom_mission_id;

        IF v_conflict_count > 0 THEN
            ROLLBACK;
            SET p_status_code = 400;
            SET p_status_message = CONCAT('Mission ID ', p_custom_mission_id, ' already exists.');
            LEAVE proc_label;
        END IF;
        SET v_target_mission_id = p_custom_mission_id;
    ELSE
        SELECT COALESCE(MAX(MISSION_ID), 0) + 1 INTO v_target_mission_id FROM MISSIONS;
    END IF;

    -- 10. Atomic Insertion & Package Reservation
    INSERT INTO MISSIONS (MISSION_ID, DRONE_ID, PILOT_ID, PACKAGE_ID, ROUTE_ID, MISSION_STATUS, START_TIME, END_TIME)
    VALUES (v_target_mission_id, p_drone_id, p_pilot_id, p_package_id, p_route_id, 'IDLE', NULL, NULL);

    UPDATE PACKAGES
    SET STATUS = 'NOT AVAILABLE'
    WHERE PACKAGE_ID = p_package_id;

    COMMIT;

    SET p_mission_id = v_target_mission_id;
    SET p_status_code = 200;
    SET p_status_message = 'Mission successfully created in IDLE state.';
END//

DELIMITER ;

-- Refine sp_start_mission with latest maintenance condition check
DROP PROCEDURE IF EXISTS sp_start_mission;

DELIMITER //

CREATE PROCEDURE sp_start_mission(
    IN p_mission_id INT,
    IN p_vendor_id INT,
    OUT p_status_code INT,
    OUT p_status_message VARCHAR(255)
)
proc_label: BEGIN
    DECLARE v_current_status VARCHAR(20);
    DECLARE v_drone_id INT;
    DECLARE v_pilot_id INT;
    DECLARE v_package_id INT;
    DECLARE v_pkg_vendor INT;
    DECLARE v_pilot_status VARCHAR(20);
    DECLARE v_good_batteries INT DEFAULT 0;
    DECLARE v_charging_batteries INT DEFAULT 0;
    DECLARE v_latest_maint_status VARCHAR(10) DEFAULT 'GOOD';

    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        SET p_status_code = 500;
        SET p_status_message = 'Database error during mission launch transaction.';
    END;

    START TRANSACTION;

    -- Lock mission row
    SELECT m.MISSION_STATUS, m.DRONE_ID, m.PILOT_ID, m.PACKAGE_ID, p.VENDOR_ID
    INTO v_current_status, v_drone_id, v_pilot_id, v_package_id, v_pkg_vendor
    FROM MISSIONS m
    JOIN PACKAGES p ON m.PACKAGE_ID = p.PACKAGE_ID
    WHERE m.MISSION_ID = p_mission_id
    FOR UPDATE;

    IF v_current_status IS NULL THEN
        ROLLBACK;
        SET p_status_code = 404;
        SET p_status_message = CONCAT('Mission ID ', p_mission_id, ' does not exist.');
        LEAVE proc_label;
    END IF;

    -- Vendor ownership
    IF v_pkg_vendor != p_vendor_id THEN
        ROLLBACK;
        SET p_status_code = 403;
        SET p_status_message = 'Forbidden: Mission does not belong to your vendor organization.';
        LEAVE proc_label;
    END IF;

    -- State machine: Only IDLE can transition to ONGOING
    IF v_current_status != 'IDLE' THEN
        ROLLBACK;
        SET p_status_code = 400;
        SET p_status_message = CONCAT('Cannot start mission: Current status is \'', v_current_status, '\' (must be IDLE).');
        LEAVE proc_label;
    END IF;

    -- Re-verify Pilot
    SELECT STATUS INTO v_pilot_status
    FROM PILOTS WHERE PILOT_ID = v_pilot_id FOR UPDATE;

    IF v_pilot_status = 'OFF_DUTY' THEN
        ROLLBACK;
        SET p_status_code = 400;
        SET p_status_message = 'Cannot start mission: Assigned pilot has gone OFF_DUTY.';
        LEAVE proc_label;
    END IF;

    -- Re-verify Battery Health
    SELECT COUNT(*) INTO v_good_batteries
    FROM BATTERIES
    WHERE DRONE_ID = v_drone_id AND STATUS = 'GOOD';

    IF v_good_batteries = 0 THEN
        ROLLBACK;
        SET p_status_code = 400;
        SET p_status_message = 'Cannot start mission: Assigned drone has no healthy battery.';
        LEAVE proc_label;
    END IF;

    -- Re-verify Charging
    SELECT COUNT(*) INTO v_charging_batteries
    FROM CHARGING_SESSIONS cs
    JOIN BATTERIES b ON cs.BATTERY_ID = b.BATTERY_ID
    WHERE b.DRONE_ID = v_drone_id AND cs.END_TIME IS NULL;

    IF v_charging_batteries > 0 THEN
        ROLLBACK;
        SET p_status_code = 400;
        SET p_status_message = 'Cannot start mission: Assigned drone currently has an active charging session.';
        LEAVE proc_label;
    END IF;

    -- Re-verify Maintenance (Latest status)
    SELECT STATUS INTO v_latest_maint_status
    FROM MAINTENACE
    WHERE DRONE_ID = v_drone_id
    ORDER BY REPAIR_DATE DESC, MAINTENANCE_ID DESC
    LIMIT 1;

    IF v_latest_maint_status = 'BAD' THEN
        ROLLBACK;
        SET p_status_code = 400;
        SET p_status_message = 'Cannot start mission: Assigned drone is grounded under active maintenance (status is BAD).';
        LEAVE proc_label;
    END IF;

    -- Transition atomically
    UPDATE MISSIONS
    SET MISSION_STATUS = 'ONGOING', START_TIME = NOW()
    WHERE MISSION_ID = p_mission_id;

    UPDATE PILOTS
    SET STATUS = 'ON_MISSION'
    WHERE PILOT_ID = v_pilot_id;

    COMMIT;

    SET p_status_code = 200;
    SET p_status_message = 'Mission launched successfully. Status is now ONGOING.';
END//

DELIMITER ;
