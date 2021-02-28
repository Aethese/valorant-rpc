import api,utils
import asyncio
import json
import base64
import ssl
import websockets
from pypresence import Presence
import time
import urllib3
import os
import subprocess
import psutil
from psutil import AccessDenied
urllib3.disable_warnings()

ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

client_id = "811469787657928704"
RPC = Presence(client_id)

last_presence = {}

def is_process_running(required_processes=["VALORANT.exe", "RiotClientServices.exe"]):
    processes = []
    for proc in psutil.process_iter():
        try:
            processes.append(proc.name())
        except (PermissionError, AccessDenied):
            pass 
    for process in required_processes:
        if process in processes:
            return True
    return False


def update_rpc(state):
    data = json.loads(base64.b64decode(state))
    print(data)

    #party state
    party_state = "Solo" 
    if data["partySize"] > 1:
        party_state = "In a Party"
    party_state = "In an Open Party" if not data["partyAccessibility"] == "CLOSED" else party_state

    queue_id = utils.queue_ids[data["queueId"]]
    if data["partyState"] == "CUSTOM_GAME_SETUP":
        queue_id = "Custom"

    party_size = [data["partySize"],data["maxPartySize"]] if not data["partySize"] == 1 else [data["partySize"],data["maxPartySize"]] if (data["partySize"] == 1 and data["partyAccessibility"] != "CLOSED") else None


    #queue timing stuff
    time = utils.parse_time(data["queueEntryTime"])
    if not data["partyState"] == "MATCHMAKING" and not data["sessionLoopState"] == "INGAME" and not data["partyState"] == "MATCHMADE_GAME_STARTING" and not data["sessionLoopState"] == "PREGAME":
        time = False
    if data["partyState"] == "CUSTOM_GAME_SETUP":
        time = False

 
    if not data["isIdle"]:
        #menu
        if data["sessionLoopState"] == "MENUS" and data["partyState"] != "CUSTOM_GAME_SETUP":
            RPC.update(
                state=party_state,
                details=("In Queue" if data["partyState"] == "MATCHMAKING" else "Lobby") + (f" - {queue_id}" if queue_id else ""),
                start=time if not time == False else None,
                large_image="game_icon",
                large_text="VALORANT",
                small_image="crown_icon" if utils.validate_party_size(data) else None,
                small_text="Party Leader" if utils.validate_party_size(data) else None,
                party_id=data["partyId"],
                party_size=party_size,
            )

        #custom setup
        elif data["sessionLoopState"] == "MENUS" and data["partyState"] == "CUSTOM_GAME_SETUP":
            game_map = utils.maps[data["matchMap"].split("/")[-1]]
            RPC.update(
                state=party_state,
                details="Lobby" + (f" - {queue_id}" if queue_id else ""),
                start=time if not time == False else None,
                large_image=f"splash_{game_map.lower()}",
                large_text=game_map,
                small_image="crown_icon" if utils.validate_party_size(data) else None,
                small_text="Party Leader" if utils.validate_party_size(data) else None,
                party_id=data["partyId"],
                party_size=party_size,
            )

        #agent select
        elif data["sessionLoopState"] == "PREGAME":
            game_map = utils.maps[data["matchMap"].split("/")[-1]]
            RPC.update(
                state=party_state,
                details="Agent Select" + (f" - {queue_id}" if queue_id else ""),
                start = time if not time == False else None,
                large_image=f"splash_{game_map.lower()}",
                large_text=game_map,
                small_image=utils.mode_images[queue_id.lower()],
                party_id=data["partyId"],
                party_size=party_size,
            )

        #ingame
        elif data["sessionLoopState"] == "INGAME" and not data["provisioningFlow"] == "ShootingRange":
            game_map = utils.maps[data["matchMap"].split("/")[-1]]
            score = [data["partyOwnerMatchScoreAllyTeam"],data["partyOwnerMatchScoreEnemyTeam"]]
            RPC.update(
                state=party_state,
                details=f"{queue_id.upper()}: {score[0]} - {score[1]}",
                start = time if not time == False else None,
                large_image=f"splash_{game_map.lower()}",
                large_text=game_map,
                small_image=utils.mode_images[queue_id.lower()],
                party_id=data["partyId"],
                party_size=party_size,
            )

        #ingame//range
        elif data["sessionLoopState"] == "INGAME" and data["provisioningFlow"] == "ShootingRange":
            game_map = utils.maps[data["matchMap"].split("/")[-1]]
            RPC.update(
                state=party_state,
                details="THE RANGE",
                large_image=f"splash_{game_map.lower()}",
                large_text=game_map,
                small_image=utils.mode_images[queue_id.lower()],
                party_id=data["partyId"],
                party_size=party_size,
            )


    elif data["isIdle"]:
        RPC.update(
            state="Away",
            details="Lobby" + (f" - {queue_id}" if queue_id else ""),
            large_image="game_icon",
            large_text="VALORANT",
            small_image="away_icon",
        )


def listen():
    global last_presence
    while True:
        if not is_process_running():
            print("valorant closed, exiting")
            quit()
        presence = api.get_presence(lockfile)
        if presence == last_presence:
            last_presence = presence
            continue
        update_rpc(presence)
        last_presence = presence
        time.sleep(1)

if __name__=="__main__":
    
    if not is_process_running():
        print("valorant not opened, attempting to run...")
        subprocess.Popen([os.environ['RCS_PATH'], "--launch-product=valorant", "--launch-patchline=live"])
        while not is_process_running():
            print("waiting for valorant...")
            time.sleep(1)

    RPC.connect()

    RPC.update(
        state="Loading",
        large_image="game_icon",
        large_text="VALORANT"
    )

    lockfile = api.get_lockfile()
    if lockfile is None:
        while lockfile is None:
            print("waiting for lockfile...")
            lockfile = api.get_lockfile()
            time.sleep(1)
    print("lockfile loaded!")
    presence = api.get_presence(lockfile)
    if presence is None:
        while presence is None:
            print("waiting for presence...")
            presence = api.get_presence(lockfile)
            time.sleep(1)
    update_rpc(presence)
    print(f"LOCKFILE: {lockfile}")
    loop = asyncio.get_event_loop()
    loop.run_until_complete(listen())