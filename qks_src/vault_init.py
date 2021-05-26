import vaultClient 

client = vaultClient.VaultClient("localhost", 8200)
print("init: ", client.initialize(1,1) )

print("unseal: ", client.unseal())
print("token: ", client.client.token)
