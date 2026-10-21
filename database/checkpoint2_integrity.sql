-- =====================================================================
-- Drone Delivery Management System - Checkpoint 2 Integrity Script
-- Database Name: DRONEDELIVERY
-- Purpose: Stored Procedures, Triggers, and Constraints for Delivery
--          Lifecycle Integrity and Atomic State Transitions.
-- Repeatability: Idempotent (uses DROP IF EXISTS before CREATE).
-- =====================================================================

USE DRONEDELIVERY;

-- ---------------------------------------------------------------------
-- 0. Schema Alignment & Discrepancy Resolution
-- Ensure PACKAGES.STATUS and MISSIONS.MISSION_STATUS support both
-- classic DDL values and granular lifecycle values without truncation.
-- ---------------------------------------------------------------------
ALTER TABLE PACKAGES MODIFY COLUMN STATUS ENUM(
    'AVAILABLE',
    'NOT AVAILABLE',
    'REQUESTED',
    'READY',
    'ASSIGNED',
    'IN_TRANSIT',
    'DELIVERED',
    'CANCELLED'
) NOT NULL DEFAULT 'AVAILABLE';

ALTER TABLE MISSIONS MODIFY COLUMN MISSION_STATUS ENUM(
    'IDLE',
    'ONGOING',
    'OVER',
    'CANCELLED'
) NOT NULL DEFAULT 'IDLE';

-- =====================================================================
-- TRIGGERS (At least 3 dedicated integrity guards)
-- =====================================================================

-- ---------------------------------------------------------------------
-- Trigger 1: Mission Payload & Double-Booking Guard
-- Enforces:
-- 1. PACKAGES.WEIGHT <= DRONES.PAYLOAD_CAP
-- 2. No overlapping active mission for the same drone, pilot, or package
-- ---------------------------------------------------------------------
DROP TRIGGER IF EXISTS trg_check_mission_payload_assignment;

DELIMITER //

CREATE TRIGGER trg_check_mission_payload_assignment
BEFORE INSERT ON MISSIONS
FOR EACH ROW
BEGIN
    DECLARE v_drone_cap INT;
    DECLARE v_pkg_weight INT;
    DECLARE v_active_count INT;

    -- Fetch drone payload capacity
    SELECT PAYLOAD_CAP INTO v_drone_cap
    FROM DRONES
    WHERE DRONE_ID = NEW.DRONE_ID;

    -- Fetch package weight
    SELECT WEIGHT INTO v_pkg_weight
    FROM PACKAGES
    WHERE PACKAGE_ID = NEW.PACKAGE_ID;

    -- 1. Payload capacity invariant
    IF v_pkg_weight IS NOT NULL AND v_drone_cap IS NOT NULL THEN
        IF v_pkg_weight > v_drone_cap THEN
            SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Integrity Violation: Package weight exceeds drone payload capacity.';
        END IF;
    END IF;

    -- Double-booking checks for active missions
    IF NEW.MISSION_STATUS IN ('IDLE', 'ONGOING') THEN
        -- 2. Prevent drone double-booking on active missions
        SELECT COUNT(*) INTO v_active_count
        FROM MISSIONS
        WHERE DRONE_ID = NEW.DRONE_ID
          AND MISSION_STATUS IN ('IDLE', 'ONGOING');

        IF v_active_count > 0 THEN
            SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Integrity Violation: Assigned Drone is already reserved by another active mission.';
        END IF;

        -- 3. Prevent pilot double-booking on active missions
        SELECT COUNT(*) INTO v_active_count
        FROM MISSIONS
        WHERE PILOT_ID = NEW.PILOT_ID
          AND MISSION_STATUS IN ('IDLE', 'ONGOING');

        IF v_active_count > 0 THEN
            SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Integrity Violation: Assigned Pilot is already reserved by another active mission.';
        END IF;

        -- 4. Prevent package double-booking on active missions
        SELECT COUNT(*) INTO v_active_count
        FROM MISSIONS
        WHERE PACKAGE_ID = NEW.PACKAGE_ID
          AND MISSION_STATUS IN ('IDLE', 'ONGOING');

        IF v_active_count > 0 THEN
            SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Integrity Violation: Assigned Package is already reserved by another active mission.';
        END IF;
    END IF;
