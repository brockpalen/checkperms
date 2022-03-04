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


# Custom Log Formater
# https://stackoverflow.com/questions/1343227/can-pythons-logging-format-be-modified-depending-on-the-message-log-level
class MyFormatter(logging.Formatter):
    """Don't leave it up to the user to corrrectly prefix log messages for log watcher to pick up."""

    err_fmt = "%(module)s AUTOFS_PERMISSION_ERROR: %(msg)s"
    warn_fmt = "%(module)s AUTOFS_PERMISSION_WARNING: %(msg)s"
    info_fmt = "%(module)s AUTOFS_PERMISSION_INFO: %(msg)s"
    dbg_fmt = "%(module)s AUTOFS_PERMISSION_DEBUG: %(msg)s"

    def __init__(self):
        super().__init__(fmt="%(levelno)d: %(msg)s", datefmt=None, style="%")

    def format(self, record):

        # Save the original format configured by the user
        # when the logger formatter was instantiated
        format_orig = self._style._fmt

        # Replace the original format with one customized by logging level
        if record.levelno == logging.DEBUG:
            self._style._fmt = MyFormatter.dbg_fmt

        elif record.levelno == logging.INFO:
            self._style._fmt = MyFormatter.info_fmt

        elif record.levelno == logging.WARNING:
            self._style._fmt = MyFormatter.warn_fmt

        elif record.levelno == (logging.ERROR or logging.CRITICAL):
            self._style._fmt = MyFormatter.err_fmt

        else:  # Unknown log level
            self._style._fmt = MyFormatter.err_fmt

        # Call the original formatter class to do the grunt work
        result = logging.Formatter.format(self, record)

        # Restore the original format configured by the user
        self._style._fmt = format_orig

        return result


parser = argparse.ArgumentParser(
    description="""
checkperms is for warning/notifying if directories have world permission bits set of any kind

AUTOFS_PERMISSION_DEBUG    Extra Debug information
AUTOFS_PERMISSION_INFO     Information on current state
AUTOFS_PERMISSION_WARNING  Entry defined in autofs but server not exporting
AUTOFS_PERMISSION_ERROR    User has world permission bits set

INFO messages are always logged.  This allows for knowing _when_ an export become to permissive.

It is on the admin to setup a log handler to raise alerts on ERROR of permissive access.

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
parser.add_argument(
    "--fix-list",
    help="Path to save a list of paths that can be fixed by simple POSIX permissions",
    default=False,
)
parser.add_argument(
    "--allow-obscurity",
    help="Don't raise ERROR when using posix execute bit to allow access but not list folders eg o+x but o-r",
    action="store_true",
)

args = parser.parse_args()

fmt = MyFormatter()
# setup log interface and setup syslog
logger = logging.getLogger(__name__)
# set default level for all handlers
logger.setLevel(logging.DEBUG)


# stream / stderr handler used for all cases
st_handler = logging.StreamHandler()
st_handler.setFormatter(fmt)

if args.debug:
    # debug requsted
    st_handler.setLevel(logging.DEBUG)
else:
    # syslog handler used production run only
    sl_handler = logging.handlers.SysLogHandler(address="/dev/log")
    sl_handler.setFormatter(fmt)
    sl_handler.setLevel(logging.INFO)
    logger.addHandler(sl_handler)

    # set stream / stderr handler level
    st_handler.setLevel(logging.CRITICAL)

logger.addHandler(st_handler)


class cd:
    """Context manager for changing the current working directory.

    Borrowed from https://stackoverflow.com/questions/431684/equivalent-of-shell-cd-command-to-change-the-working-directory
    """

    def __init__(self, newPath):
        self.newPath = os.path.expanduser(newPath)

    def __enter__(self):
        self.savedPath = os.getcwd()
        os.chdir(self.newPath)

    def __exit__(self, etype, value, traceback):
        os.chdir(self.savedPath)


def any_world_access(st):
    """ Check if any of the world permission bits are set """
    # https://docs.python.org/3/library/stat.html
    return bool(st.st_mode & stat.S_IRWXO)


def posix_issue(st, fullpath, fix_list=None):
    """Log and optionally writeout fixes for posix permissions."""
    # some world bits are set log it
    logger.error(f"{fullpath} Permissions: {stat.filemode(st.st_mode)}")
    if fix_list:
        with open(fix_list, "a+") as fl:
            fl.write(f"chmod o-rwx {str(fullpath)}\n")


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


def posix_or_acl(st, fullpath, fix_list=None):
    """Check if permissions was granted by open Unix/POSIX permisions or some other reason

    Params:
        st: stat  os.stat object
        fullpath: (path)  Path being checked
        fix_list: (path) Default: False,  write to path if --fix-list given
    """
    if any_world_access(st):
        posix_issue(st, fullpath, fix_list)
    elif items:
        #  means we were able to list items in path but did not have world permissions set
        #  This means permissions are granted via ACL or other method than POSIX permissions eg AFS
        logger.error(
            f"{fullpath} allowed access without posix permisions: {stat.filemode(st.st_mode)}"
        )


####  MAIN  ####
if __name__ == "__main__":
    # check that option given is a directory
    path = Path(args.path)
    if not path.is_dir():
        logger.critical(f"{path} is not a directory exiting")
        sys.exit(-2)

    # if --fix-list delete if log exists
    if args.fix_list:
        fix_list = Path(args.fix_list)
        if fix_list.is_file():
            logger.debug(f"Prior fix-list found {fix_list} removing")
            fix_list.unlink()
    else:
        fix_list = None

    # walk top level directory itterating over ever directory
    for mount in next(os.walk(path))[1]:
        fullpath = path / mount
        logger.debug(f"Checking: {fullpath}")

        # trigger automount by stepping into the top level of the directory
        try:
            # grab metadata on the path for permissions
            st = os.stat(fullpath)
            logger.debug(st)

            # try and list items in the directory if not it will raise an PermissionError
            items = os.listdir(fullpath)

            # beyond this location we were able to list the directory

            # check if path is in ignore list
            if in_ignore_list(mount, args.ignore):
                # found in ignore list skip over rest
                continue

            # If here we can list what's in the directory AND it's not in the ingore list
            # why can we and log it
            posix_or_acl(st, fullpath, fix_list=fix_list)

        except PermissionError:
            # GOOD we cannot access this path
            logger.info(f"{fullpath} Permissions: {stat.filemode(st.st_mode)}")

            # while we can't list check for obsurity issues, eg POSIX permission for X bit only.
            # allows to cd but not list. A clever user could guess file/folder names and copy out data
            try:
                with cd(fullpath):
                    # if we are here we could cd into the folder but not list it's contents
                    if not args.allow_obscurity:
                        posix_issue(st, fullpath, fix_list)
            except PermissionError:
                # expected to have permission issue again let slide cannot cd into location
                pass

        except FileNotFoundError:
            # BAD when defined in /etc/autofs.d/  but not currently exported to host or server down
            logger.warning(
                f"{fullpath} Not exported but in autofs config or server not responding"
            )
        except Exception:
            # BAD something else happened and that's unexpected/bad
            logger.critical(f"Unknown Error", exc_info=True)
            sys.exit(-1)
