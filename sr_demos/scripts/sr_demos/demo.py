#!/usr/bin/env python3

# Software License Agreement (BSD License)
# Copyright © 2021-2023 belongs to Shadow Robot Company Ltd.
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without modification,
# are permitted provided that the following conditions are met:
#   1. Redistributions of source code must retain the above copyright notice,
#      this list of conditions and the following disclaimer.
#   2. Redistributions in binary form must reproduce the above copyright notice,
#      this list of conditions and the following disclaimer in the documentation
#      and/or other materials provided with the distribution.
#   3. Neither the name of Shadow Robot Company Ltd nor the names of its contributors
#      may be used to endorse or promote products derived from this software without
#      specific prior written permission.
#
# This software is provided by Shadow Robot Company Ltd "as is" and any express
# or implied warranties, including, but not limited to, the implied warranties of
# merchantability and fitness for a particular purpose are disclaimed. In no event
# shall the copyright holder be liable for any direct, indirect, incidental, special,
# exemplary, or consequential damages (including, but not limited to, procurement of
# substitute goods or services; loss of use, data, or profits; or business interruption)
# however caused and on any theory of liability, whether in contract, strict liability,
# or tort (including negligence or otherwise) arising in any way out of the use of this
# software, even if advised of the possibility of such damage.

import random
import time
from builtins import input
import termios
import tty
import sys
import argparse
from threading import Thread
from math import degrees
import yaml
import rospy
from sr_hand.tactile_receiver import TactileReceiver
from sr_robot_commander.sr_hand_commander import SrHandCommander

SAMPLES_TO_COLLECT = 50
TOUCH_THRESHOLD = 75
CONST_TIME_TO_COMPLETE_DEMO = 15


class TactileReading:
    def __init__(self, hand_commander, demo_joint_states, prefix):
        self.hand_commander = hand_commander
        self.demo_joint_states = demo_joint_states
        self.prefix = prefix

        # Read tactile type
        self.tactile_receiver = TactileReceiver(prefix)
        self.tactile_type = self.tactile_receiver.get_tactile_type()

        if self.get_tactiles() is None:
            rospy.loginfo("You don't have tactile sensors. " +
                          "Talk to your Shadow representative to purchase some " +
                          "or use the keyboard to access this demo.")

        # Initialize values for current tactile values
        self.tactile_values = {"FF": 0, "MF": 0, "RF": 0, "LF": 0, "TH": 0}
        # Zero values in dictionary for tactile sensors (initialized at 0)
        self.reference_tactile_values = dict(self.tactile_values)
        self.zero_tactile_sensors()

    def zero_tactile_sensors(self):
        if self.get_tactiles() is not None:
            rospy.logwarn('\nPLEASE ENSURE THAT THE TACTILE SENSORS ARE NOT PRESSED')
            input('\nPress ENTER to continue...')

            # Collect SAMPLES_TO_COLLECT next samples and average them to filter out possible noise
            accumulator = []
            for _ in range(SAMPLES_TO_COLLECT):
                self.read_tactile_values()
                accumulator.append(self.tactile_values)

            for key in ["FF", "MF", "RF", "LF", "TH"]:
                self.reference_tactile_values[key] = sum(entry[key] for entry in accumulator) / len(accumulator)

            rospy.loginfo('Reference values: ' + str(self.reference_tactile_values))

    def read_tactile_values(self):
        if self.get_tactiles() is not None:
            # Read current state of tactile sensors
            tactile_state = self.tactile_receiver.get_tactile_state()

            if self.tactile_type == "biotac":
                self.tactile_values['FF'] = tactile_state.tactiles[0].pdc
                self.tactile_values['MF'] = tactile_state.tactiles[1].pdc
                self.tactile_values['RF'] = tactile_state.tactiles[2].pdc
                self.tactile_values['LF'] = tactile_state.tactiles[3].pdc
                self.tactile_values['TH'] = tactile_state.tactiles[4].pdc
            elif self.tactile_type == "PST":
                self.tactile_values['FF'] = tactile_state.pressure[0]
                self.tactile_values['MF'] = tactile_state.pressure[1]
                self.tactile_values['RF'] = tactile_state.pressure[2]
                self.tactile_values['LF'] = tactile_state.pressure[3]
                self.tactile_values['TH'] = tactile_state.pressure[4]

    def get_tactiles(self):
        return self.tactile_type

    def confirm_touched(self):
        touched = None
        if self.get_tactiles() is not None:
            self.read_tactile_values()
            for finger in ["FF", "MF", "RF", "LF", "TH"]:
                if self.tactile_values[finger] > self.reference_tactile_values[finger] + TOUCH_THRESHOLD:
                    touched = finger
                    rospy.loginfo(f"{touched} contact")
        return touched


