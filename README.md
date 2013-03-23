Simple WebSocket
===============


This is a simple websocket implementation according to RFC 6455 (http://tools.ietf.org/html/rfc6455)

This can be used for any purpose but there are no guarantees of its reliability

How to use
------------

	from simplewebsocket import SimpleWebSocket
	
	def onRead(client, data, binary):
		print "Data received:", data
		
	if __name__ == '__main__':
		server = SimpleWebSocket(1020)
		
		server.onRead += onRead
		server.start()

Simple doc
------------
The events of the server are:
* onClientConnected(client) - triggered when a clients connect
* onHandshake(client, info) - triggered when the client starts the handshake, the info (SimpleSocketInfo) provides:
** path - the path requested
** protocols - the websocket protocols used by the client
** version - version of the client websocket
** accept - accept or not the connection, if changed to False the connection will be dropped
* onRead(client, data, binary) - trigerred when a clients sends a message, it can be binary or plain text
* onClientDisconnected(client) - triggered when a clients disconnect
