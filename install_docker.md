# Install Docker on Raspberry Pi 5

Assuming you are running Raspberry Pi OS (64-bit) which is based on Debian 12 Bookworm.

Guidance based on: https://docs.docker.com/engine/install/debian/

```bash
# Remove old packages
for pkg in docker.io docker-doc docker-compose podman-docker containerd runc; do sudo apt-get remove $pkg; done

# Add Docker's official GPG key:
sudo apt-get update
sudo apt-get install ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc

# Add the repository to Apt sources:
echo deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/debian $(. /etc/os-release && echo "$VERSION_CODENAME") stable | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update

# Install latest package
sudo apt-get install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Verify
sudo docker run hello-world
```

To update to a specific version –

```bash
# List the available versions:
apt-cache madison docker-ce | awk '{ print $3 }'

# Should output something like –
# 5:28.3.3-1~debian.12~bookworm
# 5:28.3.2-1~debian.12~bookworm

# Set the value you want to install
VERSION_STRING=5:28.3.3-1~debian.12~bookworm

# Install
sudo apt-get install docker-ce=$VERSION_STRING docker-ce-cli=$VERSION_STRING containerd.io docker-buildx-plugin docker-compose-plugin
```