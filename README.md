# Checkperms

Used to raise awareness of any mounts where users may have changed their world permissoins to over epxose data.
Checkperms will check every directory in a given path step into it to tigger autofs if present and send to syslog 

All log messages are prefixed so they can be easily picked up by logwatch and sent to pager systems etc.

```
AUTOFS_PERMISSION_INFO     Debugging information
AUTOFS_PERMISSION_WARNING  Entry defined in autofs but server not exporting to that system or not responding
AUTOFS_PERMISSION_ERROR    User has world permission bits set
```

## Example Log Messages

```
Aug 27 22:08:58 gl-build journal: checkperms AUTOFS_PERMISSION_ERROR: /nfs/autofs/topermissive Permissions: dr-xr-xr-x
Aug 27 22:08:58 gl-build journal: checkperms AUTOFS_PERMISSION_INFO: /nfs/autofs/correctexport Permissions: drwxrws---
Aug 27 22:11:43 gl-build journal: checkperms AUTOFS_PERMISSION_WARNING: /nfs/autofs/brokenexport Not exported but in autofs config or server not responding
```

## Usage


Run printing nothing to stdout/stderr all information to syslog

```
python3 checkperms.py /nfs/autofs
```

Run including extra debug information including all messages to stderr

```
python3 checkperms.py --debug /nfs/autofs
```

## Ignoring specific mounts

You may have mounts in the same location that should have world permissions such as public shared data, reference genomes etc you can ignore them

```
python3 checkperms.py --ignore public,ref-genomes /nfs/autofs
```

## Allow users to opt out of the check

Not recomended for high sensitivity environments.  The option `--user
-accepts-risk` will check for the existance of an `accept_risk` file in the root of
the path being checked. If found further checks are skipped. 

This check allows the user to 'opt into' that they know what they are doing.

## Security by Obscurity

By default the checkperms will also try to `cd` into the folder. This is a
check for folders with execute but no read bit.  This is often used to give
another user access to a specific path but not allow them to list the path.
This is security by obscurity because with enough effort or clever guessing any
user has access to data in the folder even if they can't list it.

To disable treating the ability to `cd` but not list it's contents as an error
pass `--allow-obscurity`

```
checkperms --debug /home

AUTOFS_PERMISSION_DEBUG: Checking: /home/user
AUTOFS_PERMISSION_INFO: /home/user Permissions: drwxr-x--x
AUTOFS_PERMISSION_ERROR: /home/user Permissions: drwxr-x--x

checkperms --allow-obscurity --debug /home

AUTOFS_PERMISSION_DEBUG: Checking: /home/user
AUTOFS_PERMISSION_INFO: /home/user Permissions: drwxr-x--x
```

## Save list of paths and commands that can fix with chmod

```
python3 checkperms.py --fix-list /var/spool/fix-list /nfs/autofs

#fix-list is
chmod o-rwx <path>
```

This only saves for paths that can step into because of `other` permissions.  This is mostly used to follow up with a script to `chmod` automatically.


## Limitations

The tool can only check mounts that are static defined in autofs or not using autofs at all. 
It will not work with automount wildcard matches 

Eg. `*    server:/export/home/&`
