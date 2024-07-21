import asyncio
import websockets
import json
import traceback

connected_clients = set()
server_state = {}

# my domain
domain = 'c1@s6'
# mapping
server_mapping = {
    "c1@s7": "ws://10.13.86.167:5555"
    # Add other server mappings here
}

async def handle_client(websocket, path):
    print(f"New client connected from {path}")
    connected_clients.add(websocket)
    try:
        async for message in websocket:
            print(f"Received message from client: {message}")
            message_data = json.loads(message)
            tag = message_data.get('tag')

            if tag == 'attendance':
                presence_message = {
                    "tag": "presence",
                    "presence": [
                        {
                            "nickname": "PrimaryServer",
                            "jid": f"primary@{domain}",
                            "publickey": "PrimaryServerPem"
                        }
                    ]
                }
                await websocket.send(json.dumps(presence_message))
                print(f"Sent presence message to client: {presence_message}")
                
            if tag=='hello':
                print("I received the message")

            elif tag == 'check':
                checked_message = {"tag": "checked"}
                await websocket.send(json.dumps(checked_message))
                print(f"Sent checked message to client: {checked_message}")

            elif tag == 'message':
                from_user = message_data.get('from')
                to_user = message_data.get('to')
                info = message_data.get('info')
                print(f"Message from {from_user} to {to_user}: {info}")
                await websocket.send(json.dumps(message_data))

            elif tag == 'file':
                print(f"File transfer request: {message_data}")
                await websocket.send(json.dumps({"tag": "file_received"}))

    except websockets.ConnectionClosed:
        print("Client disconnected")
    except Exception as e:
        print(f"Error handling client: {e}")
        print(traceback.format_exc())
    finally:
        connected_clients.remove(websocket)

async def send_sequence_messages(websocket, server_id):
    try:
        attendance_message = {"tag": "attendance"}
        await websocket.send(json.dumps(attendance_message))
        print(f"Sent attendance message to {server_id}: {attendance_message}")
        
        response = await websocket.recv()
        print(f"Received response from {server_id}: {response}")

        check_message = {"tag": "check"}
        await websocket.send(json.dumps(check_message))
        print(f"Sent check message to {server_id}: {check_message}")
        
        response = await websocket.recv()
        print(f"Received response from {server_id}: {response}")

        presence_message = {
            "tag": "presence",
            "presence": [
                {
                    "nickname": "PrimaryServer",
                    "jid": f"primary@{domain}",
                    "publickey": "PrimaryServerPem"
                }
            ]
        }
        await websocket.send(json.dumps(presence_message))
        print(f"Sent presence message to {server_id}: {presence_message}")
        
        response = await websocket.recv()
        print(f"Received response from {server_id}: {response}")

        server_state[server_id] = 'ready'

    except websockets.ConnectionClosed as e:
        print(f"WebSocket connection closed: {e}")
    except Exception as e:
        print(f"Error in send_sequence_messages: {e}")
        print(traceback.format_exc())

async def connect_to_server(uri, server_id):
    while True:
        try:
            async with websockets.connect(uri) as websocket:
                print(f"Connected to Server at {uri}")
                await send_sequence_messages(websocket, server_id)

                if all(state == 'ready' for state in server_state.values()):
                    print("Both servers are ready for communication. You can now send messages.")
                    while True:
                        message = await asyncio.get_event_loop().run_in_executor(None, input, "Enter message to send: ")
                        chat_message = {
                            "tag": "message",
                            "from": f"primary@{domain}",
                            "to": f"{server_id}@{domain}",
                            "info": message
                        }
                        await websocket.send(json.dumps(chat_message))
                        response = await websocket.recv()
                        print(f"Received response from {server_id}: {response}")

        except websockets.ConnectionClosed:
            print(f"Connection to Server at {uri} closed. Reconnecting in 5 seconds...")
        except OSError as e:
            print(f"OS error in connection with Server at {uri}: {e}")
            print(traceback.format_exc())
        except Exception as e:
            print(f"Unexpected error in communication with Server at {uri}: {e}")
            print(traceback.format_exc())
        await asyncio.sleep(5)

async def connect_to_all_servers():
    tasks = [asyncio.create_task(connect_to_server(uri, server_id)) for server_id, uri in server_mapping.items()]
    await asyncio.gather(*tasks)

async def main():
    server = await websockets.serve(handle_client, "localhost", 5555)
    print("Primary server started on port 5555")
    try:
        await asyncio.gather(server.wait_closed(), connect_to_all_servers())
    except Exception as e:
        print(f"Server error: {e}")
        print(traceback.format_exc())
    finally:
        server.close()
        await server.wait_closed()

if __name__ == "__main__":
    asyncio.run(main())
