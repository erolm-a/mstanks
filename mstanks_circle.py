#!/usr/bin/python

import json
import socket
import logging
import binascii
import struct
import argparse
import random
from threading import Thread
import atexit
import select

class ServerMessageTypes(object):
	TEST = 0
	CREATETANK = 1
	DESPAWNTANK = 2
	FIRE = 3
	TOGGLEFORWARD = 4
	TOGGLEREVERSE = 5
	TOGGLELEFT = 6
	TOGGLERIGHT = 7
	TOGGLETURRETLEFT = 8
	TOGGLETURRETRIGHT = 9
	TURNTURRETTOHEADING = 10
	TURNTOHEADING = 11
	MOVEFORWARDDISTANCE = 12
	MOVEBACKWARSDISTANCE = 13
	STOPALL = 14
	STOPTURN = 15
	STOPMOVE = 16
	STOPTURRET = 17
	OBJECTUPDATE = 18
	HEALTHPICKUP = 19
	AMMOPICKUP = 20
	SNITCHPICKUP = 21
	DESTROYED = 22
	ENTEREDGOAL = 23
	KILL = 24
	SNITCHAPPEARED = 25
	GAMETIMEUPDATE = 26
	HITDETECTED = 27
	SUCCESSFULLHIT = 28
    
	strings = {
		TEST: "TEST",
		CREATETANK: "CREATETANK",
		DESPAWNTANK: "DESPAWNTANK",
		FIRE: "FIRE",
		TOGGLEFORWARD: "TOGGLEFORWARD",
		TOGGLEREVERSE: "TOGGLEREVERSE",
		TOGGLELEFT: "TOGGLELEFT",
		TOGGLERIGHT: "TOGGLERIGHT",
		TOGGLETURRETLEFT: "TOGGLETURRETLEFT",
		TOGGLETURRETRIGHT: "TOGGLETURRENTRIGHT",
		TURNTURRETTOHEADING: "TURNTURRETTOHEADING",
		TURNTOHEADING: "TURNTOHEADING",
		MOVEFORWARDDISTANCE: "MOVEFORWARDDISTANCE",
		MOVEBACKWARSDISTANCE: "MOVEBACKWARDSDISTANCE",
		STOPALL: "STOPALL",
		STOPTURN: "STOPTURN",
		STOPMOVE: "STOPMOVE",
		STOPTURRET: "STOPTURRET",
		OBJECTUPDATE: "OBJECTUPDATE",
		HEALTHPICKUP: "HEALTHPICKUP",
		AMMOPICKUP: "AMMOPICKUP",
		SNITCHPICKUP: "SNITCHPICKUP",
		DESTROYED: "DESTROYED",
		ENTEREDGOAL: "ENTEREDGOAL",
		KILL: "KILL",
		SNITCHAPPEARED: "SNITCHAPPEARED",
		GAMETIMEUPDATE: "GAMETIMEUPDATE",
		HITDETECTED: "HITDETECTED",
		SUCCESSFULLHIT: "SUCCESSFULLHIT"
	}
    
	def toString(self, id):
		if id in self.strings.keys():
			return self.strings[id]
		else:
			return "??UNKNOWN??"


class ServerComms(object):
	'''
	TCP comms handler
	
	Server protocol is simple:
	
	* 1st byte is the message type - see ServerMessageTypes
	* 2nd byte is the length in bytes of the payload (so max 255 byte payload)
	* 3rd byte onwards is the payload encoded in JSON
	'''
	ServerSocket = None
	MessageTypes = ServerMessageTypes()
	
	
	def __init__(self, hostname, port):
		self.ServerSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		self.ServerSocket.connect((hostname, port))

	def readTolength(self, length):
		messageData = self.ServerSocket.recv(length)
		while len(messageData) < length:
			buffData = self.ServerSocket.recv(length - len(messageData))
			if buffData:
				messageData += buffData
		return messageData

	def readMessage(self):
		'''
		Read a message from the server
		'''

		#logging.debug("Before message type")
		messageTypeRaw = self.ServerSocket.recv(1)
		#logging.debug("Before message length")
		messageLenRaw = self.ServerSocket.recv(1)
		messageType = struct.unpack('>B', messageTypeRaw)[0]
		messageLen = struct.unpack('>B', messageLenRaw)[0]
		
		if messageLen == 0:
			messageData = bytearray()
			messagePayload = {'messageType': messageType}
		else:
			messageData = self.readTolength(messageLen)
			logging.debug("*** {}".format(messageData))
			messagePayload = json.loads(messageData.decode('utf-8'))
			messagePayload['messageType'] = messageType
			
		logging.debug('Turned message {} into type {} payload {}'.format(
			binascii.hexlify(messageData),
			self.MessageTypes.toString(messageType),
			messagePayload))
		return messagePayload
	
	def sendMessage(self, messageType=None, messagePayload=None):
			'''
			Send a message to the server
			'''
			message = bytearray()
			
			if messageType is not None:
				message.append(messageType)
			else:
				message.append(0)
			
			if messagePayload is not None:
				messageString = json.dumps(messagePayload)
				message.append(len(messageString))
				message.extend(str.encode(messageString))
					
			else:
				message.append(0)
			
			logging.debug('Turned message type {} payload {} into {}'.format(
				self.MessageTypes.toString(messageType),
				messagePayload,
				binascii.hexlify(message)))
			return self.ServerSocket.sendall(message)


