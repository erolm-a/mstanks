#!/usr/bin/python

import json
import socket
import logging
import binascii
import struct
import argparse
from threading import Thread
import atexit
import math
import time
import random
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
    SPAWNED = 0
    CIRCLE = 1
    AMMO_PICKUP = 3
    SNITCH_KILL = 4
    BANKING = 5

    RADAR = 10
    HOOKED_ENEMY = 11

    def __init__(self, hostname, port, team_name, index):
        Thread.__init__(self)
        self.name = "{}:{}".format(team_name, index)
        self.index = index
        self.gameserver = ServerComms(hostname, port)
        self.gameserver.sendMessage(ServerMessageTypes.CREATETANK, {'Name': self.name})
        self.reset()
    
    def reset(self):
        self.is_alive = True
        self.state = Bot.SPAWNED
        self.hookup_state = Bot.RADAR
        self.hooked_objective = None
        self.i = 0.
        self.X = 0.
        self.Y = 0.
        self.last_X = 0.
        self.last_Y = 0.
        self.heading = 0.
        self.turret_heading = 0.
        self.ammo = 0
        self.health = 3
        self.expected_heading = None
        self.kill_counter = 0

    def update(self, X, Y, heading, turret_heading, health, ammo):
        self.X = X
        self.Y = Y
        self.heading = heading
        self.turret_heading = turret_heading
        self.ammo = ammo
        self.health = health

    def kill(self):
        self.is_alive = False

    def run(self):
        while self.is_alive:
            self.execute_next()
            self.execute_next_turret()

    def readMessage(self):
        return self.gameserver.readMessage()
    
    def sendMessage(self, mtype, payload=None):
        self.gameserver.sendMessage(mtype, payload)

    def execute_next(self):
        message = self.readMessage()
        field.update(message, self.index)

        logging.info("I am in state {}".format(self.state))

        if self.state == Bot.SPAWNED:
            self.moveForward(5)
            message = self.readMessage()
            field.update(message, self.index)

            logging.info("{} {} {} {}".format(self.last_X, self.X, self.last_Y, self.Y))

            if math.fabs(self.last_X - self.X) > 1 and math.fabs(self.last_Y - self.Y) > 1 and self.last_X*self.last_Y != 0:
                self.state = Bot.CIRCLE
                return

            if self.i % 5 == 0:
                self.last_X = self.X
                self.last_Y = self.Y
        
        if self.state == Bot.CIRCLE:
            if self.X**2 + self.Y**2 >= 40**2:
                logging.info("Moving to the centre")
                self.moveTo(0, 0)
            else:
                self.goCircle()
            
        if self.state == Bot.AMMO_PICKUP:
            self.moveTo(self.hooked_objective[0], self.hooked_objective[1])
        
        if self.kill_counter > 0: # TODO: change this
            self.state = Bot.BANKING

        if self.state == Bot.BANKING:
            goal_posts = [(0, 100), (0, -100)]
            closest_goal_post = min(goal_posts, key=lambda post: distance(self.X, self.Y, post[0], post[1]))
            self.moveTo(closest_goal_post[0], closest_goal_post[1])
        self.i += 1
    
    def execute_next_turret(self):
        if self.state == Bot.SPAWNED:
            return

        if self.hookup_state == Bot.RADAR:
            self.radarTurret()

            if self.ammo == 0 and len(field.ammo_pickups) > 0 and self.hooked_objective == None and self.state != Bot.AMMO_PICKUP:
                logging.info("Run out of ammo")
                closest_ammo = min(field.ammo_pickups, key=lambda x: distance(self.X, self.Y, x[0], x[1]))
                self.hooked_objective = closest_ammo
                self.state = Bot.AMMO_PICKUP
            
            if self.ammo > 0:
                if self.hooked_objective == None and len(field.enemies):
                    closest_enemy = min(field.enemies.keys(), key=lambda x: distance(self.X, self.Y, field.enemies[x][0], field.enemies[x][1]))
                    x_enemy, y_enemy = field.enemies[closest_enemy]
                    if distance(self.X, self.Y, x_enemy, y_enemy) < 80:
                        logging.info("Hooked an enemy! {}".format(closest_enemy))
                        self.hooked_objective = closest_enemy
                        self.hookup_state = Bot.HOOKED_ENEMY

        if self.hookup_state == Bot.HOOKED_ENEMY:
            if self.ammo == 0:
                self.hookup_state = Bot.RADAR
                self.hooked_objective = None
            else:
                x_enemy, y_enemy = field.enemies[self.hooked_objective]
                if distance(self.X, self.Y, x_enemy, y_enemy) > 80:
                    self.hookup_state = Bot.RADAR
                    self.hooked_objective = None
                else:
                    self.rotateTurretTo(x_enemy, y_enemy)
                    self.shoot()
                


    def moveTo(self, new_x, new_y, offset = 0):
        dist = distance(self.X, self.Y, new_x, new_y) + offset
        degree = rotate_head(self.X, self.Y, new_x, new_y)
        self.rotateByDeg(-degree, absolute=True)
        self.moveForward(dist) 

    def radarTurret(self):
        self.sendMessage(ServerMessageTypes.TOGGLETURRETLEFT, {'Amount': (self.turret_heading + 60) % 360})

    def shoot(self):
        self.sendMessage(ServerMessageTypes.FIRE)

    def goCircle(self, radius=40, speed=1):
        targetX, targetY = self.getOffsetInAngle(0, 0, radius, (time.time() * 10*speed + self.index*90) % 360)
        self.moveTo(targetX, targetY, offset=10)
        new_degree = rotate_head(self.X, self.Y, targetX, targetY)
        self.rotateByDeg(-new_degree, absolute=True)
    
    def getOffsetInAngle(self, baseX, baseY, radius, angle):
        rangle = angle / 180 * math.pi
        offsetX = math.sin(rangle) * radius
        offsetY = -math.cos(rangle) * radius
        return (baseX + offsetX, baseY + offsetY)
    
    def rotateByDeg(self, degree, absolute=False):
        if not absolute:
            degree = self.heading - degree
        self.expected_heading = degree
        self.sendMessage(ServerMessageTypes.TURNTOHEADING, {'Amount': degree % 360})
    
    def rotateTo(self, new_x, new_y):
        new_degree = rotate_head(self.X, self.Y, new_x, new_y)
        self.rotateByDeg(-new_degree, absolute=True)
    
    def rotateTurretTo(self, new_x, new_y):
        new_degree = rotate_head(self.X, self.Y, new_x, new_y)
        new_degree = (-new_degree) % 360
        self.sendMessage(ServerMessageTypes.TURNTURRETTOHEADING, {'Amount': new_degree})

    def moveForward(self, amount):
        self.gameserver.sendMessage(ServerMessageTypes.MOVEFORWARDDISTANCE, {'Amount': amount})
    
    def changeState(self, newState):
        logging.info(self.state)
        self.state = newState
        logging.info(self.state)


        
       
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
            bots[index].ammo = 10
            bots[index].changeState(Bot.CIRCLE)
            bots[index].hooked_objective = None

            to_delete_pickups = []
            for p in filter(lambda x: x[0] == 'Ammo', self.ammo_pickups):
                if math.hypot(bot.X - p[1], bot.Y - p[2]) < 10:
                    to_delete_pickups.append(p)

            for to_delete in to_delete_pickups:
                self.ammo_pickups.remove(to_delete)

        elif messageType == ServerMessageTypes.ENTEREDGOAL:
            bots[index].changeState(Bot.CIRCLE)
            bots[index].kill_counter = 0

        elif messageType == ServerMessageTypes.KILL:
            bots[index].kill_counter += 1

        elif messageType == ServerMessageTypes.HITDETECTED:
            #bots[index].recover()
            pass

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