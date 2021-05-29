import vaultClient 

client = vaultClient.VaultClient("localhost", 8200)
print("init: ", client.initialize(1,1) )
keys = None
print("unseal: ", client.unseal(keys))
print("token: ", client.client.token)
