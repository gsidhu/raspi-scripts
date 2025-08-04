# Setup Samba File Sharing
How to set up Samba file sharing on your Raspberry Pi, allowing you to share files with other devices on your network.

## 1. Install Samba
```bash
sudo apt update
sudo apt install samba
```

## 2. Configure Samba
Edit the Samba configuration file:
```bash
sudo nano /etc/samba/smb.conf
```

Assuming you want to mount three drives: two connected HDDs (`/mnt/hdd1` and `/mnt/hdd2`) and the root filesystem (`/home/<USER>/`), you can add the following configuration to the end of the file:

```ini
[HDD1]
  path = /mnt/hdd1
  read only = no
  browsable = yes
  # guest ok = yes
  force user = <USER>

[HDD2]
  path = /mnt/hdd2
  read only = no
  browsable = yes
  # guest ok = yes
  force user = <USER>

[RootFS]
  path = /home/<USER>/
  read only = no
  browsable = yes
  # guest ok = yes
  force user = <USER>
```

> [!NOTE]
> Replace `<USER>` with your actual username on the Raspberry Pi.

In case you log into your Pi via SSH and thus not have a password set, you can either choose to enable public (passwordless) access or set a password for your user account. If you want to enable public access, uncomment the `guest ok = yes` line in each section.

> [!WARNING]
> The `guest ok = yes` setting allows anyone on your network to access the shared folders without a password. If you want to restrict access, you can comment it out or set it to `no`.

## 3. (Optional but Recommended) Create User for Samba
If you want to set up a user for Samba access, you can create a Samba user with the following command:
```bash
sudo smbpasswd -a <USER>
```

Replace `<USER>` with your actual username. You will be prompted to set a password for this user. You can then use this username and password to access the shared folders.

## 4. Ensure You Have the Correct Permissions
Make sure the user has the necessary permissions to access the directories you are sharing. 

1. Find out about the connected drives with `sudo blkid`. It should output something like:
  ```
  /dev/sda1: LABEL="..." BLOCK_SIZE="..." UUID="..." TYPE="ext4" PARTUUID="..."
  /dev/sdb1: LABEL="..." BLOCK_SIZE="..." UUID="..." TYPE="ext4" PARTUUID="..."
  ```
2. Get your `uid` and `gid` with `id <USER>`. It should output something like:
  ```
  uid=1000(<USER>) gid=1000(<USER>) groups=1000(<USER>),...
  ```
3. Make sure the drives are unmounted. You can do this with:
```bash
sudo umount /mnt/hdd1
sudo umount /mnt/hdd2
```
4. Edit the `/etc/fstab` file to ensure the drives are mounted with the correct permissions. For example:
```bash
sudo nano /etc/fstab
# Add these lines at the end of the file
## If it's an NTFS drive -
UUID=<YOUR_DRIVE_UUID_HERE> /mnt/hdd1 ntfs-3g defaults,uid=<YOUR_UID>,gid=<YOUR_GID>,umask=002,fmask=113 0 0
## If it's an exfat drive -
UUID=<YOUR_DRIVE_UUID_HERE> /mnt/hdd2 exfat defaults,uid=<YOUR_UID>,gid=<YOUR_GID>,umask=002,dmask=002 0 0
## If it's an ext4 drive -
UUID=<YOUR_DRIVE_UUID_HERE> /mnt/hdd3 ext4 defaults,uid=<YOUR_UID>,gid=<YOUR_GID>,umask=002,dmask=002 0 0
## Example –:
UUID=687F-4665 /mnt/hdd3 ext4 defaults,uid=1000,gid=1000,umask=002,dmask=002 0 0
```
5. Mount the drives again:
```bash
# Reload the fstab file
sudo systemctl daemon-reload
# Mount all filesystems defined in fstab
sudo mount -a
```

6. Verify the drives are mounted correctly:
```bash
# They should show up in the output of
df -h
# Check the permissions with
ls -ld /mnt/wd-hdd
# Your user should have read, write, and execute permissions
```

When you restart your Raspberry Pi, these drives will be automatically mounted with the specified permissions.

## 5. Restart Samba
```bash
sudo systemctl restart samba
```

## 6. Access Shared Folder

**On Windows:**
You can now access the shared folder from other devices on your network by navigating to `\\<Raspberry_Pi_IP>\HDD1`, `\\<Raspberry_Pi_IP>\HDD2`, or `\\<Raspberry_Pi_IP>\RootFS`.

**On macOS:**
1. Open Finder.
2. Press `Command + K` to open the "Connect to Server" dialog.
3. Enter `smb://<Raspberry_Pi_IP>` and click "Connect".
4. You may need to enter the Samba username and password if you set one up. Or connect as guest if you enabled public access.
5. Select the shared drives you want to mount.