class Bot(Thread):
	def __init__(self, hostname, port, team_name, index):
		Thread.__init__(self)
		self.name = "{}:{}".format(team_name, index)
		self.GameServer = ServerComms(hostname, port)
		self.GameServer.sendMessage(ServerMessageTypes.CREATETANK, {'Name': self.name})
		self.is_running = True
		self.is_watching = True
		self.turrett_degree = 0
		self.X = 0.
		self.Y = 0.

	def run(self):
		while self.is_running:
			message = self.readMessage()
			field.update(message)
			print("{} {} {}".format(self.name, self.X, self.Y))
			if random.randint(0, 10) > 2:
				logging.debug("Bot {} is firing: ".format(self.name))
				self.sendMessage(ServerMessageTypes.FIRE)
			else:
				logging.debug("Moving randomly")
				self.sendMessage(ServerMessageTypes.TURNTURRETTOHEADING, {'Amount': self.turrett_degree})
				self.turrett_degree += 30

	def updatePosition(self, X, Y):
		self.X = X
		self.Y = Y


	def kill(self):
		self.is_running = False
	
	def sendMessage(self, message=None, messagePayload=None):
		"""Avoid using this unless for hardcoded messages"""
		self.GameServer.sendMessage(message, messagePayload)

	def readMessage(self):
		"""Avoid calling this method directly"""
		return self.GameServer.readMessage()


class Field(Thread):
	def __init__(self, team_name):
		Thread.__init__(self)
		self.team_name = team_name
		self.enemies = {}
		self.snitch = None
		self.pickup = []
		self.is_running = True

	def run(self):
		while self.is_running:
			pass

	def kill(self):
		self.is_running = False

	def update(self, event):
		# Extract other tank/object positions
		if event['messageType'] == 18:
			elem_id = event['Id']
			if event['Type'] == 'Tank':
				x, y = event['X'], event['Y']
				# if it's a member of mine
				if event['Name'].startswith(self.team_name):
					tank_no = int(event['Name'][-1])
					bots[tank_no].updatePosition(x, y)
				else:
					self.enemies[elem_id] = (x, y)




# Parse command line args
parser = argparse.ArgumentParser()
parser.add_argument('-d', '--debug', action='store_true', help='Enable debug output')
parser.add_argument('-H', '--hostname', default='127.0.0.1', help='Hostname to connect to')
parser.add_argument('-p', '--port', default=8052, type=int, help='Port to connect to')
parser.add_argument('-n', '--name', default=__file__[0:-3], help='Name of bot')
args = parser.parse_args()

# Set up console logging
if args.debug:
	logging.basicConfig(format='[%(asctime)s] %(message)s', level=logging.DEBUG)
else:
	logging.basicConfig(format='[%(asctime)s] %(message)s', level=logging.INFO)


# Connect to game server
GameServer = ServerComms(args.hostname, args.port)

# Spawn our tanks
logging.info("Creating tanks with name '{}'".format(args.name))
field = Field(args.name)
field.start()

bots = []
for i in range(4):
	bots.append(Bot(args.hostname, args.port, args.name, i))

# Main loop - read game messages, ignore them and randomly perform actions

for bot in bots:
	bot.start()


def kill():
	for bot in bots:
		bot.kill()

	field.kill()

atexit.register(kill)

#i=0
#while True:
#	message = GameServer.readMessage()
#
#	for bot in bots:
#    
#	if i == 5:
#		if random.randint(0, 10) > 5:
#			logging.info("Firing")
#			GameServer.sendMessage(ServerMessageTypes.FIRE)
#	elif i == 10:
#		logging.info("Turning randomly")
#		GameServer.sendMessage(ServerMessageTypes.TURNTOHEADING, {'Amount': random.randint(0, 359)})
#	elif i == 15:
#		logging.info("Moving randomly")
#		GameServer.sendMessage(ServerMessageTypes.MOVEFORWARDDISTANCE, {'Amount': random.randint(0, 10)})
#	i = i + 1
#	if i > 20:
#		i = 0