class KeyboardPressDetector:
    def __init__(self, hand_commander, demo_states, tactile_reading, hand_type):
        self.keyboard_pressed = False
        self.hand_commander = hand_commander
        self.demo_states = demo_states
        self.tactile_reading = tactile_reading
        self.hand_type = hand_type

    @staticmethod
    def _get_input():
        file_descriptor = sys.stdin.fileno()
        old_settings = termios.tcgetattr(file_descriptor)
        try:
            tty.setraw(sys.stdin.fileno())
            first_char = sys.stdin.read(1)
        finally:
            termios.tcsetattr(file_descriptor, termios.TCSADRAIN, old_settings)
        return first_char

    def run(self):
        while not rospy.is_shutdown():
            input_val = self._get_input()
            if input_val == "1":
                sequence_th(self.hand_commander, self.demo_states)
            elif input_val == "2":
                sequence_ff(self.hand_commander, self.demo_states)
            elif input_val == "3":
                sequence_mf(self.hand_commander, self.demo_states)
            elif input_val == "4":
                sequence_rf(self.hand_commander, self.demo_states, self.tactile_reading, self.hand_type)
            elif input_val == "5":
                if self.hand_type == 'hand_e':
                    sequence_lf(self.hand_commander, self.demo_states, self.tactile_reading)
                else:
                    rospy.logerr("This demo only works for a 5-fingered Hand E. Please try demos 1-4")
            elif input_val == "6":
                rospy.signal_shutdown("Ending demo as key 6 has been pressed.")
                sys.exit(0)
            rospy.sleep(0.05)


def sequence_th(hand_commander, joint_states_config):
    rospy.loginfo("TH demo started")

    rospy.sleep(0.5)
    execute_command_check(hand_commander, joint_states_config, 'start_pos', 1.5, 1.5)

    rospy.loginfo("TH demo completed")


def sequence_ff(hand_commander, joint_states_config):
    rospy.loginfo("FF demo started")

    rospy.sleep(1)
    sequence_ff_commands(hand_commander, joint_states_config)

    rospy.loginfo("FF demo completed")


