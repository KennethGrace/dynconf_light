#!/usr/bin/env python3
#
# DynConf: Dynamic Configuration
# An Attempt at Network Automation by Kenneth J. Grace
#
from __future__ import annotations

__version__ = "0.0.1"
__author__ = "Kenneth J. Grace"

import argparse
import csv
import json
import sys
import colors
import netmiko
import yaml


class Environment:
    def __init__(self, table: list) -> None:
        self.devices = [Device(**entry) for entry in table]

    @classmethod
    def from_file(cls, filename: str) -> (Environment, None):
        """
        Defines an Environment around a plain-text data file in csv or yaml format.

        :param filename: The filename and path of a .yaml or .csv file.
        :return: Returns a new Environment of file existence, and None if failed.
        """
        data = []
        try:
            with open(filename, 'r') as f:
                if filename.endswith('.csv'):
                    reader = csv.DictReader(f)
                    data = [row for row in reader]
                elif filename.endswith('.yaml'):
                    data = yaml.load(f, yaml.FullLoader)
        except FileNotFoundError as e:
            raise DynConfConfigurationError(e)
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
        summary = [f"{d.id.upper()}\t{d.log[0]}" for d in self]
        device_logs = [str(d) for d in self]
        return "\n".join(summary) + "\n"*2 + "\n".join(device_logs)


class Device:
    _default_username = "admin"
    _default_password = "Password1"

    def __init__(self, host: str, device_type: str, username: str = None, password: str = None, **kwargs) -> None:
        self.id = host if 'id' not in kwargs else kwargs['id']
        self.host = host
        self.device_type = device_type
        self.port = '22' if 'port' not in kwargs else kwargs['port']
        self.username = username if username else Device._default_username
        self.password = password if password else Device._default_password
        self.secret = kwargs['secret'] if 'secret' in kwargs else ''
        # Establish empty runtime variables
        # connection denotes the netmiko connect handler object used for sending and receiving data
        self.connection: netmiko.ConnectHandler = None
        # log denotes a list of a series of codes detailing the events during this objects lifetime.
        self.log = [f"Info: {self.id} Instantiated as {self.host}:{self.port}"]

    @classmethod
    def set_defaults(cls, username: str, password: str) -> None:
        cls._default_username = username
        cls._default_password = password

    def connect(self) -> (netmiko.ConnectHandler, None):
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
        except netmiko.ssh_exception.NetMikoAuthenticationException:
            self.log.insert(0, "Error: Authentication")
            return None
        except TimeoutError:
            self.log.insert(0, "Error: Timeout")
            return None
        return self.connection

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
                        print(colors.color(f"Bad Stream on {self.id} - Trying Again - \"{command}\"", fg='red'))
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


class DynConfRuntimeError(Exception):
    ...


class DynConfConfigurationError(Exception):
    ...


def main() -> int:
    """
    When DynConf is called directly this function is called to start the default handling of args for operation
    :return: A status code indicating the success or the failure of the program
    """
    print(f"DynConf: Dynamic Configuration {__version__.upper()}")
    parser = argparse.ArgumentParser(prog="DynConf", description="Dynamic Configuration")
    parser.add_argument('operation', type=str, help="The operation type to perform")
    parser.add_argument('filename', type=str, help="Filename for file defining an environment")
    parser.add_argument('--username', '-u', type=str, help="Username for connections")
    parser.add_argument('--password', '-p', type=str, help="Password for connections")
    args = parser.parse_args()
    if args.username and args.password:
        Device.set_defaults(username=args.username, password=args.password)
    elif args.username or args.password:
        raise DynConfConfigurationError("either username or password is supplied. either both must be or neither")
    env = Environment.from_file(filename=args.filename)
    for dev in env:
        handler = dev.connect()
    for dev in env:
        dev.push(['show cdp nei'])
    print(env)
    env.record('test.log')
    return 0


if __name__ == '__main__':
    code: int = main()
    sys.exit(code)
