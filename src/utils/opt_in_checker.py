# Copyright (C) 2018-2021 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

import os
import time
from enum import Enum
from pathlib import Path
from platform import system
from sys import stdin

from .colored_print import colored_print
from .input_with_timeout import input_with_timeout


class ISIPCheckResult(Enum):
    DECLINED = 0
    ACCEPTED = 1
    NO_FILE = 2


class DialogResult(Enum):
    DECLINED = 0
    ACCEPTED = 1
    TIMEOUT_REACHED = 2


class OptInChecker:
    dialog_timeout = 50  # seconds
    path_to_opt_in_out_script = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
    opt_in_out_script_name = "opt_in_out"
    doc_link = "http://openvino-docs.inn.intel.com/"
    opt_in_out_script_run_command = "\'{} --opt_out\'".format(opt_in_out_script_name)
    opt_in_question = "With your permission, Intel would like to collect occasional (anonymous) tool usage such " \
                      "as software installation, development environment, and usage responses to improve our product " \
                      "and your developer experience.  This confidential data will be kept a period of time " \
                      "to study trends, and of course you can opt out at any time in the future by running {}. " \
                      "We really appreciate your help by accepting (just type \"Y\" at the prompt) to show your " \
                      "consent to the collection of this data, a \"N\" will prevent the anonymous data from " \
                      "being sent back to Intel. " \
                      "Thanks for replying with a \"Y\"!".format(opt_in_out_script_run_command)
    opt_in_question = "Intel would like your permission to collect software performance and usage data for the " \
                      "purpose of improving Intel products and services. This data will be collected directly " \
                      "by Intel or through the use of Google Analytics. This data will be stored in countries " \
                      "where Intel or Google operate. You can opt-out at any time in the future by running {}. " \
                      "More Information is available at {}.\n" \
                      "Please type ‘Y’ to give your consent or ‘N’ to decline.".format(opt_in_out_script_run_command,
                                                                                       doc_link)
    opt_in_question_incorrect_input = "Please type ‘Y’ to give your consent or ‘N’ to decline."
    response_confirmation_accept = "The selected option was to collect telemetry data."
    response_confirmation_decline = "The selected option was NOT to collect telemetry data."
    response_confirmation_timer_reached = "The timer has expired and no data will be collected."

    @staticmethod
    def _ask_opt_in(question: str, timeout: int):
        """
        Runs input with timeout and checks user input.
        :param question: question that will be printed on the screen.
        :param timeout: timeout to wait.
        :return: opt-in dialog result.
        """
        colored_print(question)
        answer = input_with_timeout(prompt='>>', timeout=timeout)
        answer = answer.lower()
        if answer == "n" or answer == "no":
            colored_print(OptInChecker.response_confirmation_decline)
            return DialogResult.DECLINED
        if answer == "y" or answer == "yes":
            colored_print(OptInChecker.response_confirmation_accept)
            return DialogResult.ACCEPTED
        return DialogResult.TIMEOUT_REACHED

    def opt_in_dialog(self):
        """
        Runs opt-in dialog until the timeout is expired.
        :return: opt-in dialog result.
        """
        start_time = time.time()
        answer = self._ask_opt_in(self.opt_in_question, self.dialog_timeout)
        time_passed = time.time() - start_time
        while time_passed < self.dialog_timeout and answer == DialogResult.TIMEOUT_REACHED:
            answer = self._ask_opt_in(self.opt_in_question_incorrect_input, self.dialog_timeout - time_passed)
            time_passed = time.time() - start_time

        if answer == DialogResult.TIMEOUT_REACHED:
            colored_print(OptInChecker.response_confirmation_timer_reached)

        return answer

    @staticmethod
    def isip_file_base_dir():
        """
        Returns the base directory of the ISIP file.
        :return: base directory of the ISIP file.
        """
        platform = system()

        dir_to_check = None

        if platform == 'Windows':
            dir_to_check = '$LOCALAPPDATA'
        elif platform in ['Linux', 'Darwin']:
            dir_to_check = Path.home()

        if dir_to_check is None:
            raise Exception('Failed to find location of the ISIP file.')

        isip_base_dir = os.path.expandvars(dir_to_check)
        if not os.path.isdir(isip_base_dir):
            raise Exception('Failed to find location of the ISIP file.')

        return isip_base_dir

    @staticmethod
    def isip_file_subdirectory():
        """
        Returns ISIP file subdirectory.
        :return: ISIP file subdirectory.
        """
        platform = system()
        if platform == 'Windows':
            return 'Intel Corporation'
        elif platform in ['Linux', 'Darwin']:
            return '.intel'
        raise Exception('Failed to find location of the ISIP file.')

    def isip_file(self):
        """
        Returns the ISIP file path.
        :return: ISIP file path.
        """
        return os.path.join(self.isip_file_base_dir(), self.isip_file_subdirectory(), "isip")

    def create_new_isip_file(self):
        """
        Creates a new ISIP file.
        :return: True if the file is created successfully, otherwise False
        """
        if not self.create_or_check_isip_dir():
            return False
        try:
            open(self.isip_file(), 'w').close()
        except Exception:
            return False
        return True

    def create_or_check_isip_dir(self):
        """
        Creates ISIP file directory and checks if the directory is writable.
        :return: True if the directory is created and writable, otherwise False
        """
        isip_dir = os.path.join(self.isip_file_base_dir(), self.isip_file_subdirectory())
        if not os.path.isdir(isip_dir):
            if not os.access(isip_dir, os.W_OK):
                print("Failed to update opt-in status. "
                      "Cannot create directory for ISIP file, as directory is not writable: {}".format(isip_dir))
                return
            os.remove(isip_dir)
        if not os.path.exists(isip_dir):
            if not os.access(self.isip_file_base_dir(), os.W_OK):
                print("Failed to update opt-in status. "
                      "Please allow write access to the following directory: {}".format(self.isip_file_base_dir()))
                return False
            os.mkdir(isip_dir)
        if not os.access(isip_dir, os.W_OK):
            print("Failed to update opt-in status. "
                  "Please allow write access to the following directory: {}".format(isip_dir))
            return False
        return True

    def update_result(self, result: ISIPCheckResult):
        """
        Updates the 'opt_in' value in the ISIP file.
        :param result: opt-in dialog result.
        :return: False if the ISIP file is not writable, otherwise True
        """
        if not os.path.exists(self.isip_file()):
            if not self.create_new_isip_file():
                return False
        if not os.access(self.isip_file(), os.W_OK):
            print("Failed to update opt-in status. "
                  "Please allow write access to the following file: {}".format(self.isip_file()))
            return False
        try:
            with open(self.isip_file(), 'w') as file:
                if result == ISIPCheckResult.ACCEPTED:
                    file.write("1")
                else:
                    file.write("0")
        except Exception:
            return False
        return True

    def isip_is_empty(self):
        """
        Checks if the ISIP file is empty.
        :return: True if ISIP file is empty, otherwise False.
        """
        if os.stat(self.isip_file()).st_size == 0:
            return True
        return False

    def get_info_from_isip(self):
        """
        Gets information from ISIP file.
        :return: the tuple, where the first element is True if the file is read successfully, otherwise False
        and the second element is the content of the ISIP file.
        """
        if not os.access(self.isip_file(), os.R_OK):
            return False, {}
        try:
            with open(self.isip_file(), 'r') as file:
                content = file.readline().strip()
        except Exception:
            return False, {}
        return True, content

    @staticmethod
    def _check_input_is_terminal():
        """
        Checks if stdin is terminal.
        :return: True if stdin is terminal, otherwise False
        """
        return stdin.isatty()

    @staticmethod
    def _check_run_in_notebook():
        """
        Checks that script is executed in Jupyter Notebook.
        :return: True script is executed in Jupyter Notebook, otherwise False
        """
        try:
            return get_ipython().__class__.__name__ == 'ZMQInteractiveShell'
        except NameError:
            pass
        return False

    def check(self):
        """
        Checks if user has accepted the collection of the information by checking the ISIP file.
        :return: opt-in dialog result
        """
        if not self._check_input_is_terminal() or self._check_run_in_notebook():
            return ISIPCheckResult.DECLINED

        if not os.path.exists(self.isip_file()):
            return ISIPCheckResult.NO_FILE

        if not self.isip_is_empty():
            _, content = self.get_info_from_isip()
            if content == "1":
                return ISIPCheckResult.ACCEPTED
            elif content == "0":
                return ISIPCheckResult.DECLINED
        print('Incorrect format of the file with opt-in status.')
        return ISIPCheckResult.DECLINED