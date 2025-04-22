# Hetznat64

### What is it?

A NAT64/DNS64 system to provide IPv6-only servers in your hetzner cloud account with access to the IPv4 internet.

### Why does it exist?

By default, Hetzner does not assign public IPv4 addresses to servers. Yes you can get one for an extra 0.50/month, but I'm psychotic about spending money. Why do you think I created a Hetzner account in the first place? I thought maybe I could get by without IPv4. I was wrong. Because it turns out that Github still doesn't support IPv6. Nevermind that it was introduced in 1995 and ratified as an internet standard in 2017. Nevermind that Regional Internet Registries have been dealing with IPv4 exhaustion since 2011. Nevermind that over [40% of traffic to google.com](https://www.google.com/intl/en/ipv6/statistics.html#tab=ipv6-adoption) comes over IPv6. GitHub, the backbone of modern software development owned by a multi-trillion dollar technology company, still doesn't support IPv6. And a hobby development server without access to GitHub is about as useful as a screen door on a submarine.

There are much simpler [alternative solutions](https://www.transip.eu/knowledgebase/5277-using-transip-github-ipv6-proxy) if you just need to access GitHub. Or [slightly more complicated options](https://nat64.xyz/) if you want general access to the IPv4 internet via a public NAT64 service. But all of these involve sending your traffic through an untrusted third party, which didn't appeal to me. So I created this project to see if I could self-host my own functional NAT64 service since I already have a Raspberry Pi running on a [dual-stack](https://whatismyipaddress.com/dual-stack) network at home.

### What does it do?

There are two components to this project: a NAT64 service you run on a dual-stack network, and an agent that you run on your Hetzner server.

The NAT64 service monitors your Hetzner account for new servers matching the labels you specify and configures a WireGuard tunnel for each one. It sends information about the tunnel to the agent running on that host and attempts to establish a connection. On this tunnel, it expects to receive [4in6 traffic](https://en.wikipedia.org/wiki/4in6) destined for addresses using the [well-known DNS64 prefix](https://datatracker.ietf.org/doc/html/rfc6052#section-2.1) from the server, which it proxies via [tayga](http://www.litech.org/tayga/) to the IPv4 internet. Using the standard prefix allows for decoupling of the DNS & NAT functions.

The agent listens for peer information from the NAT64 service and configures the server to use the WireGuard tunnel as its default route for DNS64-prefixed IPv6 addresses.

### FAQ

#### Why does the agent listen for peer information from the NAT64 service instead of the other way around?

The router I'm running the service behind has an unconfigurable IPv6 firewall which blocks inbound connections. The only way I can get a tunnel to work is by initiating it from the service side.

#### Why is it in Python?

I want to get more involved in the AI/ML community and Python is the language of choice for that. This seemed like a good opportunity to get some practice.
