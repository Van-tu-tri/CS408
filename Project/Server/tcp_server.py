import tkinter as tk
from tkinter import filedialog, Listbox, END, NORMAL, DISABLED


import socket, threading, select
import os
import json


# Define global variables
clients = {}    # Current clients with their corresponding sockets
file_list = {}  # If folder is currently uploading set its value to zero, also used for storing the data inside.
server_running = False
base_directory = None
dummy_file_directory = None
server_socket = None    
host = "0.0.0.0"   #This should be change when it is used in different network.
port = None
lock = threading.Lock()  #Lock for thread-safe access to `clients`
lock_for_file = threading.Lock() # Lock for operations on file
lock_for_send = threading.Lock() # Lock for sending chunk

# Define Functions

def select_base_directory():
    global base_directory

    # To open filedialog for browsing
    directory = filedialog.askdirectory(title="Select Base Directory")

    if directory:
        # Set the base directory
        base_directory = directory
        log_listbox.insert(END, f"Base directory set to: {base_directory}")
    else:
        log_listbox.insert(END, "No directory selected.")


# To ensure a block is always same byte, but i could not implement it due to time constraints.
def create_dummy_file():
    if os.path.exists("dummy_file"):
        os.remove("dummy_file")
    with open("dummy_file", 'ab') as file:
        for i in range(0, 100):
            file.write(b"dummy_dummy_dummy_dummy_dummy_")


# Start server as a thread
def start_server():
    global port
    global server_socket
    global host
    global server_running
    global file_list


    create_dummy_file()

    # Take the list of current base_directory
    files = os.listdir(base_directory)
    for i in files:
        file_list[i] = 1


    # Error check for port and base directory
    port_get = port_entry.get()
    if not port_get.isdigit():
        log_listbox.insert(END, "Error: Port number must be an integer.")
        return
    elif int(port_get) < 0 or int(port_get) > 65535:
        log_listbox.insert(END, "Error: Port number must be 0-65535.")
        return
    if not base_directory:
        log_listbox.insert(END, "Error: Base directory not selected.")
        return

    # Convert port to int to bind
    port = int(port_get)

    log_listbox.insert(END, f"Starting server on port {port}...")
    log_listbox.insert(END, f"Serving files from: {base_directory}")
    # Here you can add server start logic, e.g., socket setup, threading, etc.

    
    # Create the socket with corresponding protocols.
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # Try to bind host ip and port
    try:
        server_socket.bind((host, port))
    except Exception as e:
        log_listbox.insert(END, f"Error occured while binding: {str(e)}")
        return
    
    server_socket.listen(5)

    # For debug purposes
    print(f"Server listening on {host}:{port}")

    server_running = True

    # Start threads
    accept_thread = threading.Thread(target=accept_connections, args=(server_socket,), daemon=True)
    listen_thread = threading.Thread(target=listen_for_messages, daemon=True)

    accept_thread.start()
    listen_thread.start()

    while server_running:  # Keep the main thread alive
        continue

    # Close all connections and the server socket
    for client_socket in list(clients.values()):
        client_socket.close()
    server_socket.close()
    log_listbox.insert(END, "Server Shut Down")


def start_server_threaded():
    # With button, start the thread
    start_button.config(state=DISABLED)
    shutdown_button.config(state=NORMAL)
    threading.Thread(target=start_server, daemon=True).start()


def shutdown_server():
    global server_running
    start_button.config(state=NORMAL)
    shutdown_button.config(state=DISABLED)
    server_running = False


# A thread for accepting connections concurrently
def accept_connections(server_socket):
    global clients
    global server_running
    global lock_for_send
    while server_running:
        try:
            
            #Accepting the connection for checking.
            client_socket, client_address = server_socket.accept()
            log_listbox.insert(END, f"Connection request send by: {client_address}")

            # Authentication 
            client_name = client_socket.recv(1024).decode('utf-8')

            if client_name in clients.keys():
                log_listbox.insert(END, f"There is already a user with this name. Disconnecting: {client_name}")
                # Use lock for send to send chunk of data.
                with lock_for_send:
                    client_socket.sendall("INVALID:There is already a user with this name. Disconnecting.".encode('utf-8'))
                client_socket.close()
                continue
            else:
                # Add to the clients if authentication succeed
                with lock:
                    clients[client_name] = client_socket
                with lock_for_send:
                    client_socket.sendall(f"Welcome to the server, {client_name}!".encode('utf-8'))
                log_listbox.insert(END, f"Successful entry: {client_name}")
            
        except Exception as e:
            log_listbox.insert(END, f"Error occured while accepting connections: {str(e)}")