def sequence_ff_commands(hand_commander, joint_states_config):
    execute_command_check(hand_commander, joint_states_config, 'store_3', 1.1, 1.1)
    execute_command_check(hand_commander, joint_states_config, 'start_pos', 1.1, 1.1)
    execute_command_check(hand_commander, joint_states_config, 'flex_ff', 1.1, 1.0)
    execute_command_check(hand_commander, joint_states_config, 'ext_ff', 1.1, 1.0)
    execute_command_check(hand_commander, joint_states_config, 'flex_mf', 1.1, 1.0)
    execute_command_check(hand_commander, joint_states_config, 'ext_mf', 1.1, 1.0)
    execute_command_check(hand_commander, joint_states_config, 'flex_rf', 1.1, 1.0)
    execute_command_check(hand_commander, joint_states_config, 'ext_rf', 1.1, 1.0)
    execute_command_check(hand_commander, joint_states_config, 'flex_lf', 1.1, 1.0)
    execute_command_check(hand_commander, joint_states_config, 'ext_lf', 1.1, 1.0)
    execute_command_check(hand_commander, joint_states_config, 'flex_th_1', 1, 0.7)
    execute_command_check(hand_commander, joint_states_config, 'flex_th_2', 1, 0.7)
    execute_command_check(hand_commander, joint_states_config, 'ext_th_1', 1.5, 1.5)
    execute_command_check(hand_commander, joint_states_config, 'ext_th_2', 0.5, 0.5)
    execute_command_check(hand_commander, joint_states_config, 'l_ext_lf', 0.5, 0.5)
    execute_command_check(hand_commander, joint_states_config, 'l_ext_rf', 0.5, 0.5)
    execute_command_check(hand_commander, joint_states_config, 'l_ext_mf', 0.5, 0.5)
    execute_command_check(hand_commander, joint_states_config, 'l_ext_ff', 0.5, 0.5)
    execute_command_check(hand_commander, joint_states_config, 'l_int_all', 0.5, 0.5)
    execute_command_check(hand_commander, joint_states_config, 'l_ext_all', 0.5, 0.5)
    execute_command_check(hand_commander, joint_states_config, 'l_int_ff', 0.5, 0.5)
    execute_command_check(hand_commander, joint_states_config, 'l_int_mf', 0.5, 0.5)
    execute_command_check(hand_commander, joint_states_config, 'l_int_rf', 0.5, 0.5)
    execute_command_check(hand_commander, joint_states_config, 'l_int_lf', 0.5, 0.5)
    execute_command_check(hand_commander, joint_states_config, 'l_zero_all', 0.5, 0.5)
    execute_command_check(hand_commander, joint_states_config, 'l_spock', 0.5, 0.5)
    execute_command_check(hand_commander, joint_states_config, 'l_zero_all', 0.5, 0.5)
    execute_command_check(hand_commander, joint_states_config, 'pre_ff_ok', 1.0, 1.0)
    execute_command_check(hand_commander, joint_states_config, 'ff_ok', 0.9, 0.7)
    execute_command_check(hand_commander, joint_states_config, 'ff2mf_ok', 0.4, 0.5)
    execute_command_check(hand_commander, joint_states_config, 'mf_ok', 0.9, 0.7)
    execute_command_check(hand_commander, joint_states_config, 'mf2rf_ok', 0.4, 0.5)
    execute_command_check(hand_commander, joint_states_config, 'rf_ok', 0.9, 0.7)
    execute_command_check(hand_commander, joint_states_config, 'rf2lf_ok', 0.4, 0.5)
    execute_command_check(hand_commander, joint_states_config, 'lf_ok', 0.9, 0.7)
    execute_command_check(hand_commander, joint_states_config, 'start_pos', 1.0, 1.0)
    execute_command_check(hand_commander, joint_states_config, 'flex_ff', 0.2, 0.2)
    execute_command_check(hand_commander, joint_states_config, 'flex_mf', 0.2, 0.2)
    execute_command_check(hand_commander, joint_states_config, 'flex_rf', 0.2, 0.2)
    execute_command_check(hand_commander, joint_states_config, 'flex_lf', 0.2, 0.2)
    execute_command_check(hand_commander, joint_states_config, 'ext_ff', 0.2, 0.2)
    execute_command_check(hand_commander, joint_states_config, 'ext_mf', 0.2, 0.2)
    execute_command_check(hand_commander, joint_states_config, 'ext_rf', 0.2, 0.2)
    execute_command_check(hand_commander, joint_states_config, 'ext_lf', 0.2, 0.2)
    execute_command_check(hand_commander, joint_states_config, 'flex_ff', 0.2, 0.2)
    execute_command_check(hand_commander, joint_states_config, 'flex_mf', 0.2, 0.2)
    execute_command_check(hand_commander, joint_states_config, 'flex_rf', 0.2, 0.2)
    execute_command_check(hand_commander, joint_states_config, 'flex_lf', 0.2, 0.2)
    execute_command_check(hand_commander, joint_states_config, 'ext_ff', 0.2, 0.2)
    execute_command_check(hand_commander, joint_states_config, 'ext_mf', 0.2, 0.2)
    execute_command_check(hand_commander, joint_states_config, 'ext_rf', 0.2, 0.2)
    execute_command_check(hand_commander, joint_states_config, 'ext_lf', 0.2, 0.2)
    execute_command_check(hand_commander, joint_states_config, 'flex_ff', 0.2, 0.2)
    execute_command_check(hand_commander, joint_states_config, 'flex_mf', 0.2, 0.2)
    execute_command_check(hand_commander, joint_states_config, 'flex_rf', 0.2, 0.2)
    execute_command_check(hand_commander, joint_states_config, 'flex_lf', 0.2, 0.2)
    execute_command_check(hand_commander, joint_states_config, 'ext_ff', 0.2, 0.2)
    execute_command_check(hand_commander, joint_states_config, 'ext_mf', 0.2, 0.2)
    execute_command_check(hand_commander, joint_states_config, 'ext_rf', 0.2, 0.2)
    execute_command_check(hand_commander, joint_states_config, 'ext_lf', 0.2, 0.2)
    execute_command_check(hand_commander, joint_states_config, 'pre_ff_ok', 1.0, 1.0)
    execute_command_check(hand_commander, joint_states_config, 'ff_ok', 3.3, 1.3)
    execute_command_check(hand_commander, joint_states_config, 'ne_wr', 1.1, 1.1)
    execute_command_check(hand_commander, joint_states_config, 'nw_wr', 1.1, 1.1)
    execute_command_check(hand_commander, joint_states_config, 'sw_wr', 1.1, 1.1)
    execute_command_check(hand_commander, joint_states_config, 'se_wr', 1.1, 1.1)
    execute_command_check(hand_commander, joint_states_config, 'ne_wr', 0.7, 0.7)
    execute_command_check(hand_commander, joint_states_config, 'nw_wr', 0.7, 0.7)
    execute_command_check(hand_commander, joint_states_config, 'sw_wr', 0.7, 0.7)
    execute_command_check(hand_commander, joint_states_config, 'se_wr', 0.7, 0.7)
    execute_command_check(hand_commander, joint_states_config, 'zero_wr', 0.4, 0.4)
    execute_command_check(hand_commander, joint_states_config, 'start_pos', 1.5, 1.5)


