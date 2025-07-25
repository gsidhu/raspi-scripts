You can assign a static IP address to a Pi (or any device) on your local network using the router's GUI tool.

When installing Pi OS using the official Imager tool you can fill in the WiFi SSID and password so the Pi should autoconnect every time it boots up.

For my D-Link DIR-825 router –
1. Go to `192.168.0.1
2. Username: admin Password: admin
3. Check that the Pi's name shows up under connected devices.
4. Go to Settings > Network. Scroll down to Static IP Addresses under IPv4. Select 'Known Clients' and choose the Pi device.