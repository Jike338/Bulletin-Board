import socket
import select
import sys
import threading
import argparse
from datetime import date

'''
@Author: Jike Zhong, xxx
CSE 3461 Final Project
'''

class Message():
    def __init__(self, id, sender, subject, content):
        self.id = id
        self.sender = sender
        self.date = date.today()
        self.subject = subject
        self.content = content

class Group():
    def __init__(self, id, name):
        self.id = id
        self.name = name
        self.members = []
        self.msgs = []

    def add_member(self, user_name):
        self.members.append(user_name)

    def remove_member(self, user_name):
        self.members.remove(user_name)
    
    def add_msg(self, msg):
        self.msgs.append(msg)

class ClientThread(threading.Thread):
    def __init__(self, conn, ip):
        threading.Thread.__init__(self)
        self.addr = ip
        self.conn = conn
        self.user_name = None
        self.curr_group = None
        print ("New connection added: ", self.addr)

    #sets the user name, check for invalid response
    def set_user_name(self):
        existing_names =  [c.user_name for c in client_threads if c.user_name is not None]
        self.conn.send("\nPlease pick a user name: \n".encode()) 
        action = self.conn.recv(2048).decode().strip()
        while action in existing_names:
            self.conn.send("\nUser name already exists, pick a new name: \n".encode()) 
            action = self.conn.recv(2048).decode().strip()
        self.user_name = action
        self.conn.send("\n[System Message] Success! Welcom to the chat board {}!\n".format(self.user_name).encode())

    #broadcast @msg to all users (except self) in the current group
    def broadcast(self, msg, including_self=False):
        for client in [m for m in client_threads if m.user_name in self.curr_group.members]:
            if not including_self:
                if self.user_name != client.user_name:
                    client.conn.send(msg.encode())
            else:
                client.conn.send(msg.encode())

    #displays the latest two messages from previous users
    def display_latest_two(self):
        self.conn.send("\n[System Message] Displaying latest two messages in group {}:\n".format(self.curr_group.name).encode())
        msg_1 = self.curr_group.msgs[-2]
        msg_2 = self.curr_group.msgs[-1]
        self.conn.send("\n[User Message] - Message ID: {}, Sender: {}, Date: {}, Subject: {}".format(msg_1.id, msg_1.sender, msg_1.date, msg_1.subject).encode())
        self.conn.send("\n[User Message] - Message ID: {}, Sender: {}, Date: {}, Subject: {}\n".format(msg_2.id, msg_2.sender, msg_2.date, msg_2.subject).encode())
    
    #checks if the user has joined a group
    #we only allow them to use certain commands (ex. %grouppost) provided they have joined a group
    def ok_to_post(self):
        if self.curr_group is None:
            self.conn.send("\n\n\n[System Message] >>>Warning: You must join a group before using this command!<<<\n\n\n".encode())
            return False
        else:
            return True

    #shows the user list of this group
    def users(self, action):
        if not self.ok_to_post(): return 
        self.conn.send("\n[System Message] Displaying group members:\n".encode())
        for i, name in enumerate(self.curr_group.members):
            self.conn.send("{}: {}\n".format(i+1, name).encode())
    
    #retrieve the message content, provided the message id
    def message(self, action):
        if not self.ok_to_post(): return 
        msg_id = action.split(" ")[1]
        msg = [m for m in self.curr_group.msgs if m.id == int(msg_id)][0]
        self.conn.send("\n[System Message] Displaying message sent by {} on {}:\n".format(msg.sender, msg.date).encode())
        self.conn.send("{}".format(msg.content).encode())
    
    #post to the group's discussion board
    def post(self, action):
        if not self.ok_to_post(): return 
        msg = action.split(" ")
        msg_id = max([m.id for m in self.curr_group.msgs])+1
        msg_sender = self.user_name
        msg_subject = msg[1]
        msg_content = msg[2]
        new_msg = Message(msg_id, msg_sender, msg_subject, msg_content)
        self.curr_group.add_msg(new_msg)
        self.broadcast("\n[User Message] - Message ID: {}, Sender: {}, Date: {}, Subject: {}\n".format(new_msg.id, new_msg.sender, new_msg.date, new_msg.subject))
        self.conn.send("\n[You] - Message ID: {}, Sender: {}, Date: {}, Subject: {}\n".format(new_msg.id, new_msg.sender, new_msg.date, new_msg.subject).encode())

    #exit a group
    def leave(self, action):
        if not self.ok_to_post(): return 
        self.curr_group.remove_member(self.user_name)
        self.broadcast("\n[System Message] User {} just left the group!\n".format(self.user_name))
        self.curr_group = None
        self.conn.send("\n[System Message] You just left the group!\n".encode())

    #join a group, provided the group id
    def join(self, action):
        self.curr_group = group
        self.curr_group.add_member(self.user_name)
        self.broadcast("\n[System Message] User {} just joined the group!\n".format(self.user_name))
        self.conn.send("\n[System Message] You just joined the group {}!\n".format(group.name).encode())
        self.broadcast("\nCurrent group members are: \n", True)
        for i, name in enumerate(self.curr_group.members):
            self.broadcast("{}: {}\n".format(i+1, name), True)
        self.display_latest_two()

    #sends a list of available commands to the user
    #we want them to know what to expect
    def send_commands(self):
        self.conn.send("\n[System Message] The following commands are for you to use!".encode())
        self.conn.send("\n[System Message] %join             : Join the discussion board".encode())
        self.conn.send("\n[System Message] %help             : Display commands again".encode())  
        self.conn.send("\n[System Message] %quit             : Quit the chat room".encode())
        self.conn.send("\n[System Message] The following commands can be used only if you have already joined the discussion board, see %groupjoin!".encode())
        self.conn.send("\n[System Message] %users            : View users in this discussion board".encode())
        self.conn.send("\n[System Message] %message <id>     : View the content of a message".encode())
        self.conn.send("\n[System Message] %leave            : Leave the discussion board".encode())
        self.conn.send("\n[System Message] %post <subject> <content>: Post to the discussion board\n".encode())

    #main thread
    def run(self):
        
        self.set_user_name()
        self.send_commands()

        while True: 
            action = self.conn.recv(2048).decode().strip()

            #execute function according to user input
            if "%join" in action: 
                self.join(action)
            elif "%users" in action:
                self.users(action)
            elif "%message" in action:
                self.message(action)
            elif "%post" in action:
                self.post(action)
            elif "leave" in action:
                self.leave(action)
            elif "%help" in action:
                self.send_commands()
            elif "%quit" in action:
                break
            else:
                self.conn.send("\n[System Message] Invalid command, please enter again. Use %help to display all commands if you need\n".encode())
        
        self.conn.send("\nGoodbye, it was nice seeing you!".encode())
        self.conn.close()

def arg_parse():
    parser = argparse.ArgumentParser(description='Multi-threaded Web Server')
    parser.add_argument('--port', default = 6789, type=int, required = True)
    return parser.parse_args()

def create_server_socket(port):
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind(('127.0.0.1',port))
    print("Server created successfully!")
    return server_socket
 
if __name__ == '__main__':
    args =  arg_parse() 
    server = create_server_socket(args.port)
    global client_threads, group
    client_threads = []
    group = Group(1,"A")

    #make dummy messages
    msg_1 = Message(0, "Ben", "good networking news", "Today, google annouced that...")
    msg_2 = Message(1, "Jack", "bad networking news", "Today, we are sorry to learn that...")
    group.add_msg(msg_1)
    group.add_msg(msg_2)

    while True:
        server.listen(1)
        conn, ip = server.accept()
        new_thread = ClientThread(conn, ip)
        new_thread.start()
        client_threads.append(new_thread)

