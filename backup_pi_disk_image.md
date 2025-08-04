# Backup Raspberry Pi Zero W Disk Image
This guide is for creating a backup of the Raspberry Pi Zero W microSD card image. You can use this image to restore the Pi Zero W to the saved state or to create multiple identical setups.

> [!NOTE]
> This guide is specifically for the Raspberry Pi Zero W. But it should work for other Raspberry Pi models as well. The main thing to keep in mind is that the backup image will be the size of the boot disk. So if you are booting from a 250GB SSD, it may not be ideal. Best use a small-ish microSD card (up to 32GB) for this purpose. But that's just my opinion.

## Preparation on the Raspberry Pi Zero W

Before you begin, make sure to clear up unecessary stuff on the card
```bash
sudo apt update
sudo apt clean
sudo apt autoremove -y
```

> [!NOTE]
> Pi Zero W uses ARM64 v6 Kernel to boot! You don't need the other ones!

1. Identify existing kernel packages:
```bash
dpkg -l | grep linux-image
```

2. Keep the latest v6 kernel and remove all other as they are not necessary for the Pi Zero W:

```bash
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
```

3. Prevent reinstall of v7 and v8 kernels in future:
```bash
echo -e "Package: linux-image-rpi-v7*\nPin: release *\nPin-Priority: -1" | sudo tee /etc/apt/preferences.d/no-v7-kernels
echo -e "Package: linux-image-rpi-v8*\nPin: release *\nPin-Priority: -1" | sudo tee /etc/apt/preferences.d/no-v8-kernels
```

## Backup Process using a MacBook
1. Plug the microSD card into the Mac and identify device:
```bash
diskutil list
```

2. Unmount the device (disk2, disk4 whatever):
```bash
diskutil unmountDisk /dev/disk4
```

3. Create a backup image (it runs slow cuz microSD cards are slow):
```bash
sudo dd if=/dev/rdisk4 of=/Users/thatgurjot/pi_zero_fresh_backup_250725.img bs=4m status=progress
```

Done! You now have a backup image of your Raspberry Pi Zero W microSD card.

## (Optional) Shrink the Backup Image

The back up image will always be the size of the microSD card (32GB or whatever).

### Shrink it using pishrink.sh (on Linux)
```bash
wget https://raw.githubusercontent.com/Drewsif/PiShrink/master/pishrink.sh
chmod +x pishrink.sh
./pishrink.sh /Users/thatgurjot/pi_zero_fresh_backup_250725.img
```

### Or using PiShrink-macOS (on macOS)
```bash
curl -LO https://github.com/lisanet/PiShrink-macOS/archive/master.zip
unzip master
cd PiShrink-macOS-master
make # This can take a while
sudo make install
pishrink /Users/thatgurjot/pi_zero_fresh_backup_250725.img
```

Alternatively, you can use PiShrink via Docker on macOS: https://github.com/Drewsif/PiShrink/issues/326

## Restore the image using Official Raspberry Pi Imager
1. Load the Raspberry Pi Imager
2. Select the device you want to restore the image to (the microSD card).
3. Select the 'Custom Image (.img)' option for your device.

### Expand Filesystem after restoring

If you shrunk the image before, you'll have to expand it after restoring:

1. SSH into the Pi and run the config tool: `sudo raspi-config`
2. Navigate to: **Advanced Options → Expand Filesystem**
3. After it completes, reboot: `sudo reboot`
4. Once rebooted, run: `df -h`

You should now see the /dev/mmcblk0p2 size closer to 30GB.