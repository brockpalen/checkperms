#!python3

# Brock Palen 8/2020
# brockp@umich.edu

import argparse
import logging
import logging.handlers
import os
import stat
import sys
from pathlib import Path

parser = argparse.ArgumentParser(
    description="""
checkperms is for warning/notifying if directories have world permission bits set of any kind

AUTOFS_PERMISSION_INFO     Debugging information
AUTOFS_PERMISSION_WARNING  Entry defined in autofs but server not exporting
AUTOFS_PERMISSION_ERROR    User has world permission bits set

Eg: python3 checkperms.py --debug /nfs/turbo
"""
)

parser.add_argument("path", help="Path to scan", type=str)
parser.add_argument(
    "-d",
    "--debug",
    help="Print extra debugging and print output to stderr",
    action="store_true",
)
parser.add_argument(
    "--ignore",
    help="comma list of mounts to ignore. Used for common shared data eg med-genomes",
    type=str,
    default=False,
)

args = parser.parse_args()

# setup log interface and setup syslog
logger = logging.getLogger(__name__)
# set default level for all handlers
logger.setLevel(logging.DEBUG)

# syslog handler used for all cases
handler = logging.handlers.SysLogHandler(address="/dev/log")
handler.setLevel(logging.INFO)
logger.addHandler(handler)

if args.debug:
    # stderr handler enabled if --debug
    handler = logging.StreamHandler()
    handler.setLevel(logging.DEBUG)
    logger.addHandler(handler)


def any_world_access(st):
    """ Check if any of the world permission bits are set """
    # https://docs.python.org/3/library/stat.html
    return bool(st.st_mode & stat.S_IRWXO)


def in_ignore_list(mount, ignore=False):
    """Check if mount name matches any in the ignore list"""
    if not ignore:
        # no ignores found skip
        return False

    ignore_list = ignore.split(",")
    if mount in ignore_list:
        logger.info(f"AUTOFS_PERMISSION_INFO {mount} in ignore list skipping check")
        return True
    else:
        return False


####  MAIN  ####

# check that option given is a directory
path = Path(args.path)
if not path.is_dir():
    logger.critical(f"AUTOFS_PERMISSION_ERROR {path} is not a directory exiting")
    sys.exit(-2)

# walk top level directory itterating over ever directory
for mount in next(os.walk(path))[1]:
    fullpath = path / mount
    logger.debug(f"Checking: {fullpath}")

    # check if path is in ignore list
    if in_ignore_list(mount, args.ignore):
        # found in ignore list skip over rest
        continue

    # trigger automount by stepping into the top level of the directory
    try:
        items = os.listdir(fullpath)
    except PermissionError:
        # catch the permission denied Exception and supress
        pass
    except FileNotFoundError:
        # when defined in /etc/autofs.d/  but not currently exported to host or server down
        logger.warning(
            f"AUTOFS_PERMISSION_WARNING {fullpath} Not exported but in autofs config or server not responding"
        )

    # grab metadata on the path for permissions
    st = os.stat(fullpath)
    logger.debug(st)

    if any_world_access(st):
        # some world bits are set log it
        logger.error(
            f"AUTOFS_PERMISSION_ERROR {fullpath} Permissions: {stat.filemode(st.st_mode)}"
        )
    else:
        # no world bits debug only
        logger.info(
            f"AUTOFS_PERMISSION_INFO {fullpath} Permissions: {stat.filemode(st.st_mode)}"
        )
