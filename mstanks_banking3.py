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
import math
import time
from tools import rotate_head, distance

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
		self.index = index
		self.name = "{}:{}".format(team_name, index)
		self.GameServer = ServerComms(hostname, port)
		self.GameServer.sendMessage(ServerMessageTypes.CREATETANK, {'Name': self.name})
		self.is_running = True
		self.is_watching = True
		self.start_rotating = True
		self.is_rotating = False
		self.keep_rotating = False
		self.heading = 0.
		self.turret_degree = 0.
		self.ammo = 10
		self.health = 10
		self.X = 0.
		self.Y = 0.
		self.last_X = 0.
		self.last_Y = 0.
		self.kill_ctr = 0
		self.hooked = None
		self.is_banking = False
		self.pickup_object = None
		self.respawn = True


	def run(self):
		i = 0
		while self.respawn:
			if i % 5 == 0:
				self.sendMessage(ServerMessageTypes.MOVEFORWARDDISTANCE, {'Amount': 5})
				message = self.readMessage()
				logging.debug(message)
				field.update(message, self.index)
			if abs(self.last_X - self.X) > 1 and abs(self.last_Y - self.Y) > 1 and self.last_X != 0. and self.last_Y != 0.:
				print("{} {} {}".format(self.name, self.last_X, self.X))
				self.respawn = False
				self.start_rotating = True
				break
			if i % 20 == 0:
				self.last_X = self.X
				self.last_Y = self.Y
			
			i += 1

		self.sendMessage(ServerMessageTypes.STOPALL)

		while self.is_running:
			message = self.readMessage()
			field.update(message, self.index)
			self.updateHook()
			#logging.info(message)

			if self.kill_ctr > 0: # TODO: change threshold
				if abs(self.Y) > 98 and abs(self.X) < 20:
					self.is_banking = False
					logging.info("Banked")
					self.kill_ctr = 0
					self.start_rotating = True
					self.stopAll()
				else:
					if not self.is_banking:
						logging.info("{} Banking...".format(self.name))
						self.stopAll()
						self.is_banking = True
						self.stopRotationStrategy()
						destination = min([(0, -100), (0, 100)], key=lambda x: distance(self.X, self.Y, x[0], x[1]))
						degree = rotate_head(self.X, self.Y, destination[0], destination[1])
						logging.info("{} {}".format(self.name, destination))
						self.rotateByDeg(-degree, absolute=True)
						self.toggleForward()
						self.is_banking = True


			if self.start_rotating:
				new_degree = rotate_head(self.X, self.Y, 0, 0)
				logging.info("{} going to the center".format(self.name))

				self.rotateByDeg(-new_degree, absolute=True)
				self.sendMessage(ServerMessageTypes.TOGGLEFORWARD)
				self.start_rotating = False
				self.is_rotating = True

			if self.is_rotating:
				if self.X**2 + self.Y**2 <= 25**2.:
					self.sendMessage(ServerMessageTypes.STOPMOVE)
					self.rotateByDeg(90)
					time.sleep(1.3)
					self.is_rotating = False
					self.keep_rotating = True
					self.toggleForward()

			if self.keep_rotating:
				logging.info("{} Rotating".format(self.name))
				#self.rotateByDeg(-10)
				self.goCircle(self.index)

			if not self.hooked:
				self.radarTurret()
				if len(field.enemies) and self.ammo:
					closest_enemy = min(field.enemies.keys(), key=lambda x: distance(self.X, self.Y, field.enemies[x][0], field.enemies[x][1]))
					# hook if distance < 60
					if distance(self.X, self.Y, field.enemies[closest_enemy][0], field.enemies[closest_enemy][1]) < 80:
						self.hookTo(closest_enemy)
						logging.info("{} hooked!".format(self.name))

			if self.hooked in field.enemies:
				x_enemy, y_enemy = field.enemies[self.hooked]
				# Unhook for big distances
				if distance(self.X, self.Y, x_enemy, y_enemy) > 60:
					self.unhook()
				else:
					self.shoot()

			if self.ammo == 0:
				if not self.pickup_object or self.pickup_object not in field.ammo_pickups:
					self.pickup_object = None
					if len(field.ammo_pickups) > 0:
						self.stopRotationStrategy()
						closest_ammo_pickup = min(field.ammo_pickups, key=lambda x: distance(self.X, self.Y, x[0], x[1]))
						logging.info("Found available ammo: {}".format(closest_ammo_pickup))
						self.pickup(closest_ammo_pickup)

	def reset(self):
		self.stopRotationStrategy()
		self.start_rotating = False
		self.is_banking = False
		self.pickup_object = None
		self.respawn = True
		self.hooked = None

	def update(self, X, Y, heading, turret_degree, health, ammo):
		self.X = X
		self.Y = Y
		self.health = health
		self.ammo = ammo
		self.heading = heading
		self.turret_degree = turret_degree

	def kill(self):
		self.is_running = False

	def rotateByDeg(self, degree, absolute=False):
		if not absolute:
			degree = self.heading - degree
		self.sendMessage(ServerMessageTypes.TURNTOHEADING, {'Amount': degree % 360})

	def goCircle(self, index, radius = 40, speed = 1):
		targetX, targetY = self.getOffsetInAngle(0, 0, radius, (time.time() * 10*speed + index*90) % 360)
		new_degree = rotate_head(self.X, self.Y, targetX, targetY)
		self.rotateByDeg(-new_degree, absolute=True)

	def getOffsetInAngle(self, baseX, baseY, radius, angle):
		rangle = angle / 180 * math.pi
		offsetX = math.sin(rangle) * radius
		offsetY = -math.cos(rangle) * radius
		return (baseX + offsetX, baseY + offsetY)

	def toggleForward(self):
		self.sendMessage(ServerMessageTypes.TOGGLEFORWARD)

	def stopMoving(self):
		self.sendMessage(ServerMessageTypes.STOPMOVE)

	def stopTurret(self):
		self.sendMessage(ServerMessageTypes.STOPTURRET)

	def stopRotationStrategy(self):
		self.is_rotating = False
		self.start_rotating = False
		self.keep_rotating = False

	def shoot(self):
		self.sendMessage(ServerMessageTypes.FIRE)

	def stopAll(self):
		self.sendMessage(ServerMessageTypes.STOPALL)

	def moveForward(self, amount):
		self.sendMessage(ServerMessageTypes.MOVEFORWARDDISTANCE, {'Amount': amount})

	def moveTo(self, new_x, new_y):
		degree = rotate_head(self.X, self.Y, new_x, new_y)
		dist = distance(self.X, self.Y, new_x, new_y)
		self.rotateByDeg(-degree, absolute=True)
		self.moveForward(dist)

	def rotateTurretByDeg(self, degree, absolute=False):
		if not absolute:
			degree = self.heading - degree
		self.sendMessage(ServerMessageTypes.TURNTURRETTOHEADING, {'Amount': degree % 360})

	def radarTurret(self):
		self.sendMessage(ServerMessageTypes.TOGGLETURRETLEFT, {'Amount': (self.turret_degree + 60) % 360})
	
	def sendMessage(self, message=None, messagePayload=None):
		"""Avoid using this unless for hardcoded messages"""
		self.GameServer.sendMessage(message, messagePayload)

	def readMessage(self):
		"""Avoid calling this method directly"""
		return self.GameServer.readMessage()

	def hookTo(self, obj):
		self.stopTurret()
		self.hooked = obj
		self.updateHook()

	def updateHook(self):
		if self.hooked:
			x_coord, y_coord = field.enemies[self.hooked]
			self.rotateTurretByDeg(-rotate_head(self.X, self.Y, x_coord, y_coord), absolute=True)

	def unhook(self):
		self.hooked = None
		self.radarTurret()

	def	pickup(self, obj):
		self.pickup_object = obj
		self.radarTurret()
		self.moveTo(obj[0], obj[1])


