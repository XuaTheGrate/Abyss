import asyncio
import signal
import websockets


CLIENTS = {}


async def dispatch(data):
    for cluster_name, client in CLIENTS.items():
        await client.send(data)
        print(f'> Cluster[{cluster_name}]')


# pylint: disable=unused-argument
async def serve(websocket, path):
    cluster_name = await websocket.recv()
    cluster_name = cluster_name.decode()
    if cluster_name in CLIENTS:
        print(f"! Cluster[{cluster_name}] attempted reconnection")
        await websocket.close(4029, "already connected")
        return
    CLIENTS[cluster_name] = websocket
    try:
        await websocket.send(b'{"status":"ok"}')
        print(f'$ Cluster[{cluster_name}] connected successfully')
        async for msg in websocket:
            print(f'< Cluster[{cluster_name}]: {msg}')
            await dispatch(msg)
    finally:
        CLIENTS.pop(cluster_name)
        print(f'$ Cluster[{cluster_name}] disconnected')
# pylint: enable=unused-argument


def start():
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    signal.signal(signal.SIGTERM, signal.SIG_DFL)

    server = websockets.serve(serve, 'localhost', 42069)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(server)
    loop.run_forever()
