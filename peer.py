from socket import *
import threading
import time
import select
import logging
import message as cmsg
import re
import getpass
import stdiomask
from datetime import datetime
import ddtrace


# Server side of peer


class PeerServer(threading.Thread):

    # Peer server initialization
    def __init__(self, username, peerServerPort):
        threading.Thread.__init__(self)
        # keeps the username of the peer
        self.username = username
        # tcp socket for peer server
        self.tcpServerSocket = socket(AF_INET, SOCK_STREAM)
        # udp socket for room server
        self.udpServerSocket = socket(AF_INET, SOCK_DGRAM)
        # port number of the peer server
        self.peerServerPort = peerServerPort
        # port number of the room server
        # if 1, then user is already chatting with someone
        # if 0, then user is not chatting with anyone
        self.isChatRequested = 0
        # keeps the socket for the peer that is connected to this peer
        self.connectedPeerSocket = None
        # keeps the ip of the peer that is connected to this peer's server
        self.connectedPeerIP = None
        # keeps the port number of the peer that is connected to this peer's server
        self.connectedPeerPort = None
        # online status of the peer
        self.isOnline = True
        # keeps the username of the peer that this peer is chatting with
        self.chattingClientName = None
        self.chat = 0
        self.room = 0
        self.roompeers = []
        self.rooms_messages = {}

    # main method of the peer server thread

    def run(self):

        cmsg.green_message("Peer server started...")

        # gets the ip address of this peer
        # first pip install bcrypts to get it for windows devices
        # if the device that runs this application is not windows
        # it checks to get it for macos devices
        hostname = gethostname()
        try:
            self.peerServerHostname = gethostbyname(hostname)
        except gaierror:
            import netifaces as ni
            self.peerServerHostname = ni.ifaddresses(
                'en0')[ni.AF_INET][0]['addr']

        # ip address of this peer
        # self.peerServerHostname = 'localhost'
        # socket initializations for the server of the peer
        self.tcpServerSocket.bind(
            (self.peerServerHostname, self.peerServerPort))
        self.tcpServerSocket.listen(4)
        # inputs sockets that should be listened
        inputs = [self.tcpServerSocket]
        # server listens as long as there is a socket to listen in the inputs list and the user is online
        while inputs and self.isOnline:
            # monitors for the incoming connections
            try:
                readable, writable, exceptional = select.select(inputs, [], [])
                # If a server waits to be connected enters here
                for s in readable:
                    # if the socket that is receiving the connection is
                    # the tcp socket of the peer's server, enters here
                    if s is self.tcpServerSocket:
                        # accepts the connection, and adds its connection socket to the inputs list
                        # so that we can monitor that socket as well
                        connected, addr = s.accept()
                        connected.setblocking(0)
                        inputs.append(connected)
                        # if the user is not chatting, then the ip and the socket of
                        # this peer is assigned to server variables
                        if self.isChatRequested == 0 and self.room == 0:
                            cmsg.blue_message(
                                self.username + " is connected from " + str(addr))
                            self.connectedPeerSocket = connected
                            self.connectedPeerIP = addr[0]

                    # if the socket that receives the data is the one that
                    # is used to communicate with a connected peer, then enters here
                    else:
                        # message is received from connected peer
                        messageReceived = s.recv(1024).decode()
                        # logs the received message
                        logging.info(
                            "Received from " + str(self.connectedPeerIP) + " -> " + str(messageReceived))
                        # if message is a request message it means that this is the receiver side peer server
                        # so evaluate the chat request
                        if len(messageReceived) > 11 and messageReceived[:12] == "CHAT-REQUEST":
                            # text for proper input choices is printed however OK or REJECT is taken as input in main process of the peer
                            # if the socket that we received the data belongs to the peer that we are chatting with,
                            # enters here
                            if s is self.connectedPeerSocket:
                                # parses the message
                                messageReceived = messageReceived.split()
                                # gets the port of the peer that sends the chat request message
                                self.connectedPeerPort = int(
                                    messageReceived[1])
                                # gets the username of the peer sends the chat request message
                                self.chattingClientName = messageReceived[2]
                                # prints prompt for the incoming chat request
                                cmsg.blue_message(
                                    "Incoming chat request from " + self.chattingClientName + " >> ")
                                cmsg.yellow_message(
                                    "Enter OK to accept or REJECT to reject:  ")
                                # makes isChatRequested = 1 which means that peer is chatting with someone
                                self.isChatRequested = 1
                            # if the socket that we received the data does not belong to the peer that we are chatting with
                            # and if the user is already chatting with someone else(isChatRequested = 1), then enters here
                            elif s is not self.connectedPeerSocket and self.isChatRequested == 1:
                                # sends a busy message to the peer that sends a chat request when this peer is
                                # already chatting with someone else
                                message = "BUSY"
                                s.send(message.encode())
                                # remove the peer from the inputs list so that it will not monitor this socket
                                inputs.remove(s)
                        # if an OK message is received then ischatrequested is made 1 and then next messages will be shown to the peer of this server
                        elif messageReceived == "OK":
                            self.isChatRequested = 1
                        # if an REJECT message is received then ischatrequested is made 0 so that it can receive any other chat requests
                        elif messageReceived == "REJECT":
                            self.isChatRequested = 0
                            inputs.remove(s)
                        elif messageReceived[:13] == "NEW-ROOM-PEER":
                            newPeer = messageReceived.split()
                            cmsg.green_message(
                                f"{newPeer[1]} connected to room")
                            exist = False
                            for peer in self.roompeers:
                                if peer.portToConnect == int(newPeer[3]):
                                    peer.room = 1
                                    exist = True
                                    break
                            if not exist:
                                newClient = PeerClient(newPeer[2], int(
                                    newPeer[3]), self.username, self, None, 1, None, None)
                                newClient.start()
                                newClient.connected.wait()
                                self.roompeers.append(newClient)
                        # Room message (ROOM-MESSAGE)
                        # elif messageReceived[:2] != ":q" and len(messageReceived) != 0 and messageReceived[:12] == "ROOM-MESSAGE":
                        elif len(messageReceived) != 0 and messageReceived[:12] == "ROOM-MESSAGE":
                            message = messageReceived.split(" ")
                            # print("\n" + message[1] +
                            #       ": " + " ".join(message[2:]))
                            if message[2] == ":q":
                                cmsg.red_message(
                                    message[1] + " has left the chat")
                                # Don't remove peer to send notifications
                                for peer in self.roompeers:
                                    if peer.portToConnect == int(message[3]):
                                        peer.room = 0
                                        # self.roompeers.remove(peer)
                                        # peer.tcpClientSocket.close()
                                        break
                            else:
                                print("\n" + message[1] +
                                      ": " + " ".join(message[2:]))
                        elif messageReceived[:2] != ":q" and len(messageReceived) != 0 and messageReceived[:12] == "NOTIFICATION":
                            message = messageReceived.split(" ")
                            cmsg.yellow_message(f"You have a new message in {message[1]}")
                            msg = message[2] + ": " + " ".join(message[3:])
                            if message[1] in self.rooms_messages:
                                self.rooms_messages[message[1]].append(msg)
                            else:
                                self.rooms_messages[message[1]] = [msg]
                                
                        # if a message is received, and if this is not a quit message ':q' and
                        # if it is not an empty message, show this message to the user
                        elif messageReceived[:2] != ":q" and len(messageReceived) != 0: 
                            print(self.chattingClientName +
                                  ": " + messageReceived)
                        # if the message received is a quit message ':q',
                        # makes ischatrequested 1 to receive new incoming request messages
                        # removes the socket of the connected peer from the inputs list
                        elif messageReceived[:2] == ":q":
                            if len(messageReceived) == 2:
                                # connected peer ended the chat
                                cmsg.blue_message(
                                    "User you're chatting with ended the chat")
                                cmsg.yellow_message(
                                    "Press enter to quit the chat: ")
                                self.isChatRequested = 0
                                inputs.clear()
                                inputs.append(self.tcpServerSocket)
                                
                        # if the message is an empty one, then it means that the
                        # connected user suddenly ended the chat(an error occurred)
                        elif len(messageReceived) == 0:
                            if self.room == 1:
                                self.room = 0
                            elif self.isChatRequested == 1:
                                self.isChatRequested = 0
                                cmsg.blue_message(
                                    "User you're chatting with suddenly ended the chat")
                                cmsg.yellow_message(
                                    "Press enter to quit the chat: ")
                            inputs.clear()
                            inputs.append(self.tcpServerSocket)

            except OSError as oErr:
                logging.error("OSError: {0}".format(oErr))
            except ValueError as vErr:
                logging.error("ValueError: {0}".format(vErr))


