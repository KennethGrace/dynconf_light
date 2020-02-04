#!/usr/bin/env python3
#
# DynConf: Dynamic Configuration
# An Attempt at Network Automation by Kenneth J. Grace
#
from __future__ import annotations

__version__ = "0.0.1"

import argparse
import csv
import json
import sys
import netmiko
import yaml


class Environment:
    def __init__(self, table: list) -> None:
        print(json.dumps(table, indent=1))
        self.devices = [Device(**entry) for entry in table]

    @classmethod
    def from_file(cls, filename: str) -> Environment:
        data = []
        with open(filename, 'r') as f:
            if filename.endswith('.csv'):
                reader = csv.DictReader(f)
                data = [row for row in reader]
            elif filename.endswith('.yaml'):
                data = yaml.load(f, yaml.FullLoader)
        return cls(table=data)

    def __getitem__(self, item):
        return self.devices[item]

    def __repr__(self):
        return '\n'.join([str(d) for d in self.devices])


class Device:
    _default_username = "admin"
    _default_password = "Password1"

    def __init__(self, host: str, device_type: str, username: str = None, password: str = None, **kwargs) -> None:
        self.id = host if 'id' not in kwargs else kwargs['id']
        self.host = host
        self.username = username
        self.password = password
        self.device_type = device_type
        self.connection = None

    @classmethod
    def set_defaults(cls, username: str, password: str) -> None:
        cls._default_username = username
        cls._default_password = password

    def connect(self):
        params = {
            "host": self.host,
            "device_type": self.device_type,
            "username": self.username,
            "password": self.password
        }
        self.connection = netmiko.ConnectionHandler()

    def __repr__(self):
        return json.dumps(self.__dict__, indent=1)


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
        print("If username or password is supplied, both must be!")
        return -1
    try:
        env = Environment.from_file(filename=args.filename)
    except FileNotFoundError:
        print(f"The specified file \"{args.filename}\" does not exist!")
        return -1
    print(env)
    return 0


if __name__ == '__main__':
    code: int = main()
    sys.exit(code)
