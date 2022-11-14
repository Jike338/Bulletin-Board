import socket
import select
import sys
import threading
import argparse
from datetime import date

'''
@Author: Jike Zhong
'''

#We utilize OOP design concept to make Message, Group and Thread instances
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
        self.group_joined = []
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
    def broadcast(self, msg, including_self=False, group=None):
        group_to_send = group if group is not None else self.curr_group
        for client in [m for m in client_threads if (m.user_name in group_to_send.members and m.curr_group.id == group_to_send.id)]:
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
    #self_ means the user's current group needs to be the group with @group_id
    def ok_to_post(self, group_id, self_=False):
        joined_groups = [g.id for g in self.group_joined]
        if int(group_id) not in joined_groups:
            self.conn.send("\n\n\n[System Message] >>>Warning: You are not in group {}!<<<\n\n\n".format(group_id).encode())
            return False
        else:
            if self_ is True and self.curr_group is not None:
                if self.curr_group.id != int(group_id): 
                    self.conn.send("\n\n\n[System Message] >>>Warning: You cannot view the info of other groups!<<<\n\n\n".encode())
                    return False
            return True

    #shows the user list of this group
    def group_users(self, action):
        group_id = action.split(" ")[1]
        if not self.ok_to_post(group_id, True): return 
        group = [g for g in groups if g.id == int(group_id)][0]
        self.conn.send("\n[System Message] Displaying group members:\n".encode())
        for i, name in enumerate(group.members):
            self.conn.send("{}: {}\n".format(i+1, name).encode())
    
    #retrieve the message content, provided the message id
    def group_message(self, action):
        group_id = action.split(" ")[1]
        if not self.ok_to_post(group_id, True): return 
        group = [g for g in groups if g.id == int(group_id)][0]
        msg_id = action.split(" ")[2]
        msg = [m for m in group.msgs if m.id == int(msg_id)][0]
        self.conn.send("\n[System Message] Displaying message sent by {} on {}:\n".format(msg.sender, msg.date).encode())
        self.conn.send("{}".format(msg.content).encode())
    
    #post to the group's discussion board
    def group_post(self, action):
        group_id = action.split(" ")[1]
        if not self.ok_to_post(group_id): return 
        group = [g for g in groups if g.id == int(group_id)][0]

        msg = action.split(" ")
        msg_id = max([m.id for m in group.msgs])+1
        msg_sender = self.user_name
        msg_subject = msg[2]
        msg_content = msg[3]
        new_msg = Message(msg_id, msg_sender, msg_subject, msg_content)

        group.add_msg(new_msg)
        self.broadcast("\n[User Message] - Message ID: {}, Sender: {}, Date: {}, Subject: {}\n".format(new_msg.id, new_msg.sender, new_msg.date, new_msg.subject), group = group)
        self.conn.send("\n[You] to Group {} - Message ID: {}, Sender: {}, Date: {}, Subject: {}\n".format(group.name, new_msg.id, new_msg.sender, new_msg.date, new_msg.subject).encode())

    #exit a group
    def group_leave(self, action):
        group_id = action.split(" ")[1]
        if not self.ok_to_post(group_id): return 
        group = [g for g in groups if g.id == int(group_id)][0]
        group.remove_member(self.user_name)
        self.broadcast("\n[System Message] User {} just left group {}!\n".format(self.user_name, group.name), group=group)
        self.group_joined.remove(group)
        self.conn.send("\n[System Message] You just left group {}!\n".format(group.name).encode())
        self.curr_group = None

    #view available groups
    def view_groups(self, groups_=None):
        group_names = [g.name for g in groups_]
        group_ids = [g.id for g in groups_]
        self.conn.send("\n[System Message] Displaying groups: \n".encode())
        for name, id in zip(group_names, group_ids):
            self.conn.send("Group id:{} name:{}\n".format(id, name).encode())

    #join a group, provided the group id
    def group_join(self, action):
        group_id = action.split(" ")[1]
        group = [g for g in groups if g.id == int(group_id)][0]
        if self.user_name not in group.members:
            group.add_member(self.user_name)
            self.group_joined.append(group)

        self.curr_group = group
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
        self.conn.send("\n%groups                                  : View available groups".encode())
        self.conn.send("\n%mygroups                                : View the groups you have joined".encode())
        self.conn.send("\n%groupjoin <group_id>                    : Join a group".encode())
        self.conn.send("\n%help                                    : Display commands again".encode())  
        self.conn.send("\n%quit                                    : Quit the chat room".encode())
        self.conn.send("\n[System Message] The following commands can be used only if you have already joined the specific group, see %groupjoin!".encode())
        self.conn.send("\n%groupusers <group_id>                   : View users in this group".encode())
        self.conn.send("\n%groupmessage <group_id> <message_id>    : View the content of a message".encode())
        self.conn.send("\n%groupleave <group_id>                   : Leave the group".encode())
        self.conn.send("\n%grouppost <group_id> <subject> <content>: Post to the group\n".encode())

    #shows all groups that the user has joined
    def show_curr_groups(self):
        self.conn.send("\n[System Message] Displaying your groups: \n".encode())
        if len(self.group_joined) == 0:
            self.conn.send("\n[System Message] You have joined no group, use %groups to view available groups\n".encode())
        else:
            joined_groups = [g for g in self.group_joined]
            self.view_groups(joined_groups)

    #main thread
    def run(self):
        self.set_user_name()
        self.send_commands()

        while True: 
            action = self.conn.recv(2048).decode().strip()
            try:
                #execute function according to user input
                if "%groups" in action:
                    self.view_groups(groups)
                elif "%groupjoin" in action: 
                    self.group_join(action)
                elif "%groupusers" in action:
                    self.group_users(action)
                elif "%groupmessage" in action:
                    self.group_message(action)
                elif "%grouppost" in action:
                    self.group_post(action)
                elif "%groupleave" in action:
                    self.group_leave(action)
                elif "%help" in action:
                    self.send_commands()
                elif "%mygroups" in action:
                    self.show_curr_groups()
                elif "%quit" in action:
                    self.conn.send("\nGoodbye, it was nice seeing you!".encode())
                    break
                else:
                    self.conn.send("\n[System Message] Invalid command, please enter again. Use %help to display all commands if you need\n".encode())
            except:
                self.conn.send("\n[System Message] Invalid command, please enter again. Use %help to display all commands if you need\n".encode())
                continue
        print ("Client at {} disconnected...".format(self.addr))
        
       

def make_group():
    return [Group(idx, name) for idx, name in enumerate(['A','B','C','D','E'])]

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

    #storing all running threads, as well as groups
    global client_threads, groups
    client_threads = []
    
    #make 5 inital group
    groups = make_group()

    #make dummy messages
    for i, group in enumerate(groups):
        msg_1 = Message(i, "Ben", "good networking news", "Today, google annouced that...")
        msg_2 = Message(i+1, "Jack", "bad networking news", "Today, we are sorry to learn that...")
        group.add_msg(msg_1)
        group.add_msg(msg_2)

    while True:
        server.listen(1)
        conn, ip = server.accept()
        new_thread = ClientThread(conn, ip)
        new_thread.start()
        client_threads.append(new_thread)
    
