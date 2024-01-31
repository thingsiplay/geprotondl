# geprotondl

CLI to download latest or manage your GE-Proton for Steam

- Author: Tuncay D.
- Source: [Github](https://github.com/thingsiplay/geprotondl)
- Update Notes: [CHANGES](CHANGES.md)
- License: [MIT License](LICENSE)

![demo](https://raw.githubusercontent.com/thingsiplay/geprotondl/main/demo.mp4)

## Introduction

Did you always wanted to install the newest [GE-Proton from Glorious
Eggroll](https://github.com/GloriousEggroll/proton-ge-custom), but constantly
get confused how to download files with a graphical browser? And you don't like
unpacking files manually? Well, today is your lucky day.  This application can
do all of this and less (wink wink to protonup). A commandline tool for
automating the process to display description and list, check, download,
install or remove GE-Proton packages, while staying in the terminal.

GE-Proton is an alternative to the Valve Proton in Steam. It gets faster
updates and often has additional fixes.

### Features

- supports only GE-Proton from Glorious Eggroll
- install or uninstall a package version
- list local installations
- list available versions from online repository
- display summary description
- automatically verify downloads
- no external dependency on a Python library
- no graphical user interface
- Steam only
- Linux only
- ... and much less!

### Quick Start

```bash
git clone https://github.com/thingsiplay/geprotondl
cd geprotondl
bash suggested_install.sh
geprotondl --help
# And if you have fzf installed, you can also try following command:
geprotondl-fzf
```

## Requirements

This program is written in Python 3.10. No other Python library is required.
Only the standard command *tar* is needed, which is installed at default on all
Linux distributions anyway. The Bash script *geprotondl-fzf.sh* is not part of
the core application and requires [fzf](https://github.com/junegunn/fzf) to
build and show an interactive menu.

## Installation

Download directly from Github repository with:

```bash
git clone https://github.com/thingsiplay/geprotondl
cd geprotondl
```

*geprotondl.py* is the main application. Just copy the script into a folder in
your system `$PATH` and give it the executable bit. You can also rename the
file to remove the extension if you want. There is an optional installer
*suggested_install.sh* script for convenience. It searches for an usable
directory from `$PATH` and copy, rename and set permission of all commands. You
can run the installer with arguments too, so it will only look for those
folders.

```bash
bash suggested_install.sh
```

or

```bash
bash suggested_install.sh "$HOME/my/bin" "$HOME/another/path"
```

Following commands are provided afterwards:

1. `geprotondl`
2. `geprotondl-fzf`

## Usage

When you run the application for the first time, it will download a small
database file from Github containing the links and other information for each
GE-Proton release. This file expires after 1 hour and will be re-downloaded
next time.

Use `$ geprotondl --help` to list all options and their brief descriptions.

### Location of GE-Proton installations

The folder where all versions are downloaded and installed into is searched
each time the program starts. It will lookup for your Steam installation and
use the subfolder "compatibilitytools.d", which is where Steam expects
alternative Proton versions. Or force the usage of a specific folder with
option `-D DIR` or `--dir DIR`.

### Operational Modes

There are 3 distinct main operational modes: *install*, *remove* and *test*

With the option `-i` or `--install` the newest version of GE-Proton will be
looked up and suggested for installation. Combine it with `-l` or `--list` to
choose a specific version from the online repository. A version can be chosen
by typing a number, which corresponds to a specific GE-Proton version in the
list.

```bash
geprotondl --install --list
```

With the option `-r` or `--remove` the oldest version of GE-Proton found on
your system is suggested for uninstall. Combine it with `-l` or `--list` to
choose a specific version from local installations. A version can be chosen by
typing a number, which corresponds to a specific GE-Proton version in the list.

```bash
geprotondl --remove --list
```

Use `-t` or `--test` to check if the newest version is installed on your
system. If it's not, then the tag name of it will be output.

```bash
geprotondl --test
```

This is also helpful to test by combining with `-T NAME` or `--tag NAME` with a
specific version. Option `-b` or `--brief` will change the output from full
tagname to short version number only. However combining with a listing such as
`--list` or `--releases` will always output the selected version.

### Version Listing

To show a list without any user interaction for selection, use the listing
option without an operational mode. To get a list of all local installed
versions, use `-l` or `--list` .

```bash
geprotondl --list
```

And to get a list of all available versions ready for install from repository,
use `-L` or `--releases` .

```bash
geprotondl --releases
```

### Summary Info

Another great option is `-s` or `--summary` to print description and meta
information about the selected GE-Proton version. Note, the program defaults to
the newest online available one, if nothing else is specified or selected.

```bash
geprotondl --summary
```

The summary can be combined with the other options to get information of
specific selected versions in example. And output can be customized to a degree
too; check out `-b` or `--brief` and `-H` or `--human` .

### Frontend Scripts

While these useful scripts are not part of the core application itself, they
are still useful and created for your convenience.

#### geprotondl-fzf.sh

Uses external application `fzf` to build a menu with all available GE-Proton
versions. While browsing the list, the current highlighted entry will show
corresponding summary. The confirmed selection will be prompted for
installation, but if it's already installed, it will ask to remove. Only use
short options with single dash, such as `-f` because long options are currently
not compatible. All options are forwarded to the main program *geprotondl.py*
as well.

## Additional files in use

These files are created by the script or optionally by the user. (Besides the
downloaded and unpacked GE-Proton installations in the "compatibilitytools.d"
folder.)

### created automatically

- `~/.cache/geprotondl/releases.json`: Main database to operate on. This file
is downloaded from
[Github API](https://api.github.com/repos/GloriousEggroll/proton-ge-custom/releases)
on start of application and will expire after 1 hour. This is cached, so a
re-download won't slow down with every usage of the program in short periods.
Github has a limit how often the database can be accessed per hour. A
re-download is required in order to detect any new available version of
GE-Proton.

### created automatically only by geprotondl-fzf.sh

- `~/.cache/geprotondl/*.summary`: These are just text files and contain output
of the `--summary` option for each GE-Proton version. This helps with the
performance when scrolling through the dynamically created menu, as the summary
is loaded every time the current selection focus changes.

### temporary files (deleted automatically)

The program creates temporary folder to save downloads into. These are deleted
after the job is done. The exact folders are determined by Python and the
system. On my Archlinux based system they are found under `/tmp` and consist of
random characters such as `/tmp/tmpz4zmi290/` .