class Field(Thread):
	def __init__(self, team_name):
		Thread.__init__(self)
		self.team_name = team_name
		self.enemies = {}
		self.snitch = None
		self.ammo_pickups = []
		self.health_pickups = []
		self.is_running = True

	def run(self):
		while self.is_running:
			pass

	def kill(self):
		self.is_running = False

	def update(self, event, index):
		
		messageType = event['messageType']
		if messageType == ServerMessageTypes.OBJECTUPDATE:
			elem_id = event['Id']
			if event['Type'] == 'Tank':
				x, y = event['X'], event['Y']
				# if it's a member of mine
				if event['Name'].startswith(self.team_name):
					tank_no = int(event['Name'][-1])
					heading = event['Heading']
					turret_heading = event['TurretHeading']
					health = event['Health']
					ammo = event['Ammo']
					bots[tank_no].update(x, y, heading, turret_heading, health, ammo)
				else:
					self.enemies[elem_id] = (x, y)
			elif event['Type'] == 'HealthPickup':
				self.health_pickups.append((event['X'], event['Y']))

			elif event['Type'] == 'AmmoPickup':
				self.ammo_pickups.append((event['X'], event['Y']))

		elif messageType == ServerMessageTypes.AMMOPICKUP:
			logging.info("Grabbed object")
			for bot in bots:
				to_delete_pickups = []
				for p in filter(lambda x: x[0] == 'Ammo', self.ammo_pickups):
					if math.hypot(bot.X - p[1], bot.Y - p[2]) < 10:
						to_delete_pickups.append(p)
						bot.unhook()
						bot.stopAll()
						bot.start_rotating = True

				for to_delete in to_delete_pickups:
					self.ammo_pickups.remove(to_delete)

		elif messageType == ServerMessageTypes.KILL:
			bots[index].kill_ctr += 1

		elif messageType == ServerMessageTypes.DESTROYED:
			logging.info("Bot {} has died!".format(bots[index].name))
			bots[index].reset()

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