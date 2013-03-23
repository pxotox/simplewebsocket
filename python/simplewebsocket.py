"""

	Author: Gabriel da Silva Peixoto
	Contact: pxotox@gmail.com
	Version: 1.0
	
	This is a simple websocket implementation according to RFC 6455 (http://tools.ietf.org/html/rfc6455)
	
	This code is distributed under no license and can be used for any purpose, just email me telling if this was usefull or not
	
	You can found examples, packages and how to use in http://github.com/pxotox/simplewebsocket/
	
"""

import socket
import threading
from re import match
from hashlib import sha1
from base64 import b64encode
from array import array
from random import randint

# Web Socket Server
class SimpleWebSocket(threading.Thread):
	MAX_CONNECTIONS = 5
	
	def __init__(self, port, address = ''):
		threading.Thread.__init__(self)
		self.event = threading.Event()
		self.port = port
		self.address = address
		self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		self.socket.bind((self.address, self.port))
		self.socket.listen(SimpleWebSocket.MAX_CONNECTIONS)
		self.clients = []
		
		# Events
		self.onRead = EventHook()
		self.onHandshake = EventHook()
		self.onClientConnected = EventHook()
		self.onClientDisconnected = EventHook()
	
	def run(self):
		while not self.event.is_set():
			(socket, address) = self.socket.accept()
			client = SimpleWebSocketClient(socket, address, self)
			self.clients.append(client)
			
			# Events from client
			client.onRead += self.onClientReadHandler;
			client.onHandshake += self.onClientHandshakeHandler;
			client.onConnect += self.onClientConnectHandler;
			client.onDisconnect += self.onClientDisconnectHandler;
			client.setDaemon(True)
			client.start()
	
	def stop(self):
		for client in self.clients:
			client.stop()
		self.socket.close()
		self.event.set()
		self._Thread__stop()	
		
	def onClientReadHandler(self, client, data, binary):
		self.onRead.fire(client, data, binary)
	
	def onClientHandshakeHandler(self, client, info):
		self.onHandshake.fire(client, info)
	
	def onClientDisconnectHandler(self, client, handshaked):
		if handshaked:
			self.onClientDisconnected.fire(client)
		self.clients.remove(client)
	
	def onClientConnectHandler(self, client):
		self.onClientConnected.fire(client)

# Socket info
# Used to provide and capture information on the events
class SimpleSocketInfo:
	def __init__(self, path = None, protocols = None, accept = True, version = None):
		self.path = path
		self.protocols = protocols
		self.accept = accept
		self.version = None
		
