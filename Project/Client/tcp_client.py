#Client Side GUI Chat room

import tkinter, socket, threading
from tkinter import DISABLED, NORMAL, END, filedialog
import json
import os


#Define Global Variables
client_socket = None
upload_file_path = None
base_directory = "" # Default base_directory. User does not have to choose a directory for download.

#Define Functions
def connect_to_server():
    global client_socket
    try:
        # Get the server details from the entries
        host_ip = ip_entry.get()
        port_get = port_entry.get()
        client_name = name_entry.get()

        # Error check
        if not port_get.isdigit():
            top_listbox.insert(END, "Error: Port number must be an integer.")
            return
        elif int(port_get) < 0 or int(port_get) > 65535:
            top_listbox.insert(END, "Error: Port number must be 0-65535.")
            return

        port_num = int(port_get)
        
        # Create and connect the socket
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_socket.connect((host_ip, port_num))


        # For aouthentication purposes
        client_socket.sendall(client_name.encode('utf-8'))

        # Update button states
        connect_button.config(state=DISABLED)
        upload_button.config(state=NORMAL)
        download_button.config(state=NORMAL)
        request_button.config(state=NORMAL)
        delete_button.config(state=NORMAL)

        # Wait for a response
        response = client_socket.recv(1024).decode('utf-8')

        # Connection lost
        if not response:
            # Update Button States
            connect_button.config(state=NORMAL)
            upload_button.config(state=DISABLED)
            download_button.config(state=DISABLED)
            request_button.config(state=DISABLED)
            delete_button.config(state=DISABLED)
            top_listbox.insert(END, "Disconnected from server.")
        else:
            validation = response.split(":")[0]
            if validation == "INVALID":
                # Update Button States
                connect_button.config(state=NORMAL)
                upload_button.config(state=DISABLED)
                download_button.config(state=DISABLED)
                request_button.config(state=DISABLED)
                delete_button.config(state=DISABLED)
                top_listbox.insert(END, f"{response}")
                top_listbox.insert(END, "Disconnected from server.")
            else:
                top_listbox.insert('end', f"{response}")
                threading.Thread(target=listen_for_messages, daemon=True).start()

    except Exception as e:
        top_listbox.insert(END, f"Error while connecting to the server: {str(e)}")


def disconnect_from_server():
    global client_socket
    try:
        # If client_socket is not closed
        if client_socket:
            client_socket.close()
            client_socket = None

            # Update Button States
            connect_button.config(state=NORMAL)
            upload_button.config(state=DISABLED)
            download_button.config(state=DISABLED)
            request_button.config(state=DISABLED)
            delete_button.config(state=DISABLED)

            top_listbox.insert(END, "Disconnected from server.")
        else:
            top_listbox.insert(END, "You already disconnected from server.")
    except Exception as e:
        top_listbox.insert(END, f"Error: {str(e)}")




