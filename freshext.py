#!/usr/bin/env python3
import json
import shutil
import subprocess
import requests as rq
import urllib.parse
import os
from dataclasses import dataclass, fields
import argparse
from pathlib import Path
from typing import List, Optional

try:
    from rich import print
except ImportError:
    pass

EXT_META = "metadata.json"
EXT_MAIN = "extension.php"
COMMON_WEB_SERVER_USERS = ['www-data', 'httpd', 'www', 'apache']

PKG_TMP_DIR = Path('~/.cache/freshrss-ext-manager').expanduser()

@dataclass
class Metadata:
    """
    The metadata.json file defines your extension through a number of important elements. It must contain a valid JSON array containing the following entries:

        name: the name of your extension
        author: your name, your e-mail address … but there is no specific format to adopt
        description: a description of your extension
        version: the current version number of the extension
        entrypoint: Indicates the entry point of your extension. It must match the name of the class contained in the file extension.php without the suffix Extension (so if the entry point is HelloWorld, your class will be called HelloWorldExtension)
        type: Defines the type of your extension. There are two types: system and user. We will study this difference right after.

    Only the name and entrypoint fields are required.
    """
    name: str
    entrypoint: str

    author: Optional[str] = None
    description: Optional[str] = None
    version: Optional[str] = None
    type: Optional[str] = None

    def __init__(self, **kwargs):
        # Get the names of the fields that are defined in the dataclass
        valid_fields = {f.name for f in fields(self)}

        # Iterate over the kwargs
        for key, value in kwargs.items():
            # If the key is not a field of the Repo class, ignore it
            if key not in valid_fields:
                continue
            # Otherwise, set the attribute
            setattr(self, key, value)
        
        self.__post_init__()


    def __post_init__(self):
        assert self.name and self.entrypoint
        assert self.type in ['system', 'user'] if self.type else True
        
        if self.version:
            if isinstance(self.version, (int, float)):
                self.version = str(self.version)

@dataclass
class Repo:
    name: str
    author: str
    description: str
    version: str
    entrypoint: str
    type: str
    url: str
    method: str
    directory: str

    # Repo manager specific
    pkg_name: Optional[str] = None
    installed = False
    installed_version: Optional[str] = None

    def __init__(self, **kwargs):
        # Get the names of the fields that are defined in the dataclass
        valid_fields = {f.name for f in fields(self)}

        # Iterate over the kwargs
        for key, value in kwargs.items():
            # If the key is not a field of the Repo class, ignore it
            if key not in valid_fields:
                continue
            # Otherwise, set the attribute
            setattr(self, key, value)
        
        self.__post_init__()

    def __post_init__(self):
        self._generate_pkg_name()
        self._set_installed_flag()
        if isinstance(self.version, (int, float)):
            self.version = str(self.version)

        if self.installed:
            self._set_installed_version()

    def _set_installed_flag(self):
        assert self.pkg_name
        if not (
            (Path(self.pkg_name) / EXT_META).exists()
        and (Path(self.pkg_name) / EXT_MAIN).exists()
        ):
            return

        self.installed = True
    
    def _set_installed_version(self):
        assert self.installed
        assert self.pkg_name
        with open(Path(self.pkg_name) / EXT_META, 'r') as f:
            r_json = json.load(f)
        metadata = Metadata(**r_json)
        self.installed_version = metadata.version


    def _generate_pkg_name(self):
        url_path = urllib.parse.urlparse(self.url).path
        url_path = url_path.removesuffix('/')
        pkg_name = self.directory if self.directory.startswith("xExtension-") else url_path.split('/')[-1].split('.')[0]
        assert pkg_name and pkg_name != "."
        self.pkg_name = pkg_name

def read_pkg_repos(pkg_name_fillter = "") -> List[Repo]:
    """
    Read the extensions.json file and return a list of Repo objects

    Args:
        pkg_name_fillter (str): If provided, only return the Repo object with the given pkg_name
    """
    assert os.path.exists('extensions.json'), "extensions.json not found, please run update first"
    with open('extensions.json', 'r') as f:
        r_json = json.load(f)
    assert r_json['version'] == 0.1
    repos = [Repo(**repo) for repo in r_json['extensions']]
    if pkg_name_fillter:
        repos = [repo for repo in repos if repo.pkg_name == pkg_name_fillter]
    assert repos, "No repo(s) found"
    return repos

