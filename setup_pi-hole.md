It is helpful to have a [static IP address](./static_ip_address.md) for your Pi before you setup Pi-Hole on it.

## Install Pi-hole
SSH into the Pi and run –
```bash
curl -sSL https://install.pi-hole.net | bash
```

The setup script is relatively self-explanatory, but follow these tips if you aren’t sure how to proceed:
* When prompted to choose an upstream DNS provider, choose OpenDNS
* Include StevenBlack’s Unified Hosts List
* Enable query logging

> [!NOTE]  
> After the installation, make sure to save the `admin password` in your password manager!

## (Option 1) Setup your Pi as the DNS for your router
This will block ads on any device that is connected to your WiFi. That includes your phone, iPad, computer, TV, fridge, everything.

For my D-Link DIR-825 router –
1. Go to `192.168.0.1
2. Username: admin Password: admin
3. Check that the Pi's name shows up under connected devices.
4. Go to Settings > Internet > DNS. Set DNS IPv4 to Manual.

> [!NOTE]
> Save the existing values in Name Servers IPv4 in your password manager! These are the values your ISP probably put in.

5. Set your Pi's static IP as the DNS server.
6. While it kinda reduce efficacy, add `8.8.8.8` or `1.1.1.1` as the second (fallback) DNS. Your router will defer to that DNS in case your Pi bonks out (and it will).

## (Option 2) Use your Pi as the DNS selectively on your devices
Not all devices support this (your fridge likely doesn't).

1. On the Mac, go to `WiFi Settings` and cick on `Details` next to the connected network (your home network presumably).
2. Add your Pi's static IP address under DNS.
3. Add `8.8.8.8` or `1.1.1.1` as the second (fallback) DNS. Your Mac will defer to that DNS in case your Pi bonks out (and it will).

A similar setting exists on the iPhone and iPad.