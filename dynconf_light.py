#
# DYNCONF LIGHT: Dynamic Configuration
# Config generator, administrator, and retriever based on Jinja2 templates,
# CSV data, and Netmiko SSH/Telnet Sessions for Cisco IOS and Junos
#
# 2018 Dyntek Services Inc.
# Kenneth J. Grace <kenneth.grace@dyntek.com>
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
#
from __future__ import print_function
import sys, os
from jinja2 import Environment, BaseLoader
from netmiko import ConnectHandler, ssh_exception
import paramiko
import threading, copy, datetime, math
import csv, json
from optparse import OptionParser

VERSION = '1.6.9.3'
"""
VERISON NOTES:
	1.5.1: Stable, dumps to super log, does not save json data. No plugin operation. No object orientation. Utilizes multiprocessing.
	1.6: Dev, dumps to super and device log, dumps json data. Can plugin to expand operation. Object Orientation. Utilizes threading for reduced complexity.
	1.6.1: Bug for options.mode fixed, and template_filename now not part of implied schema.
	1.6.2: username and password now not part of implied schema.
	1.6.3: Value Error for handling dropped config administrations.
	1.6.4: Enable password and Line-Password handling
	1.6.5: Security and inclusion of summary files.
	1.6.6: Attempt to clean up, abort, lol.
	1.6.7: Monkey patch for SSH to Telnet failovers
	1.6.8: Monkey patch for super-logging and command except failures
	1.6.9: KeyboardInterrupt Handling, SEND_FAILED retries, Retry Logging Append
"""

def patch_crypto_be_discovery():

	"""
	Monkey patches cryptography's backend detection.
	Objective: support pyinstaller freezing.
	"""

	from cryptography.hazmat import backends

	try:
		from cryptography.hazmat.backends.commoncrypto.backend import backend as be_cc
	except ImportError:
		be_cc = None

	try:
		from cryptography.hazmat.backends.openssl.backend import backend as be_ossl
	except ImportError:
		be_ossl = None

	backends._available_backends_list = [
		be for be in (be_cc, be_ossl) if be is not None
	]
patch_crypto_be_discovery()

class Session:
	datum_schema = ["host","device_type"]
	maxThreads = 3
	def __init__(self, data, template, default_username='admin', default_password='Password1', default_secret='Secret1', directory=None, mode='RENDER', **kwargs):
		self.id = 'session'
		if 'id' in kwargs.keys():
			self.id = kwargs['id']
		self.directory = directory
		self.mode = mode
		self.devices = []
		#Perform Data Validation
		host_list = []
		id_list = []
		for datum in data:
			if 'id' in datum:
				if datum['id'] not in id_list:
					id_list.append(datum['id'])
				else:
					raise SessionError('Atleast two devices have the same id variable. This is not allowed.')
			if 'host' in datum:
				if datum['host'] not in host_list:
					host_list.append(datum['host'])
				else:
					raise SessionError('Atleast two devices have the same host variable. This is not allowed.')
			if 'password' not in datum:
				datum['password'] = default_password
			if 'username' not in datum:
				datum['username'] = default_username
			if 'secret' not in datum:
				datum['secret'] = default_secret
		#Load Device Objects
		for datum in data:
			device_template = template
			if all(prop in list(datum.keys()) for prop in self.datum_schema):
				#Username if not defined or empty, then set to default_username
				try:
					if datum['username'] == '':
						datum['username'] = default_username
				except KeyError:
					datum['username'] = default_username
				#Password if not defined or empty, then set to default_password
				try:
					if datum['password'] == '':
						datum['password'] = default_password
				except KeyError:
					datum['password'] = default_password
				#Secret if not defined or empty, then set to default_secret
				try:
					if datum['secret'] == '':
						datum['secret'] = default_secret
				except:
					datum['secret'] = default_secret
				try:
					if 'template_filename' in datum:
						if datum['template_filename'] != '':
							if os.path.exists(datum['template_filename']):
								with open(datum['template_filename'], 'r') as f:
									device_template = f.read()
							else:
								raise SessionError('Template filename does not exist for {}'.format(datum['host']))
				except TypeError:
					pass
				device = Device(**datum)
				tpl = Environment(loader=BaseLoader).from_string(device_template)
				device.assign(tpl.render(datum))
				self.devices.append(device)
			else:
				raise SessionError('Atleast one device does not meet the Dynconf data schema')

	@classmethod
	def initFromFiles(cls, data_filename, template_filename, *args, **kwargs):
		data = []
		template = ""
		with open(data_filename, 'r') as f:
			reader = csv.DictReader(f)
			for row in reader:
				data.append(row)
		with open(template_filename, 'r') as f:
			template = f.read()
		return cls(data, template, *args, **kwargs)

	def administer(self, devices=None, ignore_ids=[]):
		if not devices:
			devices = self.devices
		#Create Threads
		if self.mode != 'RENDER':
			threads = []
			length = math.ceil(len(devices)/self.maxThreads)
			batch = []
			for device in devices:
				if device.id not in ignore_ids:
					batch.append(device)
				if len(batch) >= length:
					threads.append(threading.Thread(target=Session.__administerBatch, args=(self, batch)))
					batch = []
			if len(batch) > 0:
				threads.append(threading.Thread(target=Session.__administerBatch, args=(self, batch)))
			#Start Threads
			try:
				for thread in threads:
					thread.start()
				for thread in threads:
					thread.join()
			except KeyboardInterrupt:
				print("Waiting for Active Threads to Finish...")
		else:
			raise SessionError('A Render Mode Session Can Not Administer')

	def render(self):
		for device in self.devices:
			device.saveInput(self.directory)

	def __administerBatch(self, batch):
		for device in batch:
			device.connect(self.mode, self.directory)

	def recure(self):
		self.active = True
		def loop(self):
			r_cnt = 0
			ignore=[]
			v = len(self.devices)
			while (len(ignore) < v) and self.active:
				print('RECURSION {0} [{1}/{2}]'.format(r_cnt, v-len(ignore), v))
				r_cnt+=1
				self.administer(ignore_ids=ignore)
				for device in self.devices:
					if (device.log['flag'] == 'PASS') and device.id not in ignore:
						ignore.append(device.id)
		t = threading.Thread(target=loop, args=(self,))
		t.start()
		while self.active:
			i = input('> ').lower()
			if i == 'stop':
				self.active = False

	def writeSessionLog(self):
		with open('{0}/{1}.log'.format(self.directory, self.id), 'w') as f:
			for device in self.devices:
				f.write('\n'.join(device.formatLog()))

	def saveSessionLog(self):
		with open('{0}/{1}.json'.format(self.directory, self.id), 'w') as f:
			sessionLog = []
			for device in self.devices:
				sessionLog.append(device.log)
			json.dump(sessionLog, f, indent=2)
	
	def writeSessionSummary(self):
		with open('{0}/{1}.summary.log'.format(self.directory, self.id), 'w') as f:
			f.write('\nDevices Listed:\n')
			row = ['HOST_ID', 'IP_ADDRESS', 'DEVICE_FLAG', 'DEVICE_DESCRIPTION']
			f.write(''.join(col.ljust(16) for col in row))
			f.write('\n')
			for device in self.devices:
				data = device.log
				row = [data['id'], data['host'], data['flag'], data['description']]
				f.write(''.join(col.ljust(16) for col in row))
				f.write('\n')
				