def sequence_mf(hand_commander, joint_states_config):
    rospy.loginfo("MF demo started")

    rospy.sleep(0.5)
    execute_command_check(hand_commander, joint_states_config, 'start_pos', 1.0, 1.0)
    execute_command_check(hand_commander, joint_states_config, 'bc_pre_zero', 2.0, 2.0)
    execute_command_check(hand_commander, joint_states_config, 'bc_zero', 4.0, 1.0)
    execute_command_check(hand_commander, joint_states_config, 'bc_1', 1.0, 1.0)
    execute_command_check(hand_commander, joint_states_config, 'bc_2', 1.0, 1.0)
    execute_command_check(hand_commander, joint_states_config, 'bc_3', 1.0, 1.0)
    execute_command_check(hand_commander, joint_states_config, 'bc_4', 1.0, 1.0)
    execute_command_check(hand_commander, joint_states_config, 'bc_5', 1.0, 1.0)
    execute_command_check(hand_commander, joint_states_config, 'bc_6', 1.0, 1.0)
    execute_command_check(hand_commander, joint_states_config, 'bc_7', 1.0, 1.0)
    execute_command_check(hand_commander, joint_states_config, 'bc_8', 1.0, 1.0)
    execute_command_check(hand_commander, joint_states_config, 'bc_9', 1.0, 1.0)
    execute_command_check(hand_commander, joint_states_config, 'bc_11', 1.0, 1.0)
    execute_command_check(hand_commander, joint_states_config, 'bc_12', 4.0, 3.0)
    execute_command_check(hand_commander, joint_states_config, 'start_pos', 1.5, 1.5)

    rospy.loginfo("MF demo completed")


