
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

## Windows Notes

On Windows, passing a 