# Socket client
class SimpleWebSocketClient(threading.Thread):
	def __init__(self, socket, address, parent): 
		threading.Thread.__init__(self) 
		self.socket = socket 
		self.address = address 
		self.parent = parent
		self.protocols = [ ]
		self.connected = True
		self.hanshaked = False
		self.event = threading.Event()
		self.dataReceived = []
		self.lastOpcode = 0x0
		self.version = None
		self.data = ""
		
		# Events
		self.onRead = EventHook()
		self.onHandshake = EventHook()
		self.onConnect = EventHook()
		self.onDisconnect = EventHook()

	def run(self): 
		while not self.event.is_set():
			data = self.socket.recv(1024 * 10)
			if len(data) > 0:
				self.data += data
				if self.hanshaked:
					proccess = True
					while proccess:
						proccess = False
						frame = SimpleWebSocketFrame.unpack(map(ord, self.data))
						
						# If payload is None, then the frame still being transfered over TCP (bigger than the buffer received at one time)
						if frame.payload != None:
							self.data = ""
							# Check if there are more to proccess
							if len(frame.buffer) > 0:
								proccess = True
								self.data = array('B', frame.buffer).tostring()
							
							# Append payload to the data received
							self.dataReceived += frame.payload
							
							# If the opcode is 0x0, that means this is a continuation frame
							#	so we must get the last opcode to know what kind of data is this
							if frame.opcode != 0x0:
								self.lastOpcode = frame.opcode
							
							# If this is the final frame, return the data received
							if frame.FIN:
								# Text frame
								if frame.opcode == 0x1:
									self.onRead.fire(self, array('B', self.dataReceived).tostring(), False)
								# Binary frame
								elif frame.opcode == 0x2:
									self.onRead.fire(self, self.dataReceived, True)
								# Close connection frame
								elif frame.opcode == 0x8:
									self.stop()
								# Ping frame
								elif frame.opcode == 0x9:
									self.sendPong(self.dataReceived)
								# Pong frame
								# elif frame.pong == 0xA
								# 	do nothing
								
								self.dataReceived = []
				else:
					self.data = ""
					if self.handshake(data):
						self.hanshaked = True
						
						info = SimpleSocketInfo(self.path, None if len(self.protocols) == 0 else self.protocols, True, self.version)
						self.onHandshake.fire(self, info)
						
						# Check if still connected, the client can be disconnected on handshake
						if not info.accept:
							self.hanshaked = False
							self.stop()

						# Check if still connected, the client can be disconnected on handshake
						if self.connected:
							self.onConnect.fire(self)
					else:
						self.stop()
			else:
				self.stop()

	# Send data
	def send(self, data, binary = False):
		frame = SimpleWebSocketFrame.pack(data if binary else map(ord, data), 0x2 if binary else 0x1)
		self.socket.send(array('B', frame))
	
	# Send a ping frame
	def sendPing(self):
		frame = SimpleWebSocketFrame.pack([], 0x9)
		self.socket.send(array('B', frame))

	# Send a pong frame
	def sendPong(self, data):
		frame = SimpleWebSocketFrame.pack(data, 0xA)
		self.socket.send(array('B', frame))

	# Proccess the handshake
	def handshake(self, data):
		if data.find("\r\n\r\n") > -1:
			lines = data.split("\r\n\r\n")[0].split("\r\n")
			
			# Check first line of the header
			firstLine = lines[0]
			result = match("^GET /(\w+) HTTP/(\d.\d)$", firstLine)
			if result != None:
				self.path = result.group(1)
			else:
				# ERROR (Bad Request)
				self.socket.send("HTTP/1.1 400 Bad Request\r\n\r\n")
				return False
			
			# List params
			params = { }
			for line in lines[1:]:
				result = match("^(.*): (.*)$", line)
				if result != None:
					(param, value) = (result.group(1), result.group(2))
					params.update({ param: value })
				else:
					# ERROR (Bad Request)
					self.socket.send("HTTP/1.1 400 Bad Request\r\n\r\n")
					return False
			
			if not "Upgrade" in params or params["Upgrade"].lower() != "websocket":
				# ERROR (Bad Request)
				self.socket.send("HTTP/1.1 400 Bad Request\r\n\r\nCan \"Upgrade\" only to \"WebSocket\".")
				return False
			
			if not "Connection" in params or params["Connection"].lower() != "upgrade":
				# ERROR (Bad Request)
				self.socket.send("HTTP/1.1 400 Bad Request\r\n\r\n\"Connection\" must be \"Upgrade\".")
				return False
			
			if not "Sec-WebSocket-Key" in params:
				# ERROR (Bad Request)
				self.socket.send("HTTP/1.1 400 Bad Request\r\n\r\n\"Sec-WebSocket-Key\" must be provided.")
				return False
			
			if "Sec-WebSocket-Version" in params:
				self.version = params["Sec-WebSocket-Version"]
			
			if "Sec-WebSocket-Protocol" in params:
				self.protocols = params["Sec-WebSocket-Protocol"].strip().split(',')
			
			# Proccess and send handshake
			self.logged = True
			key = params["Sec-WebSocket-Key"] + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
			newKey = b64encode(sha1(key).digest())
			s = "HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Accept: %s\r\n\r\n" % newKey
			self.socket.send(s)
			
			
		else:
			# ERROR (Bad Request)
			self.socket.send("HTTP/1.1 400 Bad Request\r\n\r\n")
		
		# Handshake done
		return True

	# Stops the connection
	def stop(self):
		self.connected = False
		h = self.hanshaked
		self.onDisconnect.fire(self, h)
		self.socket.close()
		self.event.set()
		self._Thread__stop()

		