def sequence_rf(hand_commander, joint_states_config, tactile_reading, hand_type):
    rospy.loginfo("RF demo started")

    # Trigger flag array
    trigger = [0, 0, 0, 0, 0]

    # Move Hand to zero position
    execute_command_check(hand_commander, joint_states_config, 'start_pos', 2.0, 2.0)

    # Move Hand to starting position
    execute_command_check(hand_commander, joint_states_config, 'pregrasp_pos', 2.0, 2.0)

    # Move Hand to close position
    execute_command_check(hand_commander, joint_states_config, 'grasp_pos', 0.0, 11.0)
    offset1 = 3

    # Initialize end time
    end_time = time.time() + 11

    prefix = "lh_"
    for joint_state in joint_states_config['start_pos'].keys():
        if "rh_" in joint_state:
            prefix = "rh_"
            break

    # For now, tactile_reading is only being considered for uni-manual
    while tactile_reading is not None:
        # Record current joint positions
        hand_pos = {joint: degrees(i) for joint, i in hand_commander.get_joints_position().items()}

        # If any tacticle sensor has been triggered, send
        # the corresponding digit to its current position
        if (tactile_reading.confirm_touched() == 'FF' and trigger[0] == 0):
            hand_pos_incr_f = {f"{prefix}FFJ1": hand_pos[f'{prefix}FFJ1'] + offset1,
                               f"{prefix}FFJ3": hand_pos[f'{prefix}FFJ3'] + offset1}
            hand_commander.move_to_joint_value_target_unsafe(hand_pos_incr_f, 0.5, wait=False, angle_degrees=True)
            rospy.loginfo('First finger contact')
            trigger[0] = 1

        if (tactile_reading.confirm_touched() == 'MF' and trigger[1] == 0):
            hand_pos_incr_m = {f"{prefix}MFJ1": hand_pos[f'{prefix}MFJ1'] + offset1,
                               f"{prefix}MFJ3": hand_pos[f'{prefix}MFJ3'] + offset1}
            hand_commander.move_to_joint_value_target_unsafe(hand_pos_incr_m, 0.5, wait=False, angle_degrees=True)
            rospy.loginfo('Middle finger contact')
            trigger[1] = 1

        if (tactile_reading.confirm_touched() == 'RF' and trigger[2] == 0):
            hand_pos_incr_r = {f"{prefix}RFJ1": hand_pos[f'{prefix}RFJ1'] + offset1,
                               f"{prefix}RFJ3": hand_pos[f'{prefix}RFJ3'] + offset1}
            hand_commander.move_to_joint_value_target_unsafe(hand_pos_incr_r, 0.5, wait=False, angle_degrees=True)
            rospy.loginfo('Ring finger contact')
            trigger[2] = 1

        if (tactile_reading.confirm_touched() == 'LF' and trigger[3] == 0):
            hand_pos_incr_l = {f"{prefix}LFJ1": hand_pos[f'{prefix}LFJ1'] + offset1,
                               f"{prefix}LFJ3": hand_pos[f'{prefix}LFJ3'] + offset1}
            hand_commander.move_to_joint_value_target_unsafe(hand_pos_incr_l, 0.5, wait=False, angle_degrees=True)
            rospy.loginfo('Little finger contact')
            trigger[3] = 1

        if (tactile_reading.confirm_touched() == 'TH' and trigger[4] == 0):
            hand_pos_incr_th = {f"{prefix}THJ2": hand_pos[f'{prefix}THJ2'] + offset1,
                                f"{prefix}THJ5": hand_pos[f'{prefix}THJ5'] + offset1}
            hand_commander.move_to_joint_value_target_unsafe(hand_pos_incr_th, 0.5, wait=False, angle_degrees=True)
            rospy.loginfo('Thumb contact')
            trigger[4] = 1

        if (trigger[0] == 1 and trigger[1] == 1 and trigger[2] == 1 and trigger[3] == 1 and trigger[4] == 1):
            break

        if time.time() > end_time:
            break

    # Send all joints to current position to compensate
    # for minor offsets created in the previous loop
    hand_pos = {joint: degrees(i) for joint, i in hand_commander.get_joints_position().items()}
    hand_commander.move_to_joint_value_target_unsafe(hand_pos, 2.0, wait=False, angle_degrees=True)
    rospy.sleep(2.0)

    # Generate new values to squeeze object slightly
    offset2 = 3
    squeeze = hand_pos.copy()
    if hand_type == 'hand_lite':
        squeeze.update({f"{prefix}THJ5": hand_pos[f'{prefix}THJ5'] + offset2,
                        f"{prefix}THJ2": hand_pos[f'{prefix}THJ2'] + offset2,
                        f"{prefix}FFJ3": hand_pos[f'{prefix}FFJ3'] + offset2,
                        f"{prefix}FFJ1": hand_pos[f'{prefix}FFJ1'] + offset2,
                        f"{prefix}MFJ3": hand_pos[f'{prefix}MFJ3'] + offset2,
                        f"{prefix}MFJ1": hand_pos[f'{prefix}MFJ1'] + offset2,
                        f"{prefix}RFJ3": hand_pos[f'{prefix}RFJ3'] + offset2,
                        f"{prefix}RFJ1": hand_pos[f'{prefix}RFJ1'] + offset2})
    elif hand_type == 'hand_extra_lite':
        squeeze.update({f"{prefix}THJ5": hand_pos[f'{prefix}THJ5'] + offset2,
                        f"{prefix}THJ2": hand_pos[f'{prefix}THJ2'] + offset2,
                        f"{prefix}FFJ3": hand_pos[f'{prefix}FFJ3'] + offset2,
                        f"{prefix}FFJ1": hand_pos[f'{prefix}FFJ1'] + offset2,
                        f"{prefix}RFJ3": hand_pos[f'{prefix}RFJ3'] + offset2,
                        f"{prefix}RFJ1": hand_pos[f'{prefix}RFJ1'] + offset2})
    else:
        squeeze.update({f"{prefix}THJ5": hand_pos[f'{prefix}THJ5'] + offset2,
                        f"{prefix}THJ2": hand_pos[f'{prefix}THJ2'] + offset2,
                        f"{prefix}FFJ3": hand_pos[f'{prefix}FFJ3'] + offset2,
                        f"{prefix}FFJ1": hand_pos[f'{prefix}FFJ1'] + offset2,
                        f"{prefix}MFJ3": hand_pos[f'{prefix}MFJ3'] + offset2,
                        f"{prefix}MFJ1": hand_pos[f'{prefix}MFJ1'] + offset2,
                        f"{prefix}RFJ3": hand_pos[f'{prefix}RFJ3'] + offset2,
                        f"{prefix}RFJ1": hand_pos[f'{prefix}RFJ1'] + offset2,
                        f"{prefix}LFJ3": hand_pos[f'{prefix}LFJ3'] + offset2,
                        f"{prefix}LFJ1": hand_pos[f'{prefix}LFJ1'] + offset2})

    # Squeeze object gently
    hand_commander.move_to_joint_value_target_unsafe(squeeze, 0.5, wait=False, angle_degrees=True)
    rospy.sleep(0.5)
    hand_commander.move_to_joint_value_target_unsafe(hand_pos, 0.5, wait=False, angle_degrees=True)
    rospy.sleep(0.5)
    hand_commander.move_to_joint_value_target_unsafe(squeeze, 0.5, wait=False, angle_degrees=True)
    rospy.sleep(0.5)
    hand_commander.move_to_joint_value_target_unsafe(hand_pos, 2.0, wait=False, angle_degrees=True)
    rospy.sleep(2.0)
    execute_command_check(hand_commander, joint_states_config, 'pregrasp_pos', 2.0, 2.0)
    execute_command_check(hand_commander, joint_states_config, 'start_pos', 2.0, 2.0)

    rospy.loginfo("RF demo completed")


