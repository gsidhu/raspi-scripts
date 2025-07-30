##############

# Prior Setup
## 0. Make sure to clear up unecessary stuff on the card
sudo apt clean
sudo apt autoremove -y

# Pi Zero W uses ARM64 v6 Kernel to boot
## Identify existing kernel packages 
dpkg -l | grep linux-image
## Keep the latest v6 kernel and remove all other as they are not necessary for the Pi Zero W
sudo apt purge -y \
  linux-image-6.12.25+rpt-rpi-v6 \
  linux-image-6.12.25+rpt-rpi-v7 \
  linux-image-6.12.25+rpt-rpi-v7l \
  linux-image-6.12.25+rpt-rpi-v8 \
  linux-image-6.12.34+rpt-rpi-v7 \
  linux-image-6.12.34+rpt-rpi-v7l \
  linux-image-rpi-v7 \
  linux-image-rpi-v7l \
  linux-image-rpi-v8
sudo apt autoremove -y
## Prevent reinstall of v7 and v8 kernels in future
echo -e "Package: linux-image-rpi-v7*\nPin: release *\nPin-Priority: -1" | sudo tee /etc/apt/preferences.d/no-v7-kernels
echo -e "Package: linux-image-rpi-v8*\nPin: release *\nPin-Priority: -1" | sudo tee /etc/apt/preferences.d/no-v8-kernels

##############

# Backup Process using a MacBook
## 1. Plug the microSD card into the Mac and identify device
diskutil list

## 2. Unmount the device (disk2, disk4 whatever)
diskutil unmountDisk /dev/disk4

## 3. Create a backup image (it runs slow cuz microSD cards are slow)
sudo dd if=/dev/rdisk4 of=/Users/thatgurjot/pi_zero_fresh_backup_250725.img bs=4m status=progress

## (Optional)
### The back up image will always be the size of the microSD card (32GB or whatever).
### Shrink it using pishrink.sh (on Linux)
wget https://raw.githubusercontent.com/Drewsif/PiShrink/master/pishrink.sh
chmod +x pishrink.sh
./pishrink.sh /Users/thatgurjot/pi_zero_fresh_backup_250725.img

### Or using PiShrink-macOS (on macOS)
curl -LO https://github.com/lisanet/PiShrink-macOS/archive/master.zip
unzip master
cd PiShrink-macOS-master
make # This can take a while
sudo make install
pishrink /Users/thatgurjot/pi_zero_fresh_backup_250725.img

### Can also use PiShrink via Docker on macOS: https://github.com/Drewsif/PiShrink/issues/326

##############

# Restore the image using Official Raspberry Pi Imager or Balena Etcher.
## Select the 'Custom Image (.img)' option for your device.

## If you shrunk the image before, you'll have to expand it after restoring
# 1. SSH into the Pi and run the config tool: sudo raspi-config
# 2. Navigate to: Advanced Options → Expand Filesystem
# 3. After it completes, reboot: sudo reboot
# 4. Once rebooted, run: df -h
# You should now see the /dev/mmcblk0p2 size closer to 30GB.