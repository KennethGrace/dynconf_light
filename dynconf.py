#!/usr/bin/env python3
#
# DynConf Light: Dynamic Configuration
#
# Copyright (c) 2020 Kenneth J. Grace <kenneth.grace@dyntek.com>
#
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE
# LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION
# WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
#

from __future__ import annotations

__version__ = "0.0.1"
__author__ = "Kenneth J. Grace"

import argparse
import csv
import sys
import netmiko
import paramiko
import yaml
import jinja2
import pathlib
import enum


class Log(enum.IntEnum):
    DEBUG = 0
    INFO = 1
    WARNING = 2
    ERROR = 3
    FATAL = 4


class Environment:
    def __init__(self, table: list) -> None:
        self.devices = [Device(**entry) for entry in table]

    @classmethod
    def from_file(cls, filename: str) -> Environment:
        """
        Defines an Environment around a plain-text data file in csv or yaml format.

        :param filename: The filename and path of a .yaml or .csv file.
        :return: Returns a new Environment of file existence, and None if failed.
        """
        data = []
        with open(filename, 'r') as f:
            if filename.endswith('.csv'):
                reader = csv.DictReader(f)
                data = [row for row in reader]
            elif filename.endswith('.yaml'):
                data = yaml.load(f, yaml.FullLoader)
        return cls(table=data)

    def record(self, filename: str):
        """
        Records this log of this environment to a specified log file.
        :return: A reference to the file path of the newly created log file
        """
        with open(filename, 'w') as f:
            f.write(str(self))
        return filename

    def __getitem__(self, item):
        return self.devices[item]

    def __repr__(self):
        summary = [f"{d.id.upper()} -> {d.log[0]}" for d in self]
        device_logs = [str(d) for d in self]
        return "\n".join(summary) + "\n"*2 + "\n".join(device_logs)


class Device:
    _default_username = "admin"
    _default_password = "Password1"
    _default_template = "template.j2"

    def __init__(self, host: str, device_type: str, username: str = None, password: str = None, port: str = '22',
                 secret: str = '', template: str = None, **kwargs) -> None:
        self.id = host if 'id' not in kwargs else kwargs['id']
        self.host = host
        self.device_type = device_type
        self.username = username if username else Device._default_username
        self.password = password if password else Device._default_password
        self.port = port
        self.secret = secret
        self.template = template if template else Device._default_template
        self.vars = kwargs
        # Establish empty runtime variables
        # connection denotes the netmiko connect handler object used for sending and receiving data
        self.connection: netmiko.ConnectHandler = None
        # log denotes a list of a series of codes detailing the events during this objects lifetime.
        self.log = [f"Info: {self.id} Instantiated as \"{self.host}:{self.port}\""]
        self.log.insert(0, f"Info: Device variables set as \"{self.vars}\"")

    @classmethod
    def set_defaults(cls, username: str, password: str, template: str) -> None:
        cls._default_username = username if username else cls._default_username
        cls._default_password = password if password else cls._default_password
        cls._default_template = template if template else cls._default_template

    def log(self, level: int, message: str) -> None:
        """
        Adds a log message to the log and prints the log to standard out unless the program was instructed to run in
        quiet mode.

        :param level:
        :param message:
        :return:
        """
        # TODO: implement functionality for logging in a better more versatile way than currently

    def connect(self) -> netmiko.ConnectHandler:
        """
        Given the device params defined at device instantiation, we now attempt to build the netmiko connection.
        In the event of a failure during connection establishment, we will return None and set the log of this device
        for a failure in whatever exception caused the failure.

        :return: Return the netmiko.ConnectHandler object in case it is desired outside the class functionality.
        """
        params = {
            "host": self.host,
            "device_type": self.device_type,
            "username": self.username,
            "password": self.password,
            "port": self.port,
            "secret": self.secret
        }
        # TODO: implement netmiko.ConnectHandler exception handling for the various possible exceptions when attempting
        #  a connection.
        try:
            self.connection: netmiko.ConnectHandler = netmiko.ConnectHandler(**params)
        except paramiko.ssh_exception.AuthenticationException:
            self.log.insert(0, "Error: Authentication")
            return None
        except TimeoutError:
            self.log.insert(0, "Error: Timeout")
            return None
        else:
            self.log.insert(0, "Info: Connection Successful")
        return self.connection

    def deploy(self, max_attempts: int = -1) -> list:
        """
        Accepts and renders a Jinja formatted template to a string of deployment code and administers the code to
        the device.

        :param max_attempts: The max number of retries to issue on io interruption. -1 is infinite.
        :return: Returns a list of the output from each command issued.
        """
        if self.connection:
            try:
                with open(self.template, 'r') as f:
                    deployment = jinja2.Environment(loader=jinja2.BaseLoader).from_string(f.read()).render(self.vars)
            except FileNotFoundError:
                self.log.insert(0, f"Error: Template file \"{self.template}\" not found")
            finally:
                self.log.insert(0, f"Info: Template Successfully Generated")
                out = self.push(commands=deployment.split('\n'), max_attempts=max_attempts)
                self.log.insert(0, f"Info: Deployment Successful")
                return out

    def push(self, commands: list, max_attempts: int = -1) -> list:
        """
        Pushes a series of commands to the target device via the pre-established connection. In the event a connection
        has not been established or failed to establish properly we do nothing and return nothing

        :param commands: The required list of commands to issue to the target device connection.
        :param max_attempts: The max number of retries to issue on io interruption. -1 is infinite.
        :return: Returns a list of the output from each command issued, in the order of the original list.
        """
        if self.connection:
            results = []
            for command in commands:
                tries = 0
                while True if max_attempts == -1 else (max_attempts >= tries):
                    try:
                        tries += 1
                        results.append(self.connection.send_command_expect(command))
                    except IOError:
                        self.log.insert(0, f"Warning: IO Failure on \"{command}\" try #{tries}")
                        print(f"Bad Stream on {self.id} - Trying Again - \"{command}\"")
                    else:
                        self.log.insert(0, f"Info: Success on \"{command}\"")
                        break
            return results

    def __repr__(self):
        """
        In contrast to the typical use of this function, we are overloading a string representation of the Device object
        to print the log of this objects history.

        :return: The formatted log of this objects history
        """
        return "\n".join([self.id.upper().center(48, "-")] + self.log)


def main() -> int:
    """
    When DynConf is called directly this function is called to start the default handling of args for operation
    :return: A status code indicating the success or the failure of the program
    """
    print(f"DynConf: Dynamic Configuration {__version__.upper()}")
    parser = argparse.ArgumentParser(prog="DynConf", description="Dynamic Configuration")
    parser.add_argument('filename', type=str, help="Filename for defining an environment")
    parser.add_argument('--username', '-u', type=str, help="Default username for connections")
    parser.add_argument('--password', '-p', type=str, help="Default password for connections")
    parser.add_argument('--template', '-t', type=str, help="Default template for deployment")
    args = parser.parse_args()
    Device.set_defaults(username=args.username, password=args.password, template=args.template)
    env = Environment.from_file(filename=args.filename)
    for dev in env:
        dev.connect()
    for dev in env:
        dev.deploy()
    print(env)
    env.record(f"{pathlib.Path(args.filename).stem}.log")
    return 0


if __name__ == '__main__':
    code: int = main()
    sys.exit(code)
