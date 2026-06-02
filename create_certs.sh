#!/bin/sh

# Create SSL certificates for development
mkcert -install
mkcert localhost 127.0.0.1 ::1
# This will generate localhost.pem and localhost-key.pem
# Edit server.js to enable SSL:
# config.enableSSL = true;
# node server.js