# Client side of peer
class PeerClient(threading.Thread):
    # variable initializations for the client side of the peer
    def __init__(self, ipToConnect, portToConnect, username, peerServer, responseReceived, room, roomId, roomUsers: list):
        threading.Thread.__init__(self)
        # keeps the ip address of the peer that this will connect
        self.ipToConnect = ipToConnect
        # keeps the username of the peer
        self.username = username
        # keeps the port number that this client should connect
        self.portToConnect = portToConnect
        # client side tcp socket initialization
        self.tcpClientSocket = socket(AF_INET, SOCK_STREAM)
        # keeps the server of this client
        self.peerServer = peerServer
        # keeps the phrase that is used when creating the client
        # if the client is created with a phrase, it means this one received the request
        # this phrase should be none if this is the client of the requester peer
        self.responseReceived = responseReceived
        # keeps if this client is ending the chat or not
        self.isEndingChat = False

        # status room or chat
        self.room = room

        self.roomId = roomId

        self.roomUsers = roomUsers

        self.emptyRoom = False

        self.connected = threading.Event()

    # main method of the peer client thread

    def run(self):
        cmsg.green_message("Peer client started...")
        # connects to the server of other peer
        self.tcpClientSocket.connect((self.ipToConnect, self.portToConnect))
        self.connected.set()
        # if the server of this peer is not connected by someone else and if this is the requester side peer client then enters here
        if self.peerServer.isChatRequested == 0 and self.responseReceived is None and self.room != 1:
            # composes a request message and this is sent to server and then this waits a response message from the server this client connects
            requestMessage = "CHAT-REQUEST " + \
                str(self.peerServer.peerServerPort) + " " + self.username
            # logs the chat request sent to other peer
            logging.info("Send to " + self.ipToConnect + ":" +
                         str(self.portToConnect) + " -> " + requestMessage)
            # sends the chat request
            self.tcpClientSocket.send(requestMessage.encode())
            print("Request message " + requestMessage + " is sent...")
            # received a response from the peer which the request message is sent to
            self.responseReceived = self.tcpClientSocket.recv(1024).decode()
            # logs the received message
            logging.info("Received from " + self.ipToConnect + ":" +
                         str(self.portToConnect) + " -> " + self.responseReceived)
            print("Response is " + self.responseReceived)
            # parses the response for the chat request
            self.responseReceived = self.responseReceived.split()
            # if response is ok then incoming messages will be evaluated as client messages and will be sent to the connected server
            if self.responseReceived[0] == "OK":
                # changes the status of this client's server to chatting
                self.peerServer.isChatRequested = 1
                # sets the server variable with the username of the peer that this one is chatting
                self.peerServer.chattingClientName = self.responseReceived[1]
                # as long as the server status is chatting, this client can send messages
                while self.peerServer.isChatRequested == 1:
                    # message input prompt
                    messageSent = input(self.username + ": ")
                    # sends the message to the connected peer, and logs it
                    self.tcpClientSocket.send(messageSent.encode())
                    logging.info("Send to " + self.ipToConnect + ":" +
                                 str(self.portToConnect) + " -> " + messageSent)
                    # if the quit message is sent, then the server status is changed to not chatting
                    # and this is the side that is ending the chat
                    if messageSent == ":q":
                        self.peerServer.isChatRequested = 0
                        self.isEndingChat = True
                        break
                # if peer is not chatting, checks if this is not the ending side
                if self.peerServer.isChatRequested == 0:
                    if not self.isEndingChat:
                        # tries to send a quit message to the connected peer
                        # logs the message and handles the exception
                        try:
                            self.tcpClientSocket.send(
                                ":q ending-side".encode())
                            logging.info("Send to " + self.ipToConnect +
                                         ":" + str(self.portToConnect) + " -> :q")
                        except BrokenPipeError as bpErr:
                            logging.error("BrokenPipeError: {0}".format(bpErr))
                    # closes the socket
                    self.responseReceived = None
                    self.tcpClientSocket.close()
            # if the request is rejected, then changes the server status, sends a reject message to the connected peer's server
            # logs the message and then the socket is closed
            elif self.responseReceived[0] == "REJECT":
                self.peerServer.isChatRequested = 0
                print("client of requester is closing...")
                self.tcpClientSocket.send("REJECT".encode())
                logging.info("Send to " + self.ipToConnect + ":" +
                             str(self.portToConnect) + " -> REJECT")
                self.tcpClientSocket.close()
            # if a busy response is received, closes the socket
            elif self.responseReceived[0] == "BUSY":
                print("Receiver peer is busy")
                self.tcpClientSocket.close()
        # if the client is created with OK message it means that this is the client of receiver side peer
        # so it sends an OK message to the requesting side peer server that it connects and then waits for the user inputs.
        elif self.responseReceived == "OK":
            # server status is changed
            self.peerServer.isChatRequested = 1
            # ok response is sent to the requester side
            okMessage = "OK"
            self.tcpClientSocket.send(okMessage.encode())
            logging.info("Send to " + self.ipToConnect + ":" +
                         str(self.portToConnect) + " -> " + okMessage)
            cmsg.blue_message(
                "Client with OK message is created... and sending messages")
            # client can send messsages as long as the server status is chatting
            while self.peerServer.isChatRequested == 1:
                # input prompt for user to enter message
                messageSent = input(self.username + ": ")
                self.tcpClientSocket.send(messageSent.encode())
                logging.info("Send to " + self.ipToConnect + ":" +
                             str(self.portToConnect) + " -> " + messageSent)
                # if a quit message is sent, server status is changed
                if messageSent == ":q":
                    self.peerServer.isChatRequested = 0
                    self.isEndingChat = True
                    break
            # if server is not chatting, and if this is not the ending side
            # sends a quitting message to the server of the other peer
            # then closes the socket
            if self.peerServer.isChatRequested == 0:
                if not self.isEndingChat:
                    self.tcpClientSocket.send(":q ending-side".encode())
                    logging.info("Send to " + self.ipToConnect +
                                 ":" + str(self.portToConnect) + " -> :q")
                self.responseReceived = None
                self.tcpClientSocket.close()

    def sendRoomMessage(self, message):
        try:
            if message[:12] != "NOTIFICATION" or message.split()[3] == ":q":
                message = "ROOM-MESSAGE " + self.username + " " + message
            self.tcpClientSocket.send(message.encode())
            logging.info("Send to " + self.ipToConnect + ":" +
                        str(self.portToConnect) + " -> " + message)
        except Exception as e:
            
            cmsg.red_message(f"ERROR: can't send to {self.portToConnect}")
            print("Peers in server:")
            for peer in self.peerServer.roompeers:
                print(peer.portToConnect)


