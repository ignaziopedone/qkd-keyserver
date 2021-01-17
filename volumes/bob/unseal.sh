#!/bin/bash

export VAULT_ADDR='http://172.16.0.4:8200'
./vault operator unseal 0aa3e6372ca61d6a232f30aadf70e489bbc45787761f89ca8564b2816c98ae9b8d
./vault operator unseal f67b2d8eee2f193b046081cb94e45b9b2bbed6996155102dc1ec6676459fa9ffec
