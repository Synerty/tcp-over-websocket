
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

## Example Client Configuration

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