def read_local_meta(ext_dir: Path) -> Metadata:
    with open(ext_dir / EXT_META, 'r') as f:
        r_json = json.load(f)
    metadata = Metadata(**r_json)
    return metadata

def get_installed_exts() -> List[Metadata]:
    installed_metas = []
    for dir in os.listdir():
        if not os.path.isdir(dir):
            continue
        if not (Path(dir) / EXT_META).exists():
            continue
        installed_meta = read_local_meta(Path(dir))
        installed_metas.append(installed_meta)
    return installed_metas

def update():
    print("Updating extensions.json")
    r = rq.get('https://raw.githubusercontent.com/FreshRSS/Extensions/master/extensions.json')
    r.raise_for_status()
    r.json()
    with open('extensions.json', 'wb') as f:
        f.write(r.content)
    print("extensions.json updated")


def list_repos(verbose: bool = False):
    pkg_repos = read_pkg_repos()
    updates: List[Repo] = []
    for repo in pkg_repos:
        update_avail = repo.installed and repo.installed_version != repo.version
        if update_avail:
            updates.append(repo)

        if verbose:
            print(repo) 
        else:
            print(repo.pkg_name,
                  repo.version,
                  "<official>"  if repo.url.lower().startswith("https://github.com/FreshRSS/Extensions".lower()) else '"community"',
                  f'[[{repo.installed_version} installed]]' if repo.installed else '')
    print()
    print(f"{len(updates)} updates available:")
    [print(f'\t{repo.pkg_name} {repo.installed_version} -> {repo.version}') for repo in updates]
    installed_exts = get_installed_exts()
    print(f"{len(installed_exts)} installed extensions.")
    local_only_exts = [ext for ext in installed_exts if not any(ext.entrypoint == repo.entrypoint for repo in pkg_repos)]
    print(f"{len(local_only_exts)} Local only extensions:")
    [print(f"\t{ext.name}") for ext in local_only_exts]


def show_repo(pkg_name: str):
    pkg_repos = read_pkg_repos()
    for repo in pkg_repos:
        if repo.pkg_name == pkg_name:
            print(repo)
            return
    print("Repo not found")

def install(pkg_name: str, exist_ok: bool = False):
    if not exist_ok:
        assert not (Path(pkg_name) / EXT_META).exists(), f"{pkg_name} already installed"

    pkg_repo = read_pkg_repos(pkg_name)[0]
    print(f"Installing {pkg_repo.name} {pkg_repo.version}")
    assert pkg_repo.method == "git", "Only git repos are supported"

    # git clone --quiet --single-branch --depth 1 --no-tags {$gitRepository} {$tempFolder}/{$key}

    if not (PKG_TMP_DIR / pkg_name / ".git" / "config").exists():
        r = subprocess.run(['git', 'clone', pkg_repo.url, PKG_TMP_DIR / pkg_name])
        r.check_returncode()
        print(f"Git repo cloned to {PKG_TMP_DIR / pkg_name}")
    else:
        print(f"Repo already cloned to {PKG_TMP_DIR / pkg_name}, fetching latest")
        r = subprocess.run(['git', 'fetch'], cwd=PKG_TMP_DIR / pkg_name)
        r.check_returncode()
        print("Latest fetched")
        
    checkout_success = False
    for branch in [f'v{pkg_repo.version}', f'{pkg_repo.version}', f'origin/{pkg_repo.version}', f'origin/v{pkg_repo.version}', 'origin/HEAD']:
        print(f"Trying to checkout {branch}")
        r = subprocess.run(['git', 'checkout', '--quiet', '--force', branch], cwd=PKG_TMP_DIR / pkg_name)
        if r.returncode == 0:
            checkout_success = True
            print(f"Checked out {branch}")
            break
    
    assert checkout_success, f"Failed to checkout {pkg_repo.version}"
    cached_meta = read_local_meta(PKG_TMP_DIR / pkg_name / pkg_repo.directory)
    print(cached_meta)


    print(f"Copying to {pkg_name}")
    shutil.copytree(PKG_TMP_DIR / pkg_name / pkg_repo.directory, pkg_name, dirs_exist_ok=True)
    print(f"Copied to {pkg_name}")
    meta = read_local_meta(Path(pkg_name))
    print("Installed:")
    print(meta)
    set_permissions(Path(pkg_name))