# A thread for listening
def listen_for_messages():
    # Global variables
    global clients
    global server_running
    global file_list
    global lock_for_send

    while server_running:
        try:
            # Create a list of sockets to poll for readability
            with lock:
                sockets = list(clients.values())  # Extract sockets from clients dictionary

            if not sockets:
                continue  # If no sockets, skip to the next iteration

            # Use select to check which sockets are ready for reading
            readable, _, _ = select.select(sockets, [], [], 0.1)  # 0.1-second timeout

            for client_socket in readable:  # Loop only through sockets with available data
                try:
                    # Receive data from the ready socket
                    message = client_socket.recv(1024).decode('utf-8')

                    # If no data is received, the client has disconnected
                    if not message:
                        raise ConnectionResetError

                    # Find the client name from the socket
                    client_name = next((name for name, sock in clients.items() if sock == client_socket), None)

                    if client_name:
                        
                        # Extract the header
                        header = message.split(":")[0]

                        if header == "DOWNLOAD_REQUEST":
                            log_listbox.insert(END, f"Header from {client_name}: {header}")
                            # Start the file sending thread
                            # Expected format: DOWNLOAD_REQUEST:filename
                            _, _, file_name = message.partition(":")

                            full_path = base_directory + "\\" + file_name

                            # If file is available start a thread for sending the requested file, else send notification.
                            with lock_for_file:
                                if file_name in file_list:
                                    if (file_list[file_name]):
                                        log_listbox.insert(END, f"File is available, thread has been started to send file to {client_name}")
                                        owner = file_name.split("_")[-1].split(".")[0]

                                        send_file_thread = threading.Thread(target=send_file, args=(client_socket, full_path, client_name), daemon=True)
                                        send_file_thread.start()

                                        with lock:
                                            if owner in clients:
                                                try:
                                                    owner_socket = clients[owner]
                                                    if client_socket != owner_socket:
                                                        with lock_for_send:  
                                                            owner_socket.sendall(f"NOTIFICATION: Your file '{file_name}' is being downloaded by {client_name}.".encode('utf-8'))
                                                    log_listbox.insert(END, f"Notification sent to owner: {owner}")
                                                except Exception as e:
                                                    log_listbox.insert(END, f"Failed to send notification to owner {owner}: {str(e)}")
                                    else:
                                        log_listbox.insert(END, f"File is currently not available")
                                else:
                                    log_listbox.insert(END, f"The file may deleted.")
                                    with lock_for_send:
                                        client_socket.sendall("NOTIFICATION: Download request could not succeed: File may deleted.".encode('utf-8'))
                            
                           
                        elif header == "FILE_LIST_REQUEST":
                            log_listbox.insert(END, f"Header from {client_name}: {header}")
                            # Excepted format: FILE_LIST_REQUEST:

                            # A thread to send the os.listdir to the client
                            send_file_list_thread = threading.Thread(target=send_file_list, args=(client_socket,), daemon=True)
                            send_file_list_thread.start()

                        elif header == "FILE_TRANSFER_INITIAL":
                            log_listbox.insert(END, f"Header from {client_name}: {header}")
                            # Initial server upload request.
                            # Expected format: FILE_TRANSFER_INITIAL:filename:filesize
                            
                            _, filename, filesize = message.split(":")
                             # In here, file name is filename.txt
                            filename = filename[:len(filename) - 4] 

                            # Now filename is only filename
                            filename = filename + "_" + client_name + ".txt"

                            filesize = int(filesize)

                            # For debug purposes, print the name of the file
                            print(filename)

                            # Check if file exists in file_list and delete the old file if necessary
                            # Concurrent access, need lock in here.
                            with lock_for_file:
                                if filename in file_list:
                                    file_path = base_directory + "\\" + filename
                                    if os.path.exists(file_path):
                                        os.remove(file_path)
                                        log_listbox.insert(END, f"Old file {filename} deleted.")
                                        # Send a notification to the client
                                        with lock_for_send:
                                            client_socket.sendall(f"NOTIFICATION:Old file {filename} is deleted.".encode('utf-8'))
                                
                                # Set the file status to 0 (not available for download)
                                file_list[filename] = 0

                            with lock_for_send:
                                # Send confirmation to the client
                                client_socket.sendall(f"UPLOAD_CONFIRMATION:".encode('utf-8'))

                        elif header == "FILE_TRANSFER_CONTINUE":
                            # Expected format: FILE_TRANSFER_CONTINUE:filename:data or FILE_TRANSFER_CONTINUE:filename:data:FILE_TRANSFER_END
                    
                            if message.endswith("FILE_TRANSFER_END"):
                                actual_data, _, trailer = message.rpartition(":FILE_TRANSFER_END")

                                _, filename, data = actual_data.split(":", 2)
                                # In here, file name is filename.txt
                                filename = filename[:len(filename) - 4] 

                                # Now filename is only filename
                                filename = filename + "_" + client_name + ".txt"
                                print(filename)

                                # Append data to the file
                                file_path = base_directory + "\\" + filename
                                with open(file_path, 'ab') as file:
                                    file.write(data.encode('utf-8'))
                                
                                with lock_for_file:
                                    # Set the file status to 1 (available for download)
                                    file_list[filename] = 1

                                with lock_for_send:
                                    # Send a notification to the client
                                    client_socket.sendall(f"NOTIFICATION: File {filename} has been uploaded successfully.\n".encode('utf-8'))

                                log_listbox.insert(END, f"File {filename} is now available for download.")

                            else:
                                actual_data, _, trailer = message.rpartition(":FILE_TRANSFER_NOT")
                                _, filename, data = actual_data.split(":", 2)

                                 # In here, file name is filename.txt
                                filename = filename[:len(filename) - 4] 

                                # Now filename is only filename
                                filename = filename + "_" + client_name + ".txt"
                                # Append data to the file
                                file_path = base_directory + "\\" + filename
                                with open(file_path, 'ab') as file:
                                    file.write(data.encode('utf-8'))
                        
                        elif header == "DELETE_REQUEST":
                            log_listbox.insert(END, f"Header from {client_name}: {header}")
                            # Parse the message to extract filename
                            # Excepted format is DELETE_REQUEST:filename

                            _, _, file_name = message.partition(":")
                            owner = file_name.split("_")[-1].split(".")[0]

                            # Adding to the directory
                            full_path = base_directory + "\\" + file_name
                            
                            with lock_for_file:
                                if os.path.exists(full_path):
                                    if owner == client_name:
                                        os.remove(full_path)  # Delete the file
                                        log_listbox.insert(END, f"{client_name} deleted {file_name}")
                                        with lock_for_send:
                                            client_socket.sendall("The file is deleted".encode('utf-8'))
                                        del file_list[file_name]
                                    else:
                                        log_listbox.insert(END, f"{client_name} is not owner of this file: {file_name}")
                                        with lock_for_send:
                                            client_socket.sendall("You are not the owner, delete is not permitted".encode('utf-8'))
                                else:
                                    log_listbox.insert(END, f"The file does not exists")
                                    with lock_for_send:
                                        client_socket.sendall("The file does not exists in the server database".encode('utf-8'))
                        
                                

                except (ConnectionResetError, OSError):
                    # Handle client disconnection
                    with lock:
                        client_name = next((name for name, sock in clients.items() if sock == client_socket), None)
                        if client_name:
                            client_socket.close()
                            del clients[client_name]
                        log_listbox.insert(END, f"{client_name} is disconnected")

                except Exception as e:
                    log_listbox.insert(END, f"Unexpected error with a client socket: {e}")

        except Exception as e:
            log_listbox.insert(END, f"Error in listen_for_messages loop: {e}")