# Class to pack and unpack frames
# Reference: http://tools.ietf.org/html/rfc6455#section-5.2
class SimpleWebSocketFrame:
	def __init__(self):
		self.FIN = None
		self.RSV1 = None
		self.RSV2 = None
		self.RSV3 = None
		self.opcode = None
		self.length = 0
		self.payload = None
		self.masked = False
		self.mask = None

	@staticmethod
	def unpack(data):
		frame = SimpleWebSocketFrame()
		
		# First byte
		frame.FIN = data[0] >> 7
		frame.RSV1 = data[0] >> 6 & 1
		frame.RSV2 = data[0] >> 5 & 1
		frame.RSV3 = data[0] >> 4 & 1
		frame.opcode = data[0] & 0xF
		
		# Second byte
		frame.masked = True if (data[1] >> 7) == 1 else False
		frame.length = data[1] & 0x7F
		
		if frame.length == 126:
			offset = 4
			frame.length = (data[2] << 8) + (data[3] << 0);
		elif frame.length == 127:
			offset = 8
			frame.length = (data[2] << 56) + (data[3] << 48) + (data[4] << 40) + (data[5] << 32) + (data[6] << 24) + (data[7] << 16) + (data[8] << 8) + (data[9] << 0);
		else:
			offset = 2
		
		if (frame.length + 2 + offset) > len(data):
			frame = SimpleWebSocketFrame()
			frame.buffer = data
			return frame

		# If the frame is masked, there are 4 bytes with the mask
		if frame.masked:
			frame.mask = data[offset : offset + 4]
			frame.payload = data[offset + 4: offset + 4 + frame.length]
			
			# If the payload exceeds the frame length, save the rest
			frame.buffer = data[offset + 4 + frame.length : len(data)]
			
			# Unmask
			for i in range(len(frame.payload)):
				frame.payload[i] = frame.payload[i] ^ frame.mask[i % 4]
		else:
			frame.payload = data[offset : offset + frame.length]
			
			# If the payload exceeds the frame length, save the rest
			frame.buffer = data[offset + frame.length : len(data)]
		# Return
		return frame
	
	@staticmethod
	def pack(data, opcode = 0x1, masked = False, FIN = True, RSV1 = False, RSV2 = False, RSV3 = False):
		frame_len = len(data)
		frame = []
		frame.append((0x80 if FIN else 0x00) ^ (0x40 if RSV1 else 0x00) ^ (0x20 if RSV2 else 0x00) ^ (0x10 if RSV3 else 0x00) ^ opcode)
		
		if frame_len < 126:
			frame.append((0x80 if masked else 0x00) ^ frame_len)
		elif frame_len < 0xFFFF:
			frame.append((0x80 if masked else 0x00) ^ 126)
			i32 = [frame_len >> i & 0xff for i in (8,0)]
			for x in i32:
				frame.append(x)
		else:
			frame.append((0x80 if masked else 0x00) ^ 127)
			i64 = [frame_len >> i & 0xff for i in (56,48,40,32,24,16,8,0)]
			for x in i64:
				frame.append(x)

		if masked:
			mask = [randint(0, 2147483647) >> i & 0xff for i in (24,16,8,0)]
			for x in mask:
				frame.append(x)
			for i in range(len(data)):
				frame.append( data[i] ^ mask[i % 4] )
		else:
			for x in data:
				frame.append(x)
		
		# Return
		return frame


# Class to hold and fire events, This was taken from the internet
class EventHook(object):
	def __init__(self):
		self.__handlers = []

	def __iadd__(self, handler):
		self.__handlers.append(handler)
		return self

	def __isub__(self, handler):
		self.__handlers.remove(handler)
		return self

	def fire(self, *args, **keywargs):
		for handler in self.__handlers:
			handler(*args, **keywargs)

	def clearObjectHandlers(self, inObject):
		for theHandler in self.__handlers:
			if theHandler.im_self == inObject:
				self -= theHandler		
