# FreshRSS extension manager

A "package manager" for FreshRSS. It allows you to install, update and remove FreshRSS extensions easily.

## Installation

```bash
cd /path/to/FreshRSS/extensions
curl https://github.com/yzqzss/freshrss-ext-manager/raw/main/freshext.py -L -o freshext.py
chmod +x freshext.py
```

## Usage

```bash
./freshext.py update # Update extensions.json index
./freshext.py list  # List all extensions
./freshext.py show <extension> # Show information about an extension
./freshext.py install <extension> # Install an extension
./freshext.py upgrade # Upgrade all extensions
./freshext.py upgrade <extension> # Upgrade an extension
./freshext.py clean # clean cache
```

One line to install all extensions:

```bash
./freshext.py update && ./freshext.py install all # "all" is a special behavior to install all extensions
```

One line to upgrade all extensions:

```bash
./freshext.py update && ./freshext.py upgrade
```
