from asyncVaultClient import vaultClient 
import asyncio

async def init(): 
    client = vaultClient.VaultClient("localhost", 8200, token=None)
    print("init: ", client.initialize(1,1) )
    keys = None # ['yKnbw2WKemkdvrhZGkobVIS4EGXDc6t7I+rbLMaV2Ak=']
    print("unseal: ", client.unseal(keys))
    print("token: ", client.client.token)

asyncio.run(init())