def listen_for_messages():
    global client_socket
    global upload_file_path
    try:
        while True:

            # Actually there is not just a header, inside there is a message (usually) 
            # Check the details of server module.
            header = client_socket.recv(1024).decode('utf-8')

            # If server is closed or something like that
            if not header:
                # Update Button States
                connect_button.config(state=NORMAL)
                upload_button.config(state=DISABLED)
                download_button.config(state=DISABLED)
                request_button.config(state=DISABLED)
                delete_button.config(state=DISABLED)
                client_socket.close()
                client_socket = None
                top_listbox.insert(END, "Disconnected from server.")
                break


            # Receiving file
            if header.startswith("FILE_TRANSFER_CONTINUE"):
                
                # If receiving file chunk is the last one.
                if header.endswith("FILE_TRANSFER_END"):
                    actual_data, _, trailer = header.rpartition(":FILE_TRANSFER_END")

                    _, filename, data = actual_data.split(":", 2)
                    # In here, file name is filename.txt

                    full_path = ""
                    if base_directory == "":
                        full_path = filename + ".txt"
                    else:
                        full_path = base_directory + "\\" + filename + ".txt"
                    
                    # The open mode is ADD-byte
                    # The data does not have to come in once. So append is needed.
                    with open(full_path, 'ab') as file:
                        file.write(data.encode('utf-8'))

                    top_listbox.insert(END, f"File {filename} is now available.")

                else:
                    actual_data, _, trailer = header.rpartition(":FILE_TRANSFER_NOT")
                    _, filename, data = actual_data.split(":", 2)
                    # In here, file name is filename.txt
                    

                    full_path = ""
                    if base_directory == "":
                        full_path = filename + ".txt"
                    else:
                        full_path = base_directory + "\\" + filename + ".txt"

                    # If the chunk is the first chunk, delete the old file if it is there.
                    if header.startswith("FILE_TRANSFER_CONTINUE0"):
                        if os.path.exists(full_path):
                            os.remove(full_path)
                            top_listbox.insert(END, f"Old file {filename} deleted.")

                    # Append data to the file
                    with open(full_path, 'ab') as file:
                        file.write(data.encode('utf-8'))
                
            
            elif header.startswith("FILE_LIST_RESPONSE"):
                # Generate a dictionary with JSON file. Than insert it to the listbox.
                _, _, encapsulated_data = header.partition(":")
                data = json.loads(encapsulated_data)
                file_list = data["files"]

                bottom_listbox.delete(0, END)
                for file in file_list: 
                    bottom_listbox.insert(END, f"{file}")

            elif header.startswith("NOTIFICATION"):
                # Any nofitication from the server is listed inside the top_listbox
                top_listbox.insert('end', f"{header}")

            elif header.startswith("UPLOAD_CONFIRMATION"):
                # Before sending the file, a confirmation should come.
                upload_file(upload_file_path)

            else:
                top_listbox.insert('end', f"Server: {header}")

    except Exception as e:
        top_listbox.insert(END, f"Error while listening for messages: {str(e)}")
        disconnect_from_server()



def request_download():
    global client_socket
    selected_indices = bottom_listbox.curselection() # Get the selected item index
    if selected_indices:

        selected_item_name = bottom_listbox.get(selected_indices[0])    # Exract the selected item name.

        # Encapsulate it and send to the server
        encapsulated_request_download = "DOWNLOAD_REQUEST:" + selected_item_name
        client_socket.sendall(f"{encapsulated_request_download}".encode('utf-8'))

        top_listbox.insert(END, f"Download request has been sent for, {selected_item_name}")
    else:
        top_listbox.insert(END, "You should select an item")


def request_files():
    global client_socket
    encapsulated_request_file_list = "FILE_LIST_REQUEST:"
    client_socket.sendall(encapsulated_request_file_list.encode('utf-8'))
    top_listbox.insert(END, "File list have been requested.")

def initialize_upload_request():
    global upload_file_path
    file_path = tkinter.filedialog.askopenfilename(title="Select a file to upload")
    upload_file_path = file_path
    if file_path:

        # Open the file and get its size
        with open(file_path, 'rb') as file:
            file_size = file.seek(0, 2) # Get file size
            file.seek(0) # Reset to beginning

            top_listbox.insert(END, f"File selected for upload: {file_path} {file_size}")
            # Send file transfer header
            filename = file_path.split("/")[-1]
            client_socket.sendall(f"FILE_TRANSFER_INITIAL:{filename}:{file_size}".encode('utf-8'))

def upload_file(file_path):

    with open(file_path, 'rb') as file:
        file_size = file.seek(0, 2)  # Get file size
        file.seek(0)  # Reset to beginning

        filename = file_path.split("/")[-1]

        top_listbox.insert(END, f"Sending file: {filename} ({file_size} bytes)")

        bytes_sent = 0  # Track the number of bytes sent
        while bytes_sent < file_size:

            max_chunk_size = 1024 - len(f"FILE_TRANSFER_CONTINUE:{filename}:".encode('utf-8')) - len(":FILE_TRANSFER_END".encode('utf-8'))
            chunk = file.read(max_chunk_size)
            bytes_sent += len(chunk)

            # Add trailer to the last chunk
            if bytes_sent == file_size:  # This is the last chunk
                chunk = f"FILE_TRANSFER_CONTINUE:{filename}:".encode('utf-8') + chunk + b":FILE_TRANSFER_END"
            else:
                chunk = f"FILE_TRANSFER_CONTINUE:{filename}:".encode('utf-8') + chunk + b":FILE_TRANSFER_NOT"
            
            # In total, always 1024 bytes, only the last byte may contain lower amount of byte, which is not a problem.

            
            client_socket.sendall(chunk)
            top_listbox.insert(END, "Chunk has been sent")

        top_listbox.insert(END, f"File {filename} sent successfully")


