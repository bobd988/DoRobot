# DoRobot Safety Improvements and Issue Resolution

This document tracks critical issues encountered during development and their solutions, focusing on safety, reliability, and system integrity.

---

## 2025-12-26: Joint Mapping Mismatch and Motor Configuration Issues

### Problem 1: Incorrect Joint Correspondence During Teleoperation

**Severity:** Critical - System functioned but with incorrect joint mapping

**Symptoms:**
- Teleoperation connection succeeded and data transmission worked
- Leader arm movements were transmitted to follower arm
- However, joints moved incorrectly: wrong joints responded to leader movements
- Example: Moving leader's shoulder_pan caused follower's joint_1 to move instead of joint_0

**Root Cause:**
- Leader arm used semantic joint names (shoulder_pan, shoulder_lift, elbow_flex, wrist_flex, wrist_roll)
- Follower arm (Piper) uses indexed joint names (joint_0, joint_1, joint_2, joint_3, joint_4, joint_5)
- Joint data was transmitted in dictionary order, causing misalignment
- Leader's shoulder_pan (ID 1) was mapped to follower's joint_1 instead of joint_0
- This created an off-by-one error in joint correspondence

**Impact:**
- Unsafe teleoperation: operator's intended movements resulted in different actual movements
- Risk of collision or damage due to unexpected joint behavior
- Difficult to control the robot arm precisely
- Potential for operator confusion and accidents

**Solution:**
1. Renamed all leader arm joints from semantic names to indexed names (joint_0 through joint_5)
2. Added missing joint_0 (Motor ID 0) to configuration
3. Updated calibration file with indexed joint names
4. Modified main.py and calibrate.py to use indexed naming
5. Removed placeholder joint insertion logic (no longer needed with 7 motors)

**Verification:**
- Created diagnostic scripts to verify joint count and mapping
- Tested teleoperation with new configuration
- Confirmed 1:1 joint correspondence between leader and follower

**Prevention Measures:**
- Use consistent naming conventions across all arm types
- Always verify joint correspondence before teleoperation
- Add diagnostic tools to validate joint mapping
- Document joint naming conventions clearly

---

### Problem 2: Missing Motor ID 0 in Configuration

**Severity:** High - One motor was not configured or controlled

**Symptoms:**
- Leader arm has 7 physical motors (ID 0-6)
- Only 6 motors were configured in software (ID 1-6)
- Motor ID 0 was physically present but not accessible
- System worked with 6 motors but lacked full control

**Root Cause:**
- Initial configuration assumed motor IDs started at 1
- Motor ID 0 was overlooked during setup
- Calibration file did not include joint_0 entry
- Motor definitions in main.py and calibrate.py started at ID 1

**Impact:**
- Incomplete control of leader arm
- One degree of freedom was unavailable
- Potential for unexpected behavior if motor ID 0 was accidentally activated
- Reduced functionality of teleoperation system

**Solution:**
1. Added joint_0 with Motor ID 0 to calibration file
2. Updated motor definitions in main.py and calibrate.py to include joint_0
3. Calibrated joint_0 with appropriate homing_offset and range values
4. Created diagnostic scripts to detect all motors including ID 0

**Verification:**
- Used detailed_scan.py to scan motor IDs 0-20
- Confirmed motor ID 0 responds to commands
- Verified joint_0 appears in joint position readings
- Tested full 7-motor control during teleoperation

**Prevention Measures:**
- Always scan full motor ID range (0-255) during initial setup
- Document expected motor count and IDs
- Create diagnostic tools to verify all motors are configured
- Add validation checks to ensure motor count matches expected value

---

### Problem 3: Lack of Diagnostic and Calibration Tools

**Severity:** Medium - Made troubleshooting difficult and time-consuming

**Symptoms:**
- No easy way to detect which motors are connected
- Difficult to verify motor IDs and positions
- Manual calibration process was error-prone
- No tools to check joint correspondence

**Root Cause:**
- System lacked comprehensive diagnostic utilities
- Calibration process required manual alignment and calculation
- No automated tools for motor detection
- Limited visibility into system state

**Impact:**
- Increased setup and debugging time
- Higher risk of configuration errors
- Difficult to diagnose joint mapping issues
- Manual calibration prone to human error

**Solution:**
Created six diagnostic and calibration scripts:

1. **detailed_scan.py**: Comprehensive motor detection (ID 0-20)
2. **scan_all_motors.py**: Quick motor scan (ID 1-15)
3. **scan_all_ports.py**: Multi-port motor detection
4. **detect_leader_joints.py**: Verify joint configuration
5. **show_leader_position.py**: Real-time position monitoring and alignment checking
6. **sync_leader_calibration.py**: Automatic calibration synchronization

**Verification:**
- All scripts tested and working correctly
- Scripts successfully detected motor ID 0
- Automatic calibration script correctly calculated homing_offset values
- Position monitoring script helped identify joint mapping issues

**Prevention Measures:**
- Maintain comprehensive diagnostic tool suite
- Document diagnostic procedures in release notes
- Add automated validation checks to startup sequence
- Create troubleshooting guides referencing diagnostic tools

---

## Key Lessons Learned

### 1. Naming Conventions Matter
- Consistent naming across system components is critical for correct operation
- Semantic names (shoulder_pan) can cause confusion when interfacing with indexed systems
- Always document naming conventions and mapping rules

### 2. Complete Motor Discovery
- Never assume motor ID ranges
- Always scan full ID space during initial setup
- Verify motor count matches physical hardware

### 3. Diagnostic Tools Are Essential
- Invest time in creating comprehensive diagnostic utilities
- Diagnostic tools pay for themselves during troubleshooting
- Automated tools reduce human error and setup time

### 4. Verify Before Operating
- Always verify joint correspondence before teleoperation
- Use diagnostic tools to validate system state
- Don't assume configuration is correct without verification

### 5. Document Everything
- Clear documentation prevents repeated mistakes
- Release notes should include troubleshooting context
- Safety improvements should be tracked and reviewed

---

## Safety Checklist for Teleoperation Setup

Before starting teleoperation, verify:

- [ ] All motors detected (7 motors for SO101 leader arm)
- [ ] Joint names match between leader and follower arms
- [ ] Calibration file includes all joints (joint_0 through joint_5 + gripper)
- [ ] Position alignment within acceptable threshold (< 40° difference)
- [ ] Diagnostic scripts run successfully
- [ ] Joint correspondence verified (leader joint_0 → follower joint_0, etc.)
- [ ] Emergency stop procedures tested and understood

---

## Future Improvements

### Recommended Enhancements:
1. Add automated joint correspondence validation at startup
2. Implement runtime checks for joint mapping correctness
3. Create visual feedback for joint positions during teleoperation
4. Add configuration validation tool to check for common errors
5. Implement safety limits to prevent dangerous joint positions
6. Add logging for joint commands and responses
7. Create automated test suite for joint mapping verification

### Monitoring and Alerts:
1. Alert if motor count doesn't match expected value
2. Warn if joint position differences exceed threshold
3. Log calibration changes for audit trail
4. Monitor for communication errors and retry failures
5. Track joint position drift over time

---

## References

- **Release Notes:** docs/RELEASE.md v0.2.134
- **Calibration File:** operating_platform/robot/components/arm_normal_so101_v1/.calibration/SO101-leader.json
- **Diagnostic Scripts:** scripts/detailed_scan.py, scripts/detect_leader_joints.py, scripts/scan_all_motors.py, scripts/scan_all_ports.py, scripts/show_leader_position.py, scripts/sync_leader_calibration.py