def sequence_lf(hand_commander, joint_states_config, tactile_reading):
    rospy.loginfo("LF demo started")

    rospy.sleep(0.5)
    # Initialize wake time
    wake_time = time.time()
    while True:
        # For now, tactile_reading is only being considered for uni-manual
        if tactile_reading is not None:
            # Check if any of the tactile senors have been triggered
            # If so, send the Hand to its start position
            touched = tactile_reading.confirm_touched()
            if touched is not None:
                execute_command_check(hand_commander, joint_states_config, 'start_pos', 0.0, 2.0)
                rospy.loginfo(f'{touched} touched!')
                rospy.sleep(2.0)
                if touched == "TH":
                    break

            # If the tactile sensors have not been triggered and the Hand
            # is not in the middle of a movement, generate a random position
            # and interpolation time
            else:
                if time.time() < wake_time + CONST_TIME_TO_COMPLETE_DEMO:
                    complete_random_sequence(hand_commander, joint_states_config)
                else:
                    break
        else:
            if time.time() < wake_time + CONST_TIME_TO_COMPLETE_DEMO:
                complete_random_sequence(hand_commander, joint_states_config)
            else:
                break

    execute_command_check(hand_commander, joint_states_config, 'start_pos', 2.0, 2.0)

    rospy.loginfo("LF demo completed")


