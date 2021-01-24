#!/bin/bash

export VAULT_ADDR='http://10.0.2.15:8200'
./vault operator unseal 62cbf8b7c181822c774d95d6ae5bd29d8f97f642f30cdcb6cc511869447131dcf8
./vault operator unseal d818f6a40a94882d78feb4fbf84f89e2b29a5ef6e45d3b3beae4dfc08a06351d63
