# Housekeeping Commands
These commands help you manage your Pi in a headless setup.

## Check Pi's IP address
```bash
hostname -I
```

## Check Pi's hostname
```bash
hostname
```

## Check Pi's temperature
```bash
vcgencmd measure_temp
```

## Check Pi's CPU usage
```bash
htop
```

## Check Pi's memory usage
```bash
free -h
```

## Check Pi's disk usage
```bash
df -h
```

## Check connected disks (storage devices)
```bash
lsblk
```

## Check file systems
```bash
sudo fdisk -l
```

## Mount a disk
```bash
sudo mkdir /mnt/hdd1
sudo mount /dev/sdX1 /mnt/hdd1
```
Replace `/dev/sdX1` with the actual device identifier (from `lsblk`) and `/mnt/hdd1` with the desired mount point.

Setting correct permissions might be necessary. [See this section for details.](./setup_samba_filesharing#4-ensure-you-have-the-correct-permissions)

## Run a speedtest
```bash
python3 -m venv speedtest-venv
source speedtest-venv/bin/activate
pip install speedtest-cli
speedtest-cli
```
