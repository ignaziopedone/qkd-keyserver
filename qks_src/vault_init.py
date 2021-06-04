import vaultClient 

client = vaultClient.VaultClient("localhost", 8200, token="s.9bjNBN94txdLY3txB8OLVWs6")
print("init: ", client.initialize(1,1) )
keys = ['yKnbw2WKemkdvrhZGkobVIS4EGXDc6t7I+rbLMaV2Ak=']
print("unseal: ", client.unseal(keys))
print("token: ", client.client.token)