END//

DELIMITER ;

-- ---------------------------------------------------------------------
-- Trigger 2: Mission Lifecycle State Transition Guard
-- Enforces:
-- 1. Terminal state OVER cannot transition to any other status
-- 2. Terminal state CANCELLED cannot transition to any other status
-- 3. IDLE missions may only transition to ONGOING or CANCELLED
-- 4. ONGOING missions may only transition to OVER
-- ---------------------------------------------------------------------
DROP TRIGGER IF EXISTS trg_check_mission_transition;

DELIMITER //

CREATE TRIGGER trg_check_mission_transition
BEFORE UPDATE ON MISSIONS
FOR EACH ROW
BEGIN
    -- Disallow changes to finished missions
    IF OLD.MISSION_STATUS = 'OVER' AND NEW.MISSION_STATUS != 'OVER' THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Lifecycle Violation: Completed (OVER) missions cannot be altered.';
    END IF;

    IF OLD.MISSION_STATUS = 'CANCELLED' AND NEW.MISSION_STATUS != 'CANCELLED' THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Lifecycle Violation: Cancelled missions cannot be altered.';
    END IF;

    -- Transition rules from IDLE
    IF OLD.MISSION_STATUS = 'IDLE' THEN
        IF NEW.MISSION_STATUS NOT IN ('IDLE', 'ONGOING', 'CANCELLED') THEN
            SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Lifecycle Violation: IDLE missions may only transition to ONGOING or CANCELLED.';
        END IF;
    END IF;

    -- Transition rules from ONGOING
    IF OLD.MISSION_STATUS = 'ONGOING' THEN
        IF NEW.MISSION_STATUS NOT IN ('ONGOING', 'OVER') THEN
            SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Lifecycle Violation: ONGOING missions may only transition to OVER.';
        END IF;
    END IF;
END//

DELIMITER ;

-- ---------------------------------------------------------------------
-- Trigger 3: Charging Safety Guard (Drone Not Flying)
-- Enforces: A battery cannot begin a charging session if its assigned
-- drone is actively flying an ONGOING mission.
-- ---------------------------------------------------------------------
DROP TRIGGER IF EXISTS trg_check_charging_drone_not_flying;

DELIMITER //

CREATE TRIGGER trg_check_charging_drone_not_flying
BEFORE INSERT ON CHARGING_SESSIONS
FOR EACH ROW
BEGIN
    DECLARE v_drone_id INT;
    DECLARE v_flying_count INT;

    -- Find drone associated with battery
    SELECT DRONE_ID INTO v_drone_id
    FROM BATTERIES
    WHERE BATTERY_ID = NEW.BATTERY_ID;

    IF v_drone_id IS NOT NULL THEN
        SELECT COUNT(*) INTO v_flying_count
        FROM MISSIONS
        WHERE DRONE_ID = v_drone_id
          AND MISSION_STATUS = 'ONGOING';

        IF v_flying_count > 0 THEN
            SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Safety Violation: Cannot initiate battery charging while assigned drone is actively flying an ONGOING mission.';
        END IF;
    END IF;
END//

DELIMITER ;

-- ---------------------------------------------------------------------
-- Trigger 4: Mission Start Safety Guard (Drone Not Charging)
-- Enforces: A mission cannot transition to ONGOING if any battery
-- belonging to its drone is currently in an active charging session.
-- ---------------------------------------------------------------------
DROP TRIGGER IF EXISTS trg_check_mission_start_drone_not_charging;

DELIMITER //