# The main transfer implementation has changed, i need to look this again.

def send_file(client_socket, file_path, client_name):
    global lock_for_send
    try:

        with open(file_path, 'rb') as file:
            file_size = file.seek(0, 2)  # Get file size
            file.seek(0)  # Reset to beginning

            filename = os.path.basename(file_path)

            log_listbox.insert(END, f"Sending file: {filename} ({file_size} bytes)")

            bytes_sent = 0  # Track the number of bytes sent
            initial = 0
            while bytes_sent < file_size:
                
                max_chunk_size = 1024 - len(f"FILE_TRANSFER_CONTINUE1:{filename}:".encode('utf-8')) - len(":FILE_TRANSFER_END".encode('utf-8'))
                chunk = file.read(max_chunk_size)
                bytes_sent += len(chunk)

                # Add trailer to the last chunk
                if bytes_sent == file_size:  # This is the last chunk
                    chunk = f"FILE_TRANSFER_CONTINUE1:{filename}:".encode('utf-8') + chunk + b":FILE_TRANSFER_END"
                else:
                    # If this is the first byte, the client should check wheter the file is already inside the directory, if so he/she should delete it.
                    if initial == 0:
                        chunk = f"FILE_TRANSFER_CONTINUE0:{filename}:".encode('utf-8') + chunk + b":FILE_TRANSFER_NOT"
                        initial = 1
                    else:
                        chunk = f"FILE_TRANSFER_CONTINUE1:{filename}:".encode('utf-8') + chunk + b":FILE_TRANSFER_NOT"

                with lock_for_send:
                    client_socket.sendall(chunk)
                    print(chunk)
                    

            log_listbox.insert(END, f"File {filename} sent successfully to {client_name}")

    except Exception as e:
        log_listbox.insert(END, f"Error while sending file: {str(e)}")


