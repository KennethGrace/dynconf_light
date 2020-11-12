# ![favicon](favicon.png) DynConf Light

   DynConf Light is a light-weight single file implementation of DynTek's DynConf. DynConf is a configuration templating and deployment engine for assisting network engineers in rapid configuration changes and information gathering at scale in a multi-vendor environment. DynConf aims to make it's deployments as easy to use as any CLI, but faster to learn and run than any alternative.

## Getting Started

You can follow the below instructions to get started. If you're familiar with Python and dependencies, the single-file nature of DynConf Light means all you need is the content of [this](dynconf.py) file.

### Prerequisites

To use DynConf Light you're going to need to install a couple of programs and libraries.

* For Windows, Download Git for Windows at [gitforwindows.org](https://gitforwindows.org/)
* For Mac and Linux, follow instructions at [git-scm.com](https://git-scm.com/book/en/v2/Getting-Started-Installing-Git)
* Install Python 3 from [python.org](https://www.python.org/)
* Install the Jinja2, Netmiko, and  Python Library via pip
```
python -m pip install jinja2 netmiko
```

### Installation

To install DynConf Light we'll be using git to download this repository.

* Do a git clone of this repository into a directory of your choosing
```
git clone https://github.com/KennethGrace/dynconf_light.git
```

## Environment and Devices
The DynConf application is built around two classes of objects, the Environment and the Device. Each DynConf instance has exactly one Environment instance, but each Environment instance can have an unlimited number of associated Device instances. The Environment and it's associated Devices are defined at launch by a "data file". This data file can be defined in either YAML, JSON, or CSV. For YAML and JSON the document should be structured as a list of dictionaries or objects respectively.

A Device definition requires that at a minimum a host and device_type value be supplied. The host value denotes the hostname or IP address at which the SSH service for the network device can be reached. The device_type value is passed directly to the underlying Netmiko ConnectionHandler. A list of available device types can be found [here](https://github.com/ktbyers/netmiko/blob/develop/EXAMPLES.md#available-device-types).

Beyond the required variables, the Device definition also accepts several special fields. These special fields, their use cases, their defaults, and scopes are listed below. An 'Internal' scope indicates the variable is not accessible from within the template.

|Field|Use-Case|Default|Scope|
|---|---|---|---|
|id|Overrides the 'host' value for a logging id.|'host' Field|External|
|username|Overrides the default Device username.|admin|Internal|
|password|Overrides the default Device password.|Password1|Internal|
|port|Overrides the default Device port.|22|Internal|
|secret|Supplies a secret password to the Device.|None|Internal|
|template|Overrides the default template file.|template.j2|Internal|

The 'data file' allows for a infinite set of additional variables. All these other fields defined in the 'data file' will be considered external and will be available to your templates. Below is an example of a 'data file' in YAML format. Make sure you can identify the required, special, and template fields in these two Device definitions.
```yaml
---
- host: switch1.example.com
  device_type: cisco_ios
  username: admin
  new_loopback_ip: 10.255.255.11
- host: switch2.example.com
  device_type: cisco_ios
  username: admin
  new_loopback_ip: 10.255.255.12
...
```
## Templating
DynConf Light uses Jinja2 as it's only available templating language. You can learn more about Jinja2 [here](https://jinja.palletsprojects.com/en/2.11.x/).

Templates are loaded from the current working directory

## Authors

* ***Kenneth J Grace*** - *Initial Work* - [KennethGrace](https://github.com/KennethGrace)

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details

## Acknowledgments
* Thank you to all the [Netmiko](https://github.com/ktbyers/netmiko) contributors
* With special thanks to [Ktbyers](https://github.com/ktbyers)