# Set up PhotoPrism

1. First, [install docker](/install_docker.md)

2. Then:

```bash
mkdir ~/photoprism
cd ~/photoprism

# Get the docker compose file
wget https://dl.photoprism.app/docker/arm64/compose.yaml

# Pull the latest image for good measure
sudo docker pull --platform=arm64 photoprism/photoprism:latest
```

3. Edit the compose file (`nano compose.yaml`). If you want to use SQLite over MariaDB, set `PHOTOPRISM_DATABASE_DRIVER: "sqlite"` and comment out or delete the MariaDB configuration.

4. Start the server:

```bash
sudo docker compose up -d
```

To stop the server:

```bash
sudo docker compose stop
```

## Relevant sections from the official documentation

Link: https://docs.photoprism.app/getting-started/docker-compose/

##### /photoprism/originals

The *originals* folder contains your original photo and video files. `~/Pictures` will be mounted by default, where `~` is a shortcut for your home directory:

```yaml
services:
  photoprism:
    volumes:
      - "~/Pictures:/photoprism/originals"
```

We recommend that you change `~/Pictures` to the directory where your existing media files are, for example:

```yaml
      - "/mnt/photos:/photoprism/originals"
```

Additional directories can be mounted as sub folders of `/photoprism/originals` (depending on [overlay filesystem support](troubleshooting/docker.md#overlay-volumes)):

```yaml
    volumes:
      - "/mnt/photos:/photoprism/originals"
      - "/mnt/videos:/photoprism/originals/videos"
```

On Windows, prefix the host path with the drive letter and use `/` instead of `\` as separator:

```yaml
    volumes:
      - "D:/Example/Pictures:/photoprism/originals"
```

> [!NOTE]
> When *read-only mode* is enabled, all features that require write permission to the *originals* folder are disabled, e.g. [WebDAV](../user-guide/sync/webdav.md), uploading and deleting files. To do this, set `PHOTOPRISM_READONLY` to `"true"` in the `environment` section of your `compose.yaml` file.[^2] You can additionally [mount volumes with the `:ro` flag](https://docs.docker.com/compose/compose-file/compose-file-v3/#short-syntax-3) so that writes are also blocked by Docker.

##### /photoprism/storage

The *storage* folder is used to save config, cache, backup, thumbnail, and sidecar files. It must always be specified so that you do not lose these files after a restart or upgrade.
If available, we recommend you put the *storage* folder on a [local SSD drive](https://docs.photoprism.app/getting-started/troubleshooting/performance/#storage) for best performance. You can otherwise keep the default and store the files in a folder relative to the current directory:

```yaml
services:
  photoprism:
    volumes:
      - "./storage:/photoprism/storage"
```

> [!NOTE]
> Never configure the *storage* folder to be inside the *originals* folder unless the name starts with a `.` to indicate that it is hidden.
> Should you later want to move your instance to another host, the easiest and most time-saving way is to copy the entire *storage* folder along with your *originals* and *database*.

##### /photoprism/import

You can optionally mount an *import* folder from which files can be transferred to the *originals* folder in a structured way that avoids duplicates, for example:

```yaml
services:
  photoprism:
    volumes:
      - "/mnt/media/usb:/photoprism/import"
```

[Imported files](https://docs.photoprism.app/user-guide/library/import/) receive a canonical filename and will be organized by year and month. You should never configure the *import* folder to be inside the *originals* folder, as this will cause a loop by importing already indexed files.