def complete_random_sequence(hand_commander, joint_states_config):
    prefix = "lh_"
    for joint_state in joint_states_config['start_pos'].keys():
        if "rh_" in joint_state:
            prefix = "rh_"
            break

    for i in joint_states_config['rand_pos']:
        joint_states_config['rand_pos'][i] =\
            random.randrange(joint_states_config['min_range'][i],
                             joint_states_config['max_range'][i])
    joint_states_config['rand_pos'][f'{prefix}FFJ4'] =\
        random.randrange(joint_states_config['min_range'][f'{prefix}FFJ4'],
                         joint_states_config['rand_pos'][f'{prefix}MFJ4'])
    joint_states_config['rand_pos'][f'{prefix}LFJ4'] =\
        random.randrange(joint_states_config['min_range'][f'{prefix}LFJ4'],
                         joint_states_config['rand_pos'][f'{prefix}RFJ4'])
    inter_time = 4.0 * random.random()
    execute_command_check(hand_commander, joint_states_config, 'rand_pos', 0.2, inter_time)


def correct_joint_states_for_hand_type(joint_states_config, hand_type):
    hand_type_joints_filename = '/home/user/projects/shadow_robot/base/src/'\
                       'sr_interface/sr_demos/config/joints_in_hand.yaml'
    with open(hand_type_joints_filename, encoding="utf-8") as hand_type_joints_file:
        hand_type_joints = yaml.load(hand_type_joints_file, Loader=yaml.FullLoader)

    for joint_state_dicts_no_id in joint_states_config.keys():
        for key in list(joint_states_config[joint_state_dicts_no_id]):
            if key not in hand_type_joints[hand_type]:
                joint_states_config[joint_state_dicts_no_id].pop(key)

    return joint_states_config


def add_prefix_to_joint_states(corrected_joint_states_config, joint_prefix):
    demo_states = {}
    for joint_state_dicts_no_id in corrected_joint_states_config.keys():
        joints_target = {}
        for key, value in corrected_joint_states_config[joint_state_dicts_no_id].items():
            if joint_prefix == 'both':
                joints_target['rh_' + key] = value
                joints_target['lh_' + key] = value
            else:
                joints_target[joint_prefix + key] = value
            demo_states[joint_state_dicts_no_id] = joints_target
    return demo_states


def execute_command_check(hand_commander, joint_states_config, joint_states,
                          sleep, time_to_execute, wait=False, angle_degrees=True):
    if joint_states in joint_states_config.keys():
        hand_commander.move_to_joint_value_target_unsafe(joint_states_config[joint_states], time_to_execute, wait,
                                                         angle_degrees)
        rospy.sleep(sleep)


