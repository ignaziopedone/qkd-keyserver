from asyncVaultClient import VaultClient 
import asyncio

async def init(): 
    client = VaultClient("localhost", 8200, token="s.G8b0bLPI35KA8yhBWCAfNgA5")
    print("init: ", await client.initialize(1,1) )
    keys =  ['ZNUv2gMf1sNz0QdnB6+z+buP2sYz53VcYsuax9rl9es='] 
    print("unseal: ", await client.unseal(keys), client.keys)
    print("token: ", client.client.token)
    await client.close()

asyncio.run(init())