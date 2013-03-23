# Example o of a echo server		
import time
from array import array
from simplewebsocket import SimpleWebSocket
import threading

def onClientConnected(client):
	print "Client connected"

def onClientDisconnected(client):
	print "Client disconnected"

def onHandshake(client, info):
	print "Performing handshake"
	
def onRead(client, data, binary):
	print "Data readed from client: ", data
	client.send(data)
	
if __name__ == '__main__':
	server = SimpleWebSocket(1020)
	
	server.onClientConnected += onClientConnected
	server.onClientDisconnected += onClientDisconnected
	server.onRead += onRead
	server.onHandshake += onHandshake
	
	
	server.setDaemon(True)
	server.start()
	print "Listening for connections on port", server.port
	
	while threading.active_count() > 0:
		time.sleep(0.1)
