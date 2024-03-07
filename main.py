#!/usr/bin/env python3

import asyncio
import websockets
import argparse
import json
import tweepy
import time
import aiohttp
import aiofiles
import discord


with open("config.json") as config:
    config = json.load(config)
    ckey = config["consumer_key"]
    csec = config["consumer_secret"]
    akey = config["access_token_key"]
    asec = config["access_token_secret"]
    bearer = config["bearer_token"]
    wsIP = config["wsIP"]
    wsPort = config["wsPort"]
    twitacc = config["twitacc"]
    disckey = config["disckey"]
    whaleamount = config["whaleamount"]

#client = discord.Client()

#client.run(disckey)
#print('We have logged in as {0.user}'.format(client))


client = tweepy.Client(consumer_key=ckey,
                  consumer_secret=csec,
                  access_token=akey,
                  access_token_secret=asec,
                       bearer_token=bearer)

#print(api.VerifyCredentials())

parser = argparse.ArgumentParser()
parser.add_argument('--host', dest='host', type=str, default=wsIP)
parser.add_argument('--port', dest='port', type=str, default=wsPort)
args = parser.parse_args()


async def get_price():
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get("https://api.coingecko.com/api/v3/simple/price?ids=banano&vs_currencies=usd") as resp:
                jsonResp = await resp.json()
                print(jsonResp)
                price = jsonResp["banano"]["usd"]
                print(price)
                return price
    except Exception as e:
        print(e)
        return 0


async def get_label(address):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                    "https://kirby.eu.pythonanywhere.com/api/v1/resources/addresses?address=" + address) as resp:
                print(resp.headers["Content-Type"])
                if resp.headers["Content-Type"] == "application/json":
                    jsonResp = await resp.json()
                    if len(jsonResp) > 0:
                        label = jsonResp[0]["alias"]
                        return label
                    else:
                        return address[:16] + "..."
                else:
                    return address[:16] + "..."
    except Exception as e:
        print(e)
        return address[:16] + "..."


def subscription(topic: str, ack: bool = False, options: dict = None):
    d = {"action": "subscribe", "topic": topic, "ack": ack}
    if options is not None:
        d["options"] = options
    return d


def update(topic: str, options: dict, ack: bool = False):
    return {"action": "update", "topic": topic, "ack": ack, "options": options}


def pretty(message):
    return json.dumps(message, indent=4)


def send_tweet(tweet):
    #try:
        #tweets = client.get_users_tweets(id=twitacc, max_results=1)
        #lastTweet = tweets[0].text
    #except Exception as e:
        #print(e)
        #print("Probably failed to get Twitter timeline at ", time.ctime())
    try:
        #if lastTweet != tweet:
        client.create_tweet(text=tweet)
    except Exception as exc:
        print(exc)
        if exc == "[{\'message\': \'Rate limit exceeded\', \'code\': 88}]":
            print("Rate limit has been hit. Sleeping for 15 minutes", time.ctime())
            time.sleep(900)
        if exc == "[{\'message\': \'Over capacity\', \'code\': 130}]":
            print("Twitter is sad right now. Sleeping for 10 minutes", time.ctime())
            time.sleep(600)
        else:
            print("Well this happened...", time.ctime())


async def main():
    while 1:
        try:
            async with websockets.connect(f"ws://{args.host}:{args.port}") as websocket:

                # Subscribe to both confirmation and votes
                # You can also add options here following instructions in
                # https://docs.nano.org/integration-guides/websockets/

                await websocket.send(json.dumps(subscription("confirmation", options={"include_election_info": "false", "include_block":"true"}, ack=True)))
                print(await websocket.recv()) # ack

                # V21.0+
                # await websocket.send(json.dumps(subscription("work", ack=True)))
                # print(await websocket.recv())  # ack

                lastsender = ""
                lastamount = ""
                lastrecipient = ""
                throttle = False
                while 1:

                    rec = json.loads(await websocket.recv())
                    topic = rec.get("topic", None)
                    if topic:
                        message = rec["message"]
                        if topic == "confirmation":
                            amount = round(int(message["amount"]) / 10 ** 29, 0)

                            subtype = message["block"]["subtype"]
                            block = message["hash"]
                            sender = await get_label(message["account"])
                            recipient = await get_label(message["block"]["link_as_account"])
                            if message["account"] == "ban_3i63uiiq46p1yzcm6yg81khts4xmdz9nyzw7mdhggxdtq8mif8scg1q71gfy":
                                print("HELLO")

                            if subtype == "send" and amount >= whaleamount:

                                price = await get_price()
                                value = round(amount * price, 0)

                                if sender == lastsender and not throttle and amount >= whaleamount:
                                    throttle = True
                                    tweet = sender + " is sending many big payments!! Check them out!\n https://creeper.banano.cc/explorer/block/" + block
                                    send_tweet(tweet)
                                elif amount >= whaleamount and recipient != lastsender and (sender != lastrecipient and amount != lastamount):

                                    tweet = "\U0001F34C \U0001F34C \U0001F34C A big splash has been observed! \U0001F34C \U0001F34C \U0001F34C \n" + sender + " sent " + str(
                                        amount) + "$BAN ($" + str(value) + ") to " + recipient + "\nBlock: " + "https://creeper.banano.cc/explorer/block/" + block
                                    send_tweet(tweet)

                                    lastsender = sender
                                    lastrecipient = recipient
                                    lastamount = amount
        except Exception as e:
            print(e)


try:
    asyncio.get_event_loop().run_until_complete(main())
except KeyboardInterrupt:
    pass
except ConnectionRefusedError:
    print("Error connecting to websocket server. [node.websocket] enable=true must be set in ~/Nano/config-node.toml ; see host/port options with ./client.py --help")