# main process of the peer
class peerMain:

    # peer initializations
    def __init__(self):
        # port number of the registry
        self.registryPort = 15600
        # tcp socket connection to registry
        while True:
            try:
                self.tcpClientSocket = socket(AF_INET, SOCK_STREAM)
                self.tcpClientSocket.settimeout(5)
                # ip address of the registry
                cmsg.magenta_message("Enter IP address of registry: ")
                self.registryName = input()
                cmsg.blue_message("Connecting to registry...")
                self.tcpClientSocket.connect(
                    (self.registryName, self.registryPort))
                break
            except Exception as e:
                if self.tcpClientSocket is not None:
                    self.tcpClientSocket.close()
                cmsg.red_message("Registry is not online...")
        self.tcpClientSocket.settimeout(None)
        cmsg.green_message("Connected to registry...")
        # initializes udp socket which is used to send hello messages
        self.udpClientSocket = socket(AF_INET, SOCK_DGRAM)
        # udp port of the registry
        self.registryUDPPort = 15500
        # login info of the peer
        self.loginCredentials = (None, None)
        # online status of the peer
        self.isOnline = False
        # server port number of this peer
        self.peerServerPort = None
        # server of this peer
        self.peerServer = None
        # client of this peer
        self.peerClient = None
        # timer initialization
        self.timer = None


        choice = "0"
        # log file initialization
        logging.basicConfig(filename="peer.log", level=logging.INFO)
        # as long as the user is not logged out, asks to select an option in the menu
        while choice != "3":
            # menu selection prompt
            cmsg.magenta_message(
                "Choose: \nCreate account: 1\nLogin: 2\nLogout: 3\nSearch: 4\nStart a chat: 5\nCreate Chat Room: 6\nJoin Room: 7")
            choice = input()
            # if choice is 1, creates an account with the username
            # and password entered by the user
            if choice == "1":
                username = input("username: ")
                password = stdiomask.getpass("password: ", mask="*")

                self.createAccount(username, password)
            # if choice is 2 and user is not logged in, asks for the username
            # and the password to login
            elif choice == "2" and not self.isOnline:
                username = input("username: ")
                password = stdiomask.getpass("password: ", mask="*")
                # asks for the port number for server's tcp socket
                try:
                    cmsg.blue_message("Enter a port number for peer server: ")
                    peerServerPort = int(input())
                    # roomServerPort = int((input("Enter a port number for room server: ")))
                except ValueError:
                    cmsg.red_message("Port number should be an integer...")
                    continue

                check_port = socket(AF_INET, SOCK_STREAM)
                portUsed = check_port.connect_ex(
                    (self.registryName, peerServerPort)) == 0
                if portUsed:
                    cmsg.red_message("Peer port is already in use...")
                    continue
                status = self.login(username, password, peerServerPort)
                # is user logs in successfully, peer variables are set
                if status == 1:
                    self.isOnline = True
                    self.loginCredentials = (username, password)
                    self.peerServerPort = peerServerPort
                    # self.roomServerPort = roomServerPort
                    # creates the server thread for this peer, and runs it
                    self.peerServer = PeerServer(
                        self.loginCredentials[0], self.peerServerPort)
                    self.peerServer.start()
                    # hello message is sent to registry
                    self.sendHelloMessage()
            # if choice is 3 and user is logged in, then user is logged out
            # and peer variables are set, and server and client sockets are closed
            elif choice == "3" and self.isOnline:
                self.logout(1)
                self.isOnline = False
                self.loginCredentials = (None, None)
                self.peerServer.isOnline = False
                self.peerServer.tcpServerSocket.close()
                if self.peerClient is not None:
                    self.peerClient.tcpClientSocket.close()
                cmsg.green_message("Logged out successfully")
            # is peer is not logged in and exits the program
            elif choice == "3":
                self.logout(2)
            # if choice is 4 and user is online, then user is asked
            # for a username that is wanted to be searched
            elif choice == "4" and self.isOnline:
                cmsg.blue_message("Enter username to search: ")
                username = input()
                searchStatus = self.searchUser(username)
                # if user is found its ip address is shown to user
                if searchStatus is not None and searchStatus != 0:
                    cmsg.yellow_message("IP address of " +
                                        username + " is " + searchStatus)
            # if choice is 5 and user is online, then user is asked
            # to enter the username of the user that is wanted to be chatted
            elif choice == "5" and self.isOnline:
                cmsg.blue_message("Enter username to chat: ")
                username = input()
                searchStatus = self.searchUser(username)
                print(searchStatus)
                # if searched user is found, then its ip address and port number is retrieved
                # and a client thread is created
                # main process waits for the client thread to finish its chat
                print(self.peerServer.peerServerHostname +
                      ":" + str(self.peerServer.peerServerPort))
                if searchStatus == self.peerServer.peerServerHostname + ":" + str(self.peerServer.peerServerPort):
                    cmsg.red_message("You cannot chat with yourself...")
                elif searchStatus is not None and searchStatus != 0:
                    searchStatus = searchStatus.split(":")
                    self.peerClient = PeerClient(searchStatus[0], int(
                        searchStatus[1]), self.loginCredentials[0], self.peerServer, None, 0, None, None)
                    self.peerClient.start()
                    self.peerClient.join()
            elif choice == "6" and self.isOnline:
                while True:
                    cmsg.blue_message("Enter room name (q to exit): ")
                    roomid = input()
                    if roomid == "q":
                        break
                    elif len(roomid) < 3:
                        cmsg.red_message(
                            "Room name can't be less than 3 characters")
                    else:
                        status = self.createRoom(roomid)
                        if status == "create-room-success":
                            break
            elif choice == "7" and self.isOnline:
                while True:
                    # Show all rooms
                    rooms = self.getRooms()
                    if len(rooms) == 0:
                        cmsg.red_message("No rooms found")
                        break

                    cmsg.blue_message("Available Rooms: ")
                    for room in rooms:
                        cmsg.blue_message(room)

                    cmsg.blue_message("Enter room id (q to exit): ")
                    roomid = input()
                    if roomid.lower() == "q":
                        break

                    status = self.joinRoom(roomid)
                    if status == "join-room-success":
                        self.peerServer.room = 1
                        self.connectAllPeers(roomid)

                        while True:
                            cmsg.blue_message("Enter message: ")
                            message = input()
                            message = self.format_message(message)
                            self.sendMessage(message, roomid)

                            if message == ":q":
                                self.leaveRoom(roomid)
                                # self.peerServer.room = 0
                                break

            # if this is the receiver side then it will get the prompt to accept an incoming request during the main loop
            # that's why response is evaluated in main process not the server thread even though the prompt is printed by server
            # if the response is ok then a client is created for this peer with the OK message and that's why it will directly
            # sent an OK message to the requesting side peer server and waits for the user input
            # main process waits for the client thread to finish its chat
            elif choice == "OK" and self.isOnline:
                okMessage = "OK " + self.loginCredentials[0]
                logging.info(
                    "Send to " + self.peerServer.connectedPeerIP + " -> " + okMessage)
                self.peerServer.connectedPeerSocket.send(okMessage.encode())
                self.peerClient = PeerClient(
                    self.peerServer.connectedPeerIP, self.peerServer.connectedPeerPort, self.loginCredentials[0], self.peerServer, "OK", 0, None, None)
                self.peerClient.start()
                self.peerClient.join()
            # if user rejects the chat request then reject message is sent to the requester side
            elif choice == "REJECT" and self.isOnline:
                self.peerServer.connectedPeerSocket.send("REJECT".encode())
                self.peerServer.isChatRequested = 0
                logging.info(
                    "Send to " + self.peerServer.connectedPeerIP + " -> REJECT")
            # if choice is cancel timer for hello message is cancelled
            elif choice == "CANCEL":
                self.timer.cancel()
                break
        # if main process is not ended with cancel selection
        # socket of the client is closed
        if choice != "CANCEL":
            self.tcpClientSocket.close()

    def sendMessage(self, message, roomid):
        if message == ":q":
            cmsg.red_message(f"You have left the room")
            message = f":q {self.peerServerPort}"
        else:
            timestamp = datetime.now().strftime("%Y-%m-%d %I:%M:%S %p")
            seconds = datetime.now().strftime("%S")
            message = f"{message} [{timestamp}.{seconds}]"

        for peer in self.peerServer.roompeers:
            if peer.room == 0:
                message = "NOTIFICATION " + roomid + " " + self.loginCredentials[0] + " " + message
            peer.sendRoomMessage(message)

    def connectAllPeers(self, roomid):
        message = "GET-ROOM-PEERS " + roomid
        logging.info("Send to " + self.registryName + ":" +
                     str(self.registryPort) + " -> " + message)
        self.tcpClientSocket.send(message.encode())
        response = self.tcpClientSocket.recv(1024).decode()
        peers = response.split(",")
        # print("PEERS -> " + str(peers))
        for peer in peers:
            # print(f"{self.peerServerPort} CONNECTING TO {peer}")
            if int(peer) == int(self.peerServerPort):
                # print("CLIENT SKIPPED")
                continue
            self.peerClient = PeerClient(self.registryName, int(
                peer), self.loginCredentials[0], self.peerServer, None, 1, None, None)
            self.peerClient.start()
            # self.peerClient.join()
            self.peerClient.connected.wait()
            newPeerMessage = "NEW-ROOM-PEER " + \
                self.loginCredentials[0] + "  " + self.registryName + \
                " " + str(self.peerServer.peerServerPort)
            self.peerClient.tcpClientSocket.send(newPeerMessage.encode())
            self.peerServer.roompeers.append(self.peerClient)
            # print(f"CONNECTED TO -> {peer}")
        # print("Finished connecting to peers")
        logging.info("Received from " + self.registryName + " -> " + response)

    def leaveRoom(self, roomid):
        try:
            # Notify the registry about leaving the room
            leaveMessage = "LEAVE-ROOM" + " " + \
                roomid + " " + str(self.peerServerPort)
            self.tcpClientSocket.send(leaveMessage.encode())
        # Receive the response from the registry
            response = self.tcpClientSocket.recv(1024).decode()
            if response == "leave-room-success":
                self.peerServer.isChatRequested = 0
            for peer in self.peerServer.roompeers:
                peer.tcpClientSocket.close()
            self.peerServer.roompeers.clear()
        except Exception as e:
            logging.error(f"Error during leaveRoom: {e}")

    def createAccount(self, username, password):
        # join message to create an account is composed and sent to registry
        # if response is success then informs the user for account creation
        # if response is exist then informs the user for account existence
        message = "JOIN " + username + " " + password
        logging.info("Send to " + self.registryName + ":" +
                     str(self.registryPort) + " -> " + message)
        self.tcpClientSocket.send(message.encode())
        response = self.tcpClientSocket.recv(1024).decode()
        logging.info("Received from " + self.registryName + " -> " + response)
        if response == "join-success":
            cmsg.green_message("Account created...")
        elif response == "join-exist":
            cmsg.red_message("choose another username or login...")
        elif response == "join-failed-username":
            cmsg.red_message("Username should be at least 3 characters...")
        elif response == "join-failed-password":
            cmsg.red_message("Password should be at least 5 characters...")
        elif response == 'invalid-message':
            cmsg.red_message("Wrong inputs, try again...")

    # login function
    def login(self, username, password, peerServerPort):
        try:
            # Check if the provided port is the same as the registry port
            if peerServerPort == self.registryPort:
                cmsg.red_message(
                    "Port reserved for registry. Choose a different port.")
                return 6  # You can choose a specific return code for this case

            message = "LOGIN " + username + " " + \
                password + " " + str(peerServerPort)
            logging.info("Send to " + self.registryName + ":" +
                         str(self.registryPort) + " -> " + message)
            self.tcpClientSocket.send(message.encode())
            response = self.tcpClientSocket.recv(1024).decode()
            logging.info("Received from " +
                         self.registryName + " -> " + response)

            # Handle the case where the requested port is already in use
            if response.startswith("login-port-in-use"):
                port_in_use_message = response.split(":", 1)[1]
                cmsg.red_message(
                    f"Port {peerServerPort} is already in use. {port_in_use_message}")
                return 7  # You can choose another specific return code for this case

            if response == "login-success":
                cmsg.green_message("Logged in successfully...")
                return 1
            elif response == "login-account-not-exist":
                cmsg.red_message("Account does not exist...")
                return 0
            elif response == "login-online":
                cmsg.red_message("Account is already online...")
                return 2
            elif response == "login-wrong-password":
                cmsg.red_message("Wrong password...")
                return 3
            elif response == 'invalid-message':
                cmsg.red_message("Wrong inputs, try again...")
                return 4
            elif response == 'address-online':
                cmsg.red_message("Address is already in use...")
                return 5
        except OSError as e:
            logging.error("OSError: {0}".format(e))
            return 8

    # logout function

    def logout(self, option):
        # a logout message is composed and sent to registry
        # timer is stopped
        if option == 1:
            message = "LOGOUT " + self.loginCredentials[0]
            self.timer.cancel()
        else:
            message = "LOGOUT"
        logging.info("Send to " + self.registryName + ":" +
                     str(self.registryPort) + " -> " + message)
        self.tcpClientSocket.send(message.encode())

    # function for searching an online user

    def searchUser(self, username):
        # a search message is composed and sent to registry
        # custom value is returned according to each response
        # to this search message
        message = "SEARCH " + username
        logging.info("Send to " + self.registryName + ":" +
                     str(self.registryPort) + " -> " + message)
        self.tcpClientSocket.send(message.encode())
        response = self.tcpClientSocket.recv(1024).decode().split()
        logging.info("Received from " + self.registryName +
                     " -> " + " ".join(response))
        if response[0] == "search-success":
            cmsg.green_message(username + " is found successfully...")
            return response[1]
        elif response[0] == "search-user-not-online":
            cmsg.red_message(username + " is not online...")
            return 0
        elif response[0] == "search-user-not-found":
            cmsg.red_message(username + " is not found")
            return None
        elif response[0] == 'invalid-message':
            cmsg.red_message("Wrong inputs, try again...")
            return None

    # function for sending hello message
    # a timer thread is used to send hello messages to udp socket of registry
    def sendHelloMessage(self):
        message = "HELLO " + self.loginCredentials[0]
        logging.info("Send to " + self.registryName + ":" +
                     str(self.registryUDPPort) + " -> " + message)
        self.udpClientSocket.sendto(
            message.encode(), (self.registryName, self.registryUDPPort))
        self.timer = threading.Timer(1, self.sendHelloMessage)
        self.timer.start()

    def roomList(self):
        message = "ROOM-LIST"
        logging.info("Send to " + self.registryName + ":" +
                     str(self.registryPort) + " -> " + message)
        self.tcpClientSocket.send(message.encode())
        response = self.tcpClientSocket.recv(1024).decode()
        cmsg.green_message(str(response))
        logging.info("Received from " + self.registryName + " -> " + response)

    def onlineList(self):
        message = "ONLINE"
        logging.info("Send to " + self.registryName + ":" +
                     str(self.registryPort) + " -> " + message)
        self.tcpClientSocket.send(message.encode())
        response = self.tcpClientSocket.recv(1024).decode()
        cmsg.green_message(str(response))
        logging.info("Received from " + self.registryName + " -> " + response)

    def createRoom(self, roomId):
        message = "CREATE-ROOM " + roomId
        logging.info("Send to " + self.registryName + ":" +
                     str(self.registryPort) + " -> " + message)
        self.tcpClientSocket.send(message.encode())
        response = self.tcpClientSocket.recv(1024).decode()
        logging.info("Received from " + self.registryName + " -> " + response)
        if response == "create-room-success":
            cmsg.green_message("Chat room created successfully")
        elif response == "chat-room-exist":
            cmsg.red_message("Chat room already exits")
        return response

    def joinRoom(self, roomId):
        message = "JOIN-ROOM " + roomId + " " + str(self.peerServerPort)
        logging.info("Send to " + self.registryName + ":" +
                     str(self.registryPort) + " -> " + message)
        self.tcpClientSocket.send(message.encode())
        response = self.tcpClientSocket.recv(1024).decode()
        logging.info("Received from " + self.registryName + " -> " + response)
        if response == "join-room-success":
            cmsg.green_message(roomId + " is joined successfully")
            if roomId in self.peerServer.rooms_messages:
                cmsg.blue_message(f"You have {len(self.peerServer.rooms_messages[roomId])} unread messages")
                for message in self.peerServer.rooms_messages[roomId]:
                    print(message)
                self.peerServer.rooms_messages.pop(roomId)
            self.peerServer.isChatRequested = 1
        elif response == "room-not-exist":
            cmsg.red_message("Chat room doesn't exist")
        return response

    def roomExist(self, roomId):
        message = "ROOM-EXIST " + roomId
        logging.info("Send to " + self.registryName + ":" +
                     str(self.registryPort) + " -> " + message)
        self.tcpClientSocket.send(message.encode())
        response = self.tcpClientSocket.recv(1024).decode()
        return response == "room-exist"

    def getRooms(self):
        message = "GET-ROOMS"
        logging.info("Send to " + self.registryName + ":" +
                     str(self.registryPort) + " -> " + message)
        self.tcpClientSocket.send(message.encode())
        response = self.tcpClientSocket.recv(1024).decode()
        logging.info("Received from " + self.registryName +
                     " -> " + response)
        if response == "no-rooms":
            return []
        else:
            return response.split(",")

    @staticmethod
    def format_message(message):
        def emphasize_text(match):
            return f'\033[1m{match.group(1)}\033[0m'

        def italicize_text(match):
            return f'\033[3m{match.group(1)}\033[0m'

        # Emphasize text (bold)
        message = re.sub(r'\*([^*]+)\*', emphasize_text, message)

        # Italicize text
        message = re.sub(r'_([^_]+)_', italicize_text, message)

        return message


# peer is started
main = peerMain()