CREATE TRIGGER trg_check_mission_start_drone_not_charging
BEFORE UPDATE ON MISSIONS
FOR EACH ROW
BEGIN
    DECLARE v_active_charging INT;

    -- Only check on transition from IDLE to ONGOING
    IF OLD.MISSION_STATUS = 'IDLE' AND NEW.MISSION_STATUS = 'ONGOING' THEN
        SELECT COUNT(*) INTO v_active_charging
        FROM CHARGING_SESSIONS cs
        JOIN BATTERIES b ON cs.BATTERY_ID = b.BATTERY_ID
        WHERE b.DRONE_ID = NEW.DRONE_ID
          AND cs.END_TIME IS NULL;

        IF v_active_charging > 0 THEN
            SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Safety Violation: Cannot launch drone on a mission while one of its batteries is actively charging.';
        END IF;
    END IF;
END//

DELIMITER ;

-- =====================================================================
-- STORED PROCEDURES (At least 3 dedicated business workflows)
-- =====================================================================

-- ---------------------------------------------------------------------
-- Stored Procedure 1: sp_create_mission
-- Validates assignments (Vendor ownership, payload capacity, active
-- mission conflicts, battery health, charging state, maintenance state)
-- and inserts a new IDLE mission atomically.
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
    DECLARE v_bad_maintenance INT DEFAULT 0;
    DECLARE v_conflict_count INT DEFAULT 0;
    DECLARE v_target_mission_id INT;

    -- Error handler for unexpected SQL exceptions
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

    -- 2. Vendor Package Ownership Guard
    IF p_vendor_id IS NOT NULL AND v_pkg_vendor != p_vendor_id THEN
        ROLLBACK;
        SET p_status_code = 403;
        SET p_status_message = 'Access Denied: You cannot dispatch packages belonging to another vendor.';
        LEAVE proc_label;
    END IF;

    -- 3. Pilot Availability Guard
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

    -- 7. Grounded Maintenance Guard
    SELECT COUNT(*) INTO v_bad_maintenance
    FROM MAINTENACE
    WHERE DRONE_ID = p_drone_id AND STATUS = 'BAD';

    IF v_bad_maintenance > 0 THEN
        ROLLBACK;
        SET p_status_code = 400;
        SET p_status_message = CONCAT('Drone #', p_drone_id, ' is grounded under active maintenance (STATUS=\'BAD\').');
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

    -- Reserve package
    UPDATE PACKAGES
    SET STATUS = 'NOT AVAILABLE'
    WHERE PACKAGE_ID = p_package_id;

    COMMIT;

    SET p_mission_id = v_target_mission_id;
    SET p_status_code = 200;
    SET p_status_message = 'Mission created successfully!';
END//

DELIMITER ;

-- ---------------------------------------------------------------------
-- Stored Procedure 2: sp_start_mission
-- Revalidates all pre-flight invariants (Pilot status, drone battery,
-- charging, and maintenance) and transitions the mission to ONGOING
-- and pilot to ON_MISSION atomically.
-- ---------------------------------------------------------------------
DROP PROCEDURE IF EXISTS sp_start_mission;

DELIMITER //

