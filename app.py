#!/usr/bin/env python

import asyncio
import json
from websockets.asyncio.server import serve
from connect4 import PLAYER1, PLAYER2, Connect4

import connect4

import secrets


JOIN = {}
WATCH = {}

async def broadcast(connected, event):
    for connection in connected:
        await connection.send(event)


async def play(websocket, game, player, connected):
    async for message in websocket:
        event = json.loads(message)
        column = int(event["column"])
        try:
            row = game.play(player, column)
        except ValueError as errorMSG:
            error = {"type": "error", "message": errorMSG.args[0]}
            await websocket.send(json.dumps(error))
            continue

        return_event = {"type": "play", "player": player, "column": column, "row": row}
        await broadcast(connected, json.dumps(return_event))
        if game.last_player_won:
            win_event = {"type": "win", "player": player}
            await broadcast(connected, json.dumps(win_event))

async def start(websocket):
    # Initialize a Connect Four game, the set of WebSocket connections
    # receiving moves from this game, and secret access token.
    game = Connect4()
    connected = {websocket}

    join_key = secrets.token_urlsafe(12)
    JOIN[join_key] = game, connected
    watch_key = secrets.token_urlsafe(12)
    WATCH[watch_key] = game, connected

    try:
        # Send the secret access token to the browser of the first player,
        # where it'll be used for building a "join" link.
        event = {
            "type": "init",
            "join": join_key,
            "watch": watch_key
        }
        await websocket.send(json.dumps(event))
        await play(websocket, game, PLAYER1, connected)

    finally:
        connected.remove(websocket)
        del JOIN[join_key]
        del WATCH[watch_key]

async def watch(websocket, watch_key):
    try:
        game, connected = WATCH[watch_key]
    except KeyError:
        event = {
            "type": "error",
            "message": "game not found",
        }
        await websocket.send(json.dumps(event))
        return

    connected.add(websocket)
    try:
        await replay(websocket, game)

        await websocket.wait_closed()

    finally:
        connected.remove(websocket)

async def replay(websocket, game):
    for player, column, row in game.get_moves():
        event = {
            "type":"play",
            "player": player,
            "column": column,
            "row": row
        }
        await websocket.send(json.dumps(event))

async def join(websocket, join_key):
    # Find the Connect Four game.
    try:
        game, connected = JOIN[join_key]
    except KeyError:
        event = {
            "type": "error",
            "message": "game not found",
        }
        await websocket.send(json.dumps(event))
        return

    # Register to receive moves from this game.
    connected.add(websocket)
    try:
        await replay(websocket, game)

        await play(websocket, game, PLAYER2, connected)

    finally:
        connected.remove(websocket)

def player_selector(player_name):
    print(player_name)
    return PLAYER1

async def handler(websocket):
    # Receive and parse the "init" event from the UI.
    message = await websocket.recv()
    event = json.loads(message)
    assert event["type"] == "init"

    if "join" in event:
        # Second player joins an existing game.
        await join(websocket, event["join"])
    elif "watch" in event:
        await watch(websocket, event["watch"])
    else:
        # First player starts a new game.
        await start(websocket)




"""
async def handler(websocket):
    game = Connect4()
    async for message in websocket:
        event = json.loads(message)
        player = game.current_player
        column = int(event["column"])
        row = 0
        try:
            row = game.play(player, column)
        except ValueError as errorMSG:
            error = {"type":"error","message":errorMSG.args[0]}
            await websocket.send(json.dumps(error))
            continue

        return_event = {"type":"play","player":player,"column":column,"row":row}
        await websocket.send(json.dumps(return_event))
        if game.last_player_won:
            win_event = {"type":"win","player":player}
            await websocket.send(json.dumps(win_event))
"""



async def main():
    async with serve(handler, "", 8001) as server:
        await server.serve_forever()


if __name__ == '__main__':
    asyncio.run(main())