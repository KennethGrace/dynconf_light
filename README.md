# DynConf: Dynamic Network Configuration
By Kenneth J. Grace

DynConf is used to automate the configuration and gathering of data from network devices over SSH. DynConf has the basic functionality to run as only a configuration renderer. DynConf utilizes Jinja templates and CSV or YAML Data to create device commands and Netmiko to run device connections. This project is a great example project for those interested in starting in Python and it's application to Network Automation. As such, this README.md is targeted to those with no experience in either or these.

## Getting Started
Before working with DynConf, you are going to need to make sure you have an installation of Python 3 on your machine. For your convenience, I have that linked [here](https://www.python.org/downloads/).

To get a copy of this program to run, you can clone this repository from Github or, for those of you without Git installed, download the .zip of the master branch.

Open a command prompt in the directory you cloned or downloaded this repository too.  Let's start by showing the required parameters
```cmd
dynconf.py --help
```
### [TODO]
You will never be happy ever again, just like me.