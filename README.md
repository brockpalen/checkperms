# Checkperms

Used to raise awareness of any mounts where users may have changed their world permissoins to over epxose data.
Checkperms will check every directory in a given path step into it to tigger autofs if present and send to syslog 

All log messages are prefixed so they can be easily picked up by logwatch and sent to pager systems etc.

```
AUTOFS_PERMISSION_INFO     Debugging information
AUTOFS_PERMISSION_WARNING  Entry defined in autofs but server not exporting to that system or not responding
AUTOFS_PERMISSION_ERROR    User has world permission bits set
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

## Limitations

The tool can only check mounts that are staticly defined in autofs or not using autofs at all. 
It will not work with automount wildcard matches 

Eg. `*    server:/export/home/&`