def chown_r(path: Path, user: str, group: str, use_sudo: bool = True):
    cmd = ['chown', '-R', f'{user}:{group}', path]
    if use_sudo:
        cmd = ['sudo', *cmd]
    r = subprocess.run(cmd, capture_output=True, text=True)
    return r.returncode

def whoami():
    r = subprocess.run(['whoami'], capture_output=True, text=True)
    return r.stdout.strip()

def sudo_available():
    r = subprocess.run(['sudo', '-n', 'whoami'])
    return r.returncode == 0

def is_common_web_server_user():
    user = whoami()
    return user in ['www-data', 'httpd', 'www', 'apache']

@dataclass
class Args:
    action: str
    pkg_name: Optional[str] = None
    verbose: bool = False

def main_parse_args():
    parser = argparse.ArgumentParser(description='FreshRSS extension manager')
    parser.add_argument('action', type=str, choices=['install', 'update', 'upgrade', 'show', 'list', 'clean'], help='Action to perform')
    parser.add_argument('pkg_name', type=str, nargs='?', help='Unique name of the extension')
    parser.add_argument('-v', action='store_true', help='Verbose output', dest='verbose')

    return Args(**vars(parser.parse_args()))

def set_permissions(path: Path):
    is_root = os.geteuid() == 0
    user = whoami()
    print(f"Running as {user} ")
    is_web_user = is_common_web_server_user()
    if is_web_user:
        print("Looks like you are running as http server user, that's great! No need to change permissions")
        return

    is_sudo = sudo_available()
    if is_sudo or is_root:
        print("trying to change permissions")
        for user_ in COMMON_WEB_SERVER_USERS:
            print(f"Trying to change permissions to {user_}")
            if not is_root and is_sudo:
                print('using sude')
            r = chown_r(path, user, user, use_sudo=not is_root)
            if r == 0:
                print(f"Permissions changed to {user_}:{user_}")
                return
            
        print("Failed to change permissions")

    print("Please run as http server user or with sudo")
    print("Or change the permissions manually")

def main():

    args = main_parse_args()

    # check pwd
    assert Path.cwd().name == "extensions" or Path('DEBUG').exists(), "Please run from the extensions directory"

    if args.action == 'update':
        update()
        return
    elif args.action == 'list':
        list_repos(verbose=args.verbose)
        return
    elif args.action == 'show':
        assert args.pkg_name, "pkg_name is required for show action"
        show_repo(args.pkg_name)
    elif args.action == 'install':
        assert args.pkg_name, "pkg_name is required for install action"
        if args.pkg_name == 'all':
            for repo in [repo for repo in read_pkg_repos() if not repo.installed]:
                assert repo.pkg_name
                install(repo.pkg_name, exist_ok=False)
            print("All extensions installed")
        else:
            install(args.pkg_name, exist_ok=False)
    elif args.action == 'upgrade':
        if not args.pkg_name:
            for repo in read_pkg_repos():
                if repo.installed and repo.installed_version != repo.version:
                    print(f"Upgrading {repo.pkg_name}, {repo.installed_version} -> {repo.version}")
                    assert repo.pkg_name
                    install(repo.pkg_name, exist_ok=True)
        else:
            assert args.pkg_name in os.listdir(), f"{args.pkg_name} not installed"
            install(args.pkg_name, exist_ok=True)
    elif args.action == 'clean':
        if PKG_TMP_DIR.exists():
            print(f"Cleaning {PKG_TMP_DIR} cache")
            shutil.rmtree(PKG_TMP_DIR)
            print("cache cleaned")
        else:
            print(f"{PKG_TMP_DIR} does not exist, nothing to clean")
    else:
        print("Invalid action")


if __name__ == '__main__':
    main()