class Device:
	def __init__(self, host, device_type, username, password, port='22', secret='', **kwargs):
		self.id = host
		if 'id' in kwargs.keys():
			self.id = kwargs['id']
		if 'input' in kwargs.keys():
			self.assign(kwargs['input'])
		if ('telnet' in device_type) and (port=='22'):
			port = '23'
		self.connectionData = {'host': host, 'device_type': device_type, 'username': username, 'password': password, 'port': port, 'secret': secret}
		self.log = {'id': self.id, 'host':host, 'username':username, 'password':password, 'port':port, 'flag': 'INIT', 'description': 'INITIALIZED'}
		self.attempts = 0

	def assign(self, input):
		self.input = input

	def connect(self, mode='CONFIGURE', directory=None, super_log=[]):
		self.attempts += 1
		if self.input:
			try:
				device = ConnectHandler(**self.connectionData)
			except ssh_exception.NetMikoAuthenticationException:
				self.log['flag'], self.log['description'] = 'ERROR', 'BAD_AUTH'
			except ssh_exception.NetMikoTimeoutException:
				self.log['flag'], self.log['description'] = 'ERROR', 'TIMEOUT'
			except ValueError:
				self.log['flag'], self.log['description'] = 'ERROR', 'VALUE'
			except ConnectionRefusedError:
				self.log['flag'], self.log['description'] = 'ERROR', 'REFUSED'
			except paramiko.ssh_exception.SSHException:
				self.log['flag'], self.log['description'] = 'ERROR', 'SSH'
			else:
				if device:
					try:
						if mode == 'CONFIGURE':
							self.log['output'] = [{'in':self.input , 'out': device.send_config_set(self.input)}]
						elif mode == 'SHOW':
							device.enable()
							t_outs = []
							cmds = self.input.splitlines()
							for cmd in cmds:
								print('{0} - Sending \"{1}\"'.format(self.id, cmd))
								while True:
									try:
										t_out = {'in':cmd, 'out':device.send_command(cmd)}
									except IOError:
										print('{0} - Trying Again - \"{1}\"'.format(self.id, cmd))
									else:
										break
								t_outs.append(t_out)
							self.log['output'] = t_outs
						self.log['flag'], self.log['description'] = 'PASS', 'ADMINISTERED'
					except ValueError:
						self.log['flag'], self.log['description'] = 'ERROR', 'MANUAL_REQUIRED'
					finally:
						device.disconnect()
			finally:
				print('{2} @ {3} - {0}:{1}'.format(self.log['flag'], self.log['description'], self.id, self.connectionData['host']))
				# Basically, in the event that we failed and it WASNT a timeout, then we want to try connecting again via another protocol
				if self.log['flag'] == 'ERROR':
					if self.log['description'] != 'SEND_FAILED':
						if self.log['description'] != 'TIMEOUT' and self.attempts < 2:
							old_description = self.log['description']
							if self.connectionData['device_type'] == 'cisco_ios_telnet':
								self.connectionData['device_type'] = 'cisco_ios'
								self.connectionData['port'] = '22'
								print('\t{} -> Error Occurred on Telnet. Trying SSH.'.format(self.id))
								self.log = self.connect(mode=mode, directory=directory, super_log=super_log)
								self.log['description'] += '&'+old_description
							elif self.connectionData['device_type'] == 'cisco_ios':
								self.connectionData['device_type'] = 'cisco_ios_telnet'
								self.connectionData['port'] = '23'
								print('\t{} -> Error Occurred on SSH. Trying Telnet.'.format(self.id))
								self.log = self.connect(mode=mode, directory=directory, super_log=super_log)
								self.log['description'] += '&'+old_description
					else:
						#In the event that connection timed out during send, we want to try again and again till we pass
						print('\t{} -> Send Failed. Trying Again.'.format(self.id))
						self.log = self.connect(mode=mode, directory=directory, super_log=super_log)
				if directory:
					self.writeLog(directory)
			super_log.append(self.log)
		else:
			raise DeviceError('Device attempted connetion before any input assignment.')
		return self.log

	def formatLog(self):
		lines = []
		def line_break(line_char, info):
			ch_len = 86 - len(info)
			br_str = '\n{0} {1} {0}\n'.format(line_char*(int(ch_len/2)), info.upper())
			return br_str
		lines.append(line_break('#', self.log['id']))
		lines.append(line_break('@', '{0}: {1}'.format(self.log['flag'], self.log['description'])))
		if 'output' in self.log:
			for output in self.log['output']:
				lines.append(line_break('=', output['in']))
				lines += output['out'].split('\n')
		return lines

	def saveInput(self, directory):
		if self.input:
			with open('{0}/{1}.conf'.format(directory, self.id), 'w') as f:
				f.write(self.input)
		else:
			raise DeviceError('Device can not save input. No Input assigned.')

	def writeLog(self, directory):
		with open('{0}/{1}.log'.format(directory, self.id), 'w') as f:
			f.write('\n'.join(self.formatLog()))