CREATE PROCEDURE sp_start_mission(
    IN p_mission_id INT,
    IN p_vendor_id INT,
    OUT p_status_code INT,
    OUT p_status_message VARCHAR(255)
)
proc_label: BEGIN
    DECLARE v_mission_exists INT DEFAULT 0;
    DECLARE v_drone_id INT;
    DECLARE v_pilot_id INT;
    DECLARE v_package_id INT;
    DECLARE v_pkg_vendor INT;
    DECLARE v_mission_status VARCHAR(20);
    DECLARE v_pilot_status VARCHAR(20);
    DECLARE v_charging_count INT DEFAULT 0;
    DECLARE v_good_batteries INT DEFAULT 0;
    DECLARE v_bad_maintenance INT DEFAULT 0;

    -- Error handler for unexpected SQL exceptions
    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        SET p_status_code = 500;
        SET p_status_message = 'Database error during mission launch transaction.';
    END;

    START TRANSACTION;

    -- Lock and retrieve mission record
    SELECT COUNT(*), MAX(DRONE_ID), MAX(PILOT_ID), MAX(PACKAGE_ID), MAX(MISSION_STATUS)
    INTO v_mission_exists, v_drone_id, v_pilot_id, v_package_id, v_mission_status
    FROM MISSIONS
    WHERE MISSION_ID = p_mission_id
    FOR UPDATE;

    IF v_mission_exists = 0 OR v_drone_id IS NULL THEN
        ROLLBACK;
        SET p_status_code = 404;
        SET p_status_message = 'Mission not found.';
        LEAVE proc_label;
    END IF;

    -- State precondition: Only IDLE missions can start
    IF v_mission_status != 'IDLE' THEN
        ROLLBACK;
        SET p_status_code = 400;
        SET p_status_message = CONCAT('Cannot start mission in \'', v_mission_status, '\' status. Only IDLE missions can be started.');
        LEAVE proc_label;
    END IF;

    -- Vendor authorization check
    SELECT VENDOR_ID INTO v_pkg_vendor
    FROM PACKAGES
    WHERE PACKAGE_ID = v_package_id;

    IF p_vendor_id IS NOT NULL AND v_pkg_vendor != p_vendor_id THEN
        ROLLBACK;
        SET p_status_code = 403;
        SET p_status_message = 'Access Denied: You cannot start a mission for a package belonging to another vendor.';
        LEAVE proc_label;
    END IF;

    -- Revalidate assigned pilot
    SELECT STATUS INTO v_pilot_status
    FROM PILOTS
    WHERE PILOT_ID = v_pilot_id
    FOR UPDATE;

    IF v_pilot_status = 'OFF_DUTY' THEN
        ROLLBACK;
        SET p_status_code = 400;
        SET p_status_message = 'Assigned pilot is OFF_DUTY and cannot start a flight mission.';
        LEAVE proc_label;
    END IF;

    IF v_pilot_status != 'AVAILABLE' THEN
        ROLLBACK;
        SET p_status_code = 400;
        SET p_status_message = CONCAT('Assigned pilot is not AVAILABLE (Current status: ', v_pilot_status, ').');
        LEAVE proc_label;
    END IF;

    -- Revalidate charging safety
    SELECT COUNT(*) INTO v_charging_count
    FROM CHARGING_SESSIONS cs
    JOIN BATTERIES b ON cs.BATTERY_ID = b.BATTERY_ID
    WHERE b.DRONE_ID = v_drone_id AND cs.END_TIME IS NULL;

    IF v_charging_count > 0 THEN
        ROLLBACK;
        SET p_status_code = 400;
        SET p_status_message = 'Safety Violation: Assigned drone has a battery actively charging.';
        LEAVE proc_label;
    END IF;

    -- Revalidate battery health
    SELECT COUNT(*) INTO v_good_batteries
    FROM BATTERIES
    WHERE DRONE_ID = v_drone_id AND STATUS = 'GOOD';

    IF v_good_batteries = 0 THEN
        ROLLBACK;
        SET p_status_code = 400;
        SET p_status_message = 'Assigned drone does not have a healthy battery.';
        LEAVE proc_label;
    END IF;

    -- Revalidate maintenance status
    SELECT COUNT(*) INTO v_bad_maintenance
    FROM MAINTENACE
    WHERE DRONE_ID = v_drone_id AND STATUS = 'BAD';

    IF v_bad_maintenance > 0 THEN
        ROLLBACK;
        SET p_status_code = 400;
        SET p_status_message = 'Assigned drone is grounded under active maintenance.';
        LEAVE proc_label;
    END IF;

    -- Atomic transition: MISSION -> ONGOING, PILOT -> ON_MISSION
    UPDATE MISSIONS
    SET MISSION_STATUS = 'ONGOING', START_TIME = NOW(), END_TIME = NULL
    WHERE MISSION_ID = p_mission_id;

    UPDATE PILOTS
    SET STATUS = 'ON_MISSION'
    WHERE PILOT_ID = v_pilot_id;

    UPDATE PACKAGES
    SET STATUS = 'NOT AVAILABLE'
    WHERE PACKAGE_ID = v_package_id;

    COMMIT;

    SET p_status_code = 200;
    SET p_status_message = CONCAT('Mission ', p_mission_id, ' started successfully! Pilot status set to ON_MISSION.');
END//

DELIMITER ;

-- ---------------------------------------------------------------------
-- Stored Procedure 3: sp_complete_mission
-- Completes an ONGOING mission atomically:
-- 1. Updates MISSIONS: MISSION_STATUS = 'OVER', END_TIME = NOW()
-- 2. Releases PILOTS: STATUS = 'AVAILABLE'
-- 3. Updates DRONES: LAST_DELIVERY = NOW(), CURR_LOCATION = route.DESTINATION
-- 4. Synchronizes PACKAGES: STATUS = 'NOT AVAILABLE' (delivered)
-- ---------------------------------------------------------------------
DROP PROCEDURE IF EXISTS sp_complete_mission;

DELIMITER //

CREATE PROCEDURE sp_complete_mission(
    IN p_mission_id INT,
    IN p_vendor_id INT,
    OUT p_status_code INT,
    OUT p_status_message VARCHAR(255)
)
proc_label: BEGIN
    DECLARE v_mission_exists INT DEFAULT 0;
    DECLARE v_drone_id INT;
    DECLARE v_pilot_id INT;
    DECLARE v_package_id INT;
    DECLARE v_route_id INT;
    DECLARE v_pkg_vendor INT;
    DECLARE v_mission_status VARCHAR(20);
    DECLARE v_destination VARCHAR(25);

    -- Error handler for unexpected SQL exceptions
    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        SET p_status_code = 500;
        SET p_status_message = 'Database error during mission completion transaction.';
    END;

    START TRANSACTION;

    -- Lock and retrieve mission record
    SELECT COUNT(*), MAX(DRONE_ID), MAX(PILOT_ID), MAX(PACKAGE_ID), MAX(ROUTE_ID), MAX(MISSION_STATUS)
    INTO v_mission_exists, v_drone_id, v_pilot_id, v_package_id, v_route_id, v_mission_status
    FROM MISSIONS
    WHERE MISSION_ID = p_mission_id
    FOR UPDATE;

    IF v_mission_exists = 0 OR v_drone_id IS NULL THEN
        ROLLBACK;
        SET p_status_code = 404;
        SET p_status_message = 'Mission not found.';
        LEAVE proc_label;
    END IF;

    -- State precondition: Only ONGOING missions can be completed
    IF v_mission_status != 'ONGOING' THEN
        ROLLBACK;
        SET p_status_code = 400;
        SET p_status_message = CONCAT('Cannot complete mission in \'', v_mission_status, '\' status. Only ONGOING missions can be completed.');
        LEAVE proc_label;
    END IF;

    -- Vendor authorization check
    SELECT VENDOR_ID INTO v_pkg_vendor
    FROM PACKAGES
    WHERE PACKAGE_ID = v_package_id;

    IF p_vendor_id IS NOT NULL AND v_pkg_vendor != p_vendor_id THEN
        ROLLBACK;
        SET p_status_code = 403;
        SET p_status_message = 'Access Denied: You cannot complete a mission for a package belonging to another vendor.';
        LEAVE proc_label;
    END IF;

    -- Retrieve route destination to update drone location
    SELECT DESTINATION INTO v_destination
    FROM ROUTES
    WHERE ROUTE_ID = v_route_id;

    -- 1. Finalize Mission record
    UPDATE MISSIONS
    SET MISSION_STATUS = 'OVER', END_TIME = NOW()
    WHERE MISSION_ID = p_mission_id;

    -- 2. Release Pilot to AVAILABLE
    UPDATE PILOTS
    SET STATUS = 'AVAILABLE'
    WHERE PILOT_ID = v_pilot_id;

    -- 3. Synchronize Drone: Update LAST_DELIVERY and CURR_LOCATION
    IF v_destination IS NOT NULL AND v_destination != '' THEN
        UPDATE DRONES
        SET LAST_DELIVERY = NOW(), CURR_LOCATION = v_destination
        WHERE DRONE_ID = v_drone_id;
    ELSE
        UPDATE DRONES
        SET LAST_DELIVERY = NOW()
        WHERE DRONE_ID = v_drone_id;
    END IF;

    -- 4. Synchronize Package availability to delivered
    UPDATE PACKAGES
    SET STATUS = 'NOT AVAILABLE'
    WHERE PACKAGE_ID = v_package_id;

    COMMIT;

    SET p_status_code = 200;
    SET p_status_message = CONCAT('Mission ', p_mission_id, ' completed successfully! Drone location updated to ', v_destination, ', and pilot released.');
END//

DELIMITER ;

-- ---------------------------------------------------------------------
-- Stored Procedure 4: sp_cancel_mission
-- Cancels an IDLE mission safely:
-- 1. Transitions MISSIONS: MISSION_STATUS = 'CANCELLED'
-- 2. Restores PACKAGES: STATUS = 'AVAILABLE'
-- 3. Ensures pilot and drone remain unencumbered.
-- ---------------------------------------------------------------------
DROP PROCEDURE IF EXISTS sp_cancel_mission;

DELIMITER //

CREATE PROCEDURE sp_cancel_mission(
    IN p_mission_id INT,
    IN p_vendor_id INT,
    OUT p_status_code INT,
    OUT p_status_message VARCHAR(255)
)
proc_label: BEGIN
    DECLARE v_mission_exists INT DEFAULT 0;
    DECLARE v_package_id INT;
    DECLARE v_pkg_vendor INT;
    DECLARE v_mission_status VARCHAR(20);

    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        SET p_status_code = 500;
        SET p_status_message = 'Database error during mission cancellation transaction.';
    END;

    START TRANSACTION;

    SELECT COUNT(*), MAX(PACKAGE_ID), MAX(MISSION_STATUS)
    INTO v_mission_exists, v_package_id, v_mission_status
    FROM MISSIONS
    WHERE MISSION_ID = p_mission_id
    FOR UPDATE;

    IF v_mission_exists = 0 OR v_package_id IS NULL THEN
        ROLLBACK;
        SET p_status_code = 404;
        SET p_status_message = 'Mission not found.';
        LEAVE proc_label;
    END IF;

    IF v_mission_status != 'IDLE' THEN
        ROLLBACK;
        SET p_status_code = 400;
        SET p_status_message = CONCAT('Cannot cancel mission in \'', v_mission_status, '\' status. Only IDLE missions can be cancelled.');
        LEAVE proc_label;
    END IF;

    SELECT VENDOR_ID INTO v_pkg_vendor
    FROM PACKAGES
    WHERE PACKAGE_ID = v_package_id;

    IF p_vendor_id IS NOT NULL AND v_pkg_vendor != p_vendor_id THEN
        ROLLBACK;
        SET p_status_code = 403;
        SET p_status_message = 'Access Denied: You cannot cancel a mission for a package belonging to another vendor.';
        LEAVE proc_label;
    END IF;

    -- Transition Mission to CANCELLED
    UPDATE MISSIONS
    SET MISSION_STATUS = 'CANCELLED', END_TIME = NOW()
    WHERE MISSION_ID = p_mission_id;

    -- Restore package back to AVAILABLE
    UPDATE PACKAGES
    SET STATUS = 'AVAILABLE'
    WHERE PACKAGE_ID = v_package_id;

    COMMIT;

    SET p_status_code = 200;
    SET p_status_message = CONCAT('Mission ', p_mission_id, ' cancelled successfully. Package restored to AVAILABLE.');
END//

DELIMITER ;