if __name__ == "__main__":

    rospy.init_node("right_hand_demo", anonymous=True)

    parser = argparse.ArgumentParser(description="Hand side")
    parser.add_argument("-s", "--side",
                        dest="side",
                        type=str,
                        required=False,
                        help="Please select hand side, can be 'right', 'left' or 'both'.",
                        default=True,
                        choices=["right", "left", "both"])
    parser.add_argument("-ht", "--hand_type",
                        dest="hand_type",
                        type=str,
                        required=True,
                        help="Please select hand type, can be 'hand_e', 'hand_lite', 'hand_extra_lite'.",
                        default="hand_e",
                        choices=["hand_e", "hand_lite", "hand_extra_lite"])

    args = parser.parse_args(rospy.myargv()[1:])

    if args.side == 'right':
        joint_prefix_name = 'rh_'
    elif args.side == 'left':
        joint_prefix_name = 'lh_'
    else:
        joint_prefix_name = 'both'

    if joint_prefix_name == 'rh_':
        hand_name = "right_hand"
    elif joint_prefix_name == 'lh_':
        hand_name = "left_hand"
    else:
        hand_name = "two_hands"

    hand_commander_instance = SrHandCommander(name=hand_name, prefix=joint_prefix_name)

    # Get joint states for demo from yaml
    joint_states_config_filename = '/home/user/projects/shadow_robot/base/src/'\
                                   'sr_interface/sr_demos/config/demo_joint_states.yaml'
    with open(joint_states_config_filename, encoding="utf-8") as joint_state_file:
        joint_states_config_yaml = yaml.load(joint_state_file, Loader=yaml.FullLoader)

    corrected_joint_states_config_for_this_hand = correct_joint_states_for_hand_type(joint_states_config_yaml,
                                                                                     args.hand_type)

    # Add prefix to joint states
    demo_states_with_prefix = add_prefix_to_joint_states(corrected_joint_states_config_for_this_hand, joint_prefix_name)

    execute_command_check(hand_commander_instance, demo_states_with_prefix, 'start_pos', 0.0, 1.0)

    # TactileReading is going to search for any available sensors (Biotact, PST, etc)
    tactile_reading_instance = None
    if joint_prefix_name == 'both':
        tactile_right = TactileReading(hand_commander_instance, demo_states_with_prefix, 'rh_')
        tactile_left = TactileReading(hand_commander_instance, demo_states_with_prefix, 'lh_')
    else:
        tactile_reading_instance = TactileReading(hand_commander_instance, demo_states_with_prefix, joint_prefix_name)

    rospy.loginfo("\nPRESS ONE OF THE TACTILES or 1-5 ON THE KEYBOARD TO START A DEMO:\
                   \nTH or 1: Open Hand\
                   \nFF or 2: Standard Demo\
                   \nMF or 3: Card Trick Demo\
                   \nRF or 4: Grasp Demo\
                   \nLF or 5: Shy Hand Demo (only works with Hand E).\
                   \nPRESS 6 TO END THE PROGRAM")

    # Keyboard thread for input
    kpd = KeyboardPressDetector(hand_commander_instance, demo_states_with_prefix,
                                tactile_reading_instance, args.hand_type)
    keyboard_thread = Thread(target=kpd.run)
    keyboard_thread.start()

    while not rospy.is_shutdown():
        # Check the state of the tactile sensors
        touched_finger = None

        if joint_prefix_name == 'both':  # Bimanual mode
            # check if tactile sensors have been previously found for at least one hand
            if tactile_right.get_tactiles() is not None or tactile_left.get_tactiles() is not None:
                # confirm_touched() will return None if no sensors are found
                touched_right = tactile_right.confirm_touched()
                touched_left = tactile_left.confirm_touched()
                if touched_right is not None and touched_left is not None:
                    rospy.loginfo("You touched fingers on both hands at the same time. Defaulting to right touch")
                    touched_finger = touched_right
                elif touched_right is not None:
                    touched_finger = touched_right
                elif touched_left is not None:
                    touched_finger = touched_left
        # check if tactile sensors have been previously found
        elif tactile_reading_instance.get_tactiles() is not None:  # Unimanual mode
            touched_finger = tactile_reading_instance.confirm_touched()

        # If the tactile is touched, trigger the corresponding function
        if touched_finger == "TH":
            sequence_th(hand_commander_instance, demo_states_with_prefix)
        elif touched_finger == "FF":
            sequence_ff(hand_commander_instance, demo_states_with_prefix)
        elif touched_finger == "MF":
            sequence_mf(hand_commander_instance, demo_states_with_prefix)
        elif touched_finger == "RF":
            sequence_rf(hand_commander_instance, demo_states_with_prefix, tactile_reading_instance, args.hand_type)
        elif touched_finger == "LF":
            sequence_lf(hand_commander_instance, demo_states_with_prefix, tactile_reading_instance)

        rospy.sleep(0.1)