class DynconfError(Exception):
	pass

class DeviceError(DynconfError):
	pass

class SessionError(DynconfError):
	pass

def main(*args, **kwargs):
	print("### DYNCONF V{0} ###\n".format(VERSION))
	print("©2018 Dyntek Services Inc.\nKenneth J. Grace\nEmail: kenneth.grace@dyntek.com\n")
	optparser = OptionParser(usage="usage: %prog [options]")
	optparser.add_option('-u', '--username', dest='default_username', default='admin',
						 help='Default username for device connections')
	optparser.add_option('-p', '--password', dest='default_password', default='Password1',
						 help='Default password for device connections')
	optparser.add_option('-s', '--secret', dest='default_secret', default='Secret1',
						 help='Default secret for device connections')
	optparser.add_option('-t', '--template', dest='template_filename',
						 help='Read template from a jinja2 or Txt file')
	optparser.add_option('-d', '--data', dest='data_filename',
						 help='Read variables from a CSV or Json file')
	optparser.add_option('-m', '--mode', dest='mode',
						 help='Set the mode for device administration (SHOW, CONFIGURE, RENDER)')
	optparser.add_option('-r', '--recure', action='store_true', dest='recure', default=False,
						 help='Recure over all devices till stopped.')
	optparser.add_option('--threads', dest='maxThreads', default=10,
						 help='assign max number of simultaneous threads')
	optparser.add_option('--output', dest='directory',
						 help='Set the output directory for program output')
	(options, args) = optparser.parse_args()
	while (not options.data_filename) or (not os.path.exists(options.data_filename)):
		options.data_filename = input('Data Filename [*.json, *.csv]: ')
	while (not options.template_filename) or (not os.path.exists(options.template_filename)):
		options.template_filename = input('Template Filename [*.txt, *.j2]: ')
	if options.mode:
		options.mode = options.mode.upper()
	while (not options.mode) or (options.mode not in ['CONFIGURE','SHOW','RENDER']):
		options.mode = input('Mode [CONFIGURE, SHOW, RENDER]: ').upper()
	if not options.directory:
		if options.mode != 'RENDER':
			options.directory = '{}.output'.format(options.data_filename[0:options.data_filename[1:].find('.')+1])
		else:
			options.directory = '{}.render'.format(options.data_filename[0:options.data_filename[1:].find('.')+1])
	try:
		if not os.path.exists(options.directory):
			os.makedirs(options.directory)
	except FileExistsError:
		pass
	session = Session.initFromFiles(**vars(options))
	session.maxThreads = int(options.maxThreads)
	if options.mode != 'RENDER':
		if not options.recure:
			session.administer()
		else:
			session.recure()
	else:
		session.render()
	session.writeSessionLog()
	session.writeSessionSummary()
	try:
		session.saveSessionLog()
	except SessionError:
		pass

if __name__ == '__main__':
	main()