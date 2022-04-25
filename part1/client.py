import socket
import select
import sys
from _thread import *
import argparse

'''
@Author: Jike Zhong, xxx
CSE 3461 Final Project
'''
  
def arg_parse():
    parser = argparse.ArgumentParser(description='Multi-threaded Web Server')
    parser.add_argument('--port', default = 6789, type=int, required = True)
    return parser.parse_args()

def create_client_socket(port):
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client_socket.connect(('127.0.0.1', port))
    print("Connected successfully!")
    return client_socket

if __name__ == '__main__':
    args = arg_parse()

    #establish connection
    client = create_client_socket(args.port) 

    while True:

        #two types: 1 > print server result  2 > send to server  
        sockets_list = [sys.stdin, client]
        read_sockets,write_socket, error_socket = select.select(sockets_list,[],[])
        for socket in read_sockets:
            if socket == client:
                print(socket.recv(2048).decode()) 
            else:
                post_msg = sys.stdin.readline()
                client.send(post_msg.encode())
        

    

    