def delete_file():
    global client_socket
    selected_indices = bottom_listbox.curselection()
    if selected_indices:

        selected_item_name = bottom_listbox.get(selected_indices[0])
        encapsulated_request_download = "DELETE_REQUEST:" + selected_item_name
        client_socket.sendall(f"{encapsulated_request_download}".encode('utf-8'))

        top_listbox.insert(END, f"Delete request has been sent for, {selected_item_name}")
    else:
        top_listbox.insert(END, "You should select an item")


def select_base_directory():
    global base_directory
    directory = filedialog.askdirectory(title="Select Base Directory")
    if directory:
        base_directory = directory
        top_listbox.insert(END, f"Base directory set to: {base_directory}")
    else:
        top_listbox.insert(END, "No directory selected.")


#Define window
root = tkinter.Tk()
root.title("Client")
root.geometry("1200x900")
root.resizable(0,0)

#Define fonts and colors
my_font = ('Consolas', 16)
my_font_smaller = ('Consolas', 12)
black = "#010101"
light_green = "#1fc742"
grey = "#808080"
dark_orange = "#FF8C00"
light_red = "#DF4646"
back_ground = "#C8E3FF"
blue = "#8CC4FF"

root.config(bg=blue)



# Configure rows and columns to make widgets fill the space
root.grid_rowconfigure(1, weight=1)  # Listboxes row
root.grid_columnconfigure(0, weight=1)  # Main layout

# Top frame for Name, IP, Port, Connect, Disconnect, Upload, Download
top_frame = tkinter.Frame(root, pady=5)
top_frame.grid(row=0, column=0, sticky="ew")

tkinter.Label(top_frame, text="Name:").grid(row=0, column=0, padx=5)
name_entry = tkinter.Entry(top_frame, width=15)
name_entry.grid(row=0, column=1, padx=5)

tkinter.Label(top_frame, text="IP:").grid(row=0, column=2, padx=5)
ip_entry = tkinter.Entry(top_frame, width=15)
ip_entry.grid(row=0, column=3, padx=5)

tkinter.Label(top_frame, text="Port:").grid(row=0, column=4, padx=5)
port_entry = tkinter.Entry(top_frame, width=8)
port_entry.grid(row=0, column=5, padx=5)

connect_button = tkinter.Button(top_frame, text="Connect", command=connect_to_server)
connect_button.grid(row=0, column=6, padx=5)

disconnect_button = tkinter.Button(top_frame, text="Disconnect", command=disconnect_from_server)
disconnect_button.grid(row=0, column=7, padx=5)

upload_button = tkinter.Button(top_frame, text="Upload", state=DISABLED, command=initialize_upload_request)
upload_button.grid(row=0, column=8, padx=5)

download_button = tkinter.Button(top_frame, text="Download", command=request_download, state=DISABLED)
download_button.grid(row=0, column=9, padx=5)

request_button = tkinter.Button(top_frame, text="Request", command=request_files, state=DISABLED)
request_button.grid(row=0, column=10, padx=5)

delete_button = tkinter.Button(top_frame, text="Delete", command=delete_file, state=DISABLED)
delete_button.grid(row=0, column=11, padx=5)

directory_button = tkinter.Button(top_frame, text="Select Directory", command=select_base_directory, state=NORMAL) 
directory_button.grid(row = 0, column= 12, padx=5)

# Frame for listboxes
listbox_frame = tkinter.Frame(root)
listbox_frame.grid(row=1, column=0, sticky="nsew")

# Configure rows and columns to make the listboxes fill the space
listbox_frame.grid_rowconfigure(0, weight=1)  # Top listbox has less weight
listbox_frame.grid_rowconfigure(1, weight=4)  # Bottom listbox has more weight
listbox_frame.grid_columnconfigure(0, weight=1)

# Top listbox
top_listbox = tkinter.Listbox(listbox_frame)
top_listbox.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)

# Bottom listbox
bottom_listbox = tkinter.Listbox(listbox_frame)
bottom_listbox.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)

# Run the main application loop
root.mainloop()