# Not used in this project (probably)
def send_message(client_socket, message, client_name):
    global dummy_file_directory
    try:
        client_socket.sendall(f"{message}".encode('utf-8'))
        log_listbox.insert(END, f"The message has been sent succesfully to: {client_name}")

    except Exception as e:
        log_listbox.insert(END, f"Error while sending message: {str(e)}")


# To send current file list.
def send_file_list(client_socket):
    global lock_for_send
    files = sorted(os.listdir(base_directory))
    data = {
        "files": files
    }
    encapsulated_data = "FILE_LIST_RESPONSE:" + json.dumps(data)

    with lock_for_send:
        client_socket.sendall(encapsulated_data.encode('utf-8'))
    log_listbox.insert(END, f"File list has been sent.")



# Define GUI
root = tk.Tk()
root.title("Server GUI")
root.geometry("600x400")
root.resizable(0, 0)

# Configure rows and columns
root.grid_rowconfigure(2, weight=1)  # Make the listbox expandable
root.grid_columnconfigure(0, weight=1)

# Top Frame for port and directory selection (and others)
top_frame = tk.Frame(root, pady=10)
top_frame.grid(row=0, column=0, sticky="ew")

tk.Label(top_frame, text="Port:").grid(row=0, column=0, padx=5, sticky="w")
port_entry = tk.Entry(top_frame, width=10)
port_entry.grid(row=0, column=1, padx=5)

select_dir_button = tk.Button(top_frame, text="Select Base Directory", command=select_base_directory)
select_dir_button.grid(row=0, column=2, padx=5)

start_button = tk.Button(top_frame, text="Start Server", command=start_server_threaded)
start_button.grid(row=0, column=3, padx=5)

shutdown_button = tk.Button(top_frame, text="Shut Down", command=shutdown_server, state=DISABLED)
shutdown_button.grid(row=0, column=4, padx=5)

# Listbox for logging server activity
log_listbox = Listbox(root, width=80, height=20)
log_listbox.grid(row=2, column=0, sticky="nsew", padx=10, pady=10)

# Add scrollbar for the listbox
scrollbar = tk.Scrollbar(log_listbox, orient="vertical", command=log_listbox.yview)
scrollbar.pack(side="right", fill="y")
log_listbox.config(yscrollcommand=scrollbar.set)

# Run the GUI
root.mainloop()