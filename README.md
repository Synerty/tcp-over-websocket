
# TCP over Websocket

This package will:

- tunnel TCP traffic within a HTTP websocket
- use a websocket, 
- OPTIONALLY secured with HTTPS
- OPTIONALLY secured with client certificate authentication (Mutual TLS)
- OPTIONALLY run on Windows as a service.

TCP data is multiplexed and can tunnel in either direction once the HTTP 
Websocket is established.

TCP tunnels are defined by a `tunnelName`, one side will listen and one side 
will connect.

## Installing

Install with the following command

```
pip install tcp-over-websocket
```

NOTE: On windows, it may help to install some dependencies first, otherwise 
pip may try to build them.

```
pip install vcversioner
```

## Running

You need to configure the settings before running tco-over-websocket, but if 
you want to just see if it starts run the command

```
run_tcp_over_websocket_service
```

It will start as a client by default and try to reconnect to nothing.

## Configuration

By default the tcp-over-websocket will create a home directory 
~/tcp-over-websocket.home and create a `config.json` file in that directory.

To change the location of this directory, pass the config directory name in 
as the first argument of the python script

Here is a windows example:
```
python c:\python\Lib\site-packages\tcp_over_websocket
\run_tcp_over_websocket_service.py c:\Users\meuser\tcp-over-websocket-server.
home
```


## Example Client Configuration

Create a directory and place the following contents in a config.json file
in that directory.

```
{
    "dataExchange": {
        "enableMutualTLS": false,
        "mutualTLSTrustedCACertificateBundleFilePath": "/Users/jchesney/Downloads/tcp_svr/trusted-ca.pem",
        "mutualTLSTrustedPeerCertificateBundleFilePath": "/Users/jchesney/Downloads/tcp_svr/certs-of-peers.pem",
        "serverUrl": "http://localhost:8080",
        "tlsBundleFilePath": "/Users/jchesney/Downloads/tcp_svr/key-cert-ca-root-chain.pem"
    },
    "logging": {
        "daysToKeep": 14,
        "level": "DEBUG",
        "logToStdout": true,
        "syslog": {
            "logToSysloyHost": null
        }
    },
    "tcpTunnelConnects": [
        {
            "connectToHost": "search.brave.com",
            "connectToPort": 80,
            "tunnelName": "brave"
        }
    ],
    "tcpTunnelListens": [
        {
            "listenBindAddress": "127.0.0.1",
            "listenPort": 8091,
            "tunnelName": "duckduckgo"
        }],
    "weAreServer": false
}

```

## Example Server Configuration

```
{
    "dataExchange": {
        "enableMutualTLS": false,
        "mutualTLSTrustedCACertificateBundleFilePath": "/Users/jchesney/Downloads/tcp_svr/trusted-ca.pem",
        "mutualTLSTrustedPeerCertificateBundleFilePath": "/Users/jchesney/Downloads/tcp_svr/certs-of-peers.pem",
        "serverUrl": "http://localhost:8080",
        "tlsBundleFilePath": "/Users/jchesney/Downloads/tcp_svr/key-cert-ca-root-chain.pem"
    },
    "logging": {
        "daysToKeep": 14,
        "level": "DEBUG",
        "logToStdout": true,
        "syslog": {
            "logToSysloyHost": null
        }
    },
    "tcpTunnelConnects": [
        {
            "connectToHost": "search.brave.com",
            "connectToPort": 80,
            "tunnelName": "brave"
        }
    ],
    "tcpTunnelListens": [
        {
            "listenBindAddress": "127.0.0.1",
            "listenPort": 8091,
            "tunnelName": "duckduckgo"
        }],
    "weAreServer": false
}
```

## Windows Services

To install tcp-over-websocket, open a command prompt as administrator, and run 
the following command.

```
winsvc_tcp_over_websocket_service --username .\user-svc --password "myPa$$" --startup auto install
  
```

Use `--username` and `--password` to run the service as a non-privileged user.

---

After registering the above, you must go and re-enter the username and password. 

1. Run `servcies.msc`
2. Find the `TCP over Websocket` service
3. Open the service properties
4. Click on the `Lok On` tab
5. Click `Local System account` and click `Apply`
6. Select `This account`
7. Enter your service username and password again.
8. Click `Ok`
9. You will then get an alert saying your service user has been granted 
   permissions to `log on as a service`

---

Consider making the service restart on failure.

1. Again, Open the properties of the service in `services.msc`
2. Click on the `Recovery` tab
3. Change the `First failure` dropdown box to `Restart the Service`
4. Click `Ok`

## Server Side TLS

Never run this service with out client TLS, and especially not without 
server TLS.

NOTE: The following all assumes you have x509 certificates in ascii format.

Prepare the standard server side TLS bundle with a command similar to:

```

# Create the file containing the server or client certificates that either 
# will send.
cat Root.crt CA.crt MyServerCert.{crt,key} > key-cert-ca-root-chain.pem

# or
cat Root.crt CA.crt MyClientCert.{crt,key} > key-cert-ca-root-chain.pem


```

--

Configure the server to service on SSL:

1. Update both client and server configurations `serverUrl` to start with 
   `https`
2. Ensure the `tlsBundleFilePath` setting points to your pem bundle as 
   prepared in the code block above.
3. Restart both client and server services.

## Mutual TLS

Mutual TLS or Client Certificate Authentication is when the client also 
sends certificates to the server, and the server verifies them.

In our case, our client also verifies that the server has provided a 
specific trusted certificate.

---

For Mutual TLS / Client Certificate Authentication, ensure you have a 
certificate that has Client and Server capabilities.

```
# Run
openssl x509 -in mycert.crt -text | grep Web

# Expect to see
#                 TLS Web Server Authentication, TLS Web Client Authentication
```

---

Prepare the certificates for mutual TLS, the same commands work for both 
sides, however, you put the servers certificates in the clients mutualTLS 
config and the clients certificates in the servers mutualTLS config.

```
# Create the file that contains the certificate chain of the trusted 
certificates.

cat Root.crt CA.crt > mtls/trusted-ca-chain.pem

# Create the file containing the peer certificates to trust
cat MyServerCert.{crt,key} > certs-of-peers.pem

# or 
cat MyClientCert.{crt,key} > certs-of-peers.pem

```

---

To configure Mutual TLS, we will:
* Tell the client to send it's own certificat and chain
* Tell both the client and server what certificates to accept from the other


On the Server
1.  Set the `enableMutualTLS` to `true`
2.  Set the `mutualTLSTrustedCACertificateBundleFilePath` value to the path 
    of a file containing the Clients root and certificate authority 
    certificates.
3.  Set the `mutualTLSTrustedPeerCertificateBundleFilePath` to the path of a 
    file containing the Clients public certificate.

On the Client
1.  Set the `tlsBundleFilePath` as per the last section.
2.  Set the `enableMutualTLS` to `true`
3.  Set the `mutualTLSTrustedCACertificateBundleFilePath` value to the path 
    of a file containing the Servers root and certificate authority 
    certificates.
4.  Set the `mutualTLSTrustedPeerCertificateBundleFilePath` to the path of a 
    file containing the Servers public certificate.


