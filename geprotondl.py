#!/usr/bin/env python3

from __future__ import annotations

import sys
import select
import os
import time
import argparse
import logging
import shutil
import subprocess
import re
import json
import datetime
import hashlib

from datetime import timedelta
from itertools import islice
from pathlib import Path, PosixPath
from tempfile import TemporaryDirectory
from urllib.error import ContentTooShortError
from urllib.error import URLError, HTTPError
from urllib import request
from urllib.parse import urlparse, ParseResult

from enum import Enum
from typing import Dict, Any, List, Tuple, Iterable

# TypeAlias
Logger = logging.Logger
# Note: Following Aliases are defined below the class, as they make use of it.
# That has the consequence of them being scattered throughout the file.
#   DatabaseEntryStatus, because of GithubDatabaseEntry and FinishStatus
#   LocalEntry, actually just leave it together with LocalEntryStatus
#   LocalEntryStatus, because of File and FinishStatus
#   GeProtonList, because of File


class FinishStatus(Enum):
    SUCCESS = True
    FAILURE = False
    UNKNOWN = None


class Time(datetime.datetime):
    def __new__(cls, *args: Any, **kwargs: Any) -> Any:
        return datetime.datetime.__new__(cls, *args, **kwargs)

    # Calculate difference of now to a datetime. Output is a timedelta format,
    # but if human_readable is enabled, then output is a string with describing
    # words attached to the number of days.

    # Calculates time difference from now to it's current date value. If
    # current value is the future, then output is in negative numbers. An
    # output is 0, if it was not successful.
    @property
    def ago(self) -> timedelta:
        try:
            now = datetime.datetime.now()
            diff: timedelta = now - self
        except (OSError, OverflowError, ZeroDivisionError):
            return timedelta()
        if diff:
            return diff
        else:
            return timedelta()

    # Number of seconds past as an integer.
    @property
    def seconds_ago(self) -> int:
        return int(self.ago.total_seconds())

    # Calculates number of days difference from now to it's current date
    # value. Output is a human readable string format with describing words
    # included.
    @property
    def days_ago(self) -> str:
        diff = self.ago
        if not diff:
            return ""
        days = diff.days
        if days == 0:
            return "today"
        elif days == 1:
            return "yesterday"
        elif days > 0:
            return f"{abs(days)} days ago"
        elif days < 0:
            return f"{abs(days)} days ahead"
        else:
            return ""


# NOTE: This workaround was required for Python 3.11 and prior. Since
#       Python 3.12 __new__() and __init__() are replaced with below __init__()
#
# class File(PosixPath):
#     def __new__(cls, *args: Any, **kwargs: Any) -> Any:
#         return cls._load_parts(args).expanduser().resolve()  # type: ignore
#
#     def __init__(self, source: str | Path, *args: Any) -> None:
#         super().__init__()
#         self.__source = Path(source)
#
class File(PosixPath):
    def __init__(self, source: str | Path, *args: Any) -> None:
        self.__source = Path(source)
        super().__init__(Path(source, *args).expanduser().resolve())

    @property
    def source(self) -> Path:
        return self.__source

    @property
    def modified(self) -> Time:
        return Time.fromtimestamp(os.path.getmtime(self))

    @property
    def changed(self) -> Time:
        return Time.fromtimestamp(os.path.getctime(self))

    @property
    def accessed(self) -> Time:
        return Time.fromtimestamp(os.path.getatime(self))

    # Calculate sha512 hash of self file and compare result to the
    # checksum found in given file. Return True if identical.
    def verify_sha512(self, file: File, buffer_size: int = 4096) -> bool:
        compare_hash: str = file.read_text().split(" ")[0]
        self_hash: str = ""
        self_checksum = hashlib.sha512()
        with open(self.as_posix(), "rb") as f:
            for chunk in iter(lambda: f.read(buffer_size), b""):
                self_checksum.update(chunk)
            self_hash = self_checksum.hexdigest()
        return self_hash == compare_hash


# TypeAlias
GeProtonListing = Dict[str, File]


class Interface:
    def __init__(self, logger: Logger | None = None, be_quiet: bool = False) -> None:
        self._be_quiet: bool
        self.assume_yes: bool
        self.timeout: int
        self.max_entries: int
        self.compact_view: bool
        self.human_readable: bool
        self.log: Logger
        if logger:
            self.log = logger
        else:
            self._be_quiet = be_quiet
            self.assume_yes = False
            self.timeout = 0
            self.max_entries = 9
            self.compact_view = False
            self.human_readable = False
            self.log = self.new_logger()
            if self._be_quiet:
                self.set_logger_level(logging.CRITICAL)
            else:
                self.set_logger_level(logging.INFO)

    # Simple setup of a message logging functionality. Intended to be used in
    # any function or class.
    # Logging levels: NOTSET, DEBUG, INFO, WARNING, ERROR, CRITICAL
    def new_logger(self, name: str = __name__, level: int = logging.INFO) -> Logger:
        self.log = logging.getLogger(name)
        logging.basicConfig(format="%(message)s")
        self.set_logger_level(level)
        return self.log

    def set_logger_level(self, level: int) -> int:
        self.log.setLevel(level)
        return level

    def print(self, message: str) -> str | None:
        if not self._be_quiet:
            print(message)
            return message
        else:
            return None

    def readline_from_stdin(
        self, prompt: str = "", timeout: int | None = None
    ) -> str | None:
        if not isinstance(prompt, str):
            e = (
                "Value of prompt has wrong type, expected optional str: "
                f"{type(prompt)}"
            )
            raise TypeError(e)
        elif not isinstance(timeout, int | None):
            e = (
                "Value of timeout has wrong type, expected optional int: "
                f"{type(timeout)}"
            )
            raise TypeError(e)
        elif prompt:
            sys.stderr.write(prompt)
            sys.stderr.flush()
        if timeout is None:
            timeout = self.timeout
        i, _, _ = select.select([sys.stdin], [], [], self.timeout)
        if i:
            return sys.stdin.readline().strip()
        else:
            sys.stderr.write("\n")
            sys.stderr.flush()
            return None

    def ask_number(self, question: str | None = None) -> Tuple[int, FinishStatus]:
        if question is None:
            question = "Enter a number:"
        self.print(question)
        answer = self.readline_from_stdin("$ ")
        if answer is None:
            self.log.info("Time up! Maybe next time.")
            return 0, FinishStatus.UNKNOWN
        else:
            try:
                return int(answer), FinishStatus.SUCCESS
            except ValueError:
                self.log.error("Input must be a number to proceed.")
                return 0, FinishStatus.FAILURE
            else:
                return 0, FinishStatus.FAILURE

    def ask_to_proceed(self, question: str | None = None) -> bool:
        if question is None:
            question = "Continue? (Y)es or (N)o:"
        self.print(question)
        if self.assume_yes:
            self.print("y")
            return True
        else:
            answer = self.readline_from_stdin("$ ")
            if answer is None:
                self.log.info("Time up! Maybe next time.")
                return False
            elif answer[0:1].lower() == "y":
                return True
            else:
                return False
        return False


class GithubDatabaseEntry:
    def __init__(self, data: Any, interface: Interface) -> None:
        self.interface = interface
        self.data = data

    # Convert the data into an alternative and flat structure, partially
    # changed keys and interpreted content.
    def parse(self) -> Dict[str, Any]:
        view: Dict[str, Any] = {}
        try:
            view["json_url"] = urlparse(self.data["url"].strip())
            view["html_url"] = urlparse(self.data["html_url"].strip())
            view["author"] = self.data["author"]["login"].strip()
            view["title"] = self.data["name"].strip()
            view["tag_name"] = self.data["tag_name"].strip()
            pub = self.data["published_at"].strip().replace("Z", "")
            view["pub"] = Time.fromisoformat(pub)
            created = self.data["created_at"].strip().replace("Z", "")
            view["date"] = Time.fromisoformat(created)
            desc = self.data["body".strip()]
            view["desc"] = "\n".join(desc.splitlines())
            # Default values for optional assets data.
            view["download_url"] = urlparse("http://")
            view["filename"] = ""
            view["size"] = 0
            for asset in self.data["assets"]:
                content_type: str = asset["content_type"].strip()
                is_archive: bool = ".tar.gz" in asset["name"].strip()
                if content_type == "application/gzip" or is_archive:
                    dl = asset["browser_download_url"].strip()
                    view["download_url"] = urlparse(dl)
                    view["filename"] = asset["name"].strip()
                    view["size"] = int(asset["size"])
                elif content_type in [
                    "application/octet-stream",
                    "binary/octet-stream",
                ]:
                    dl = asset["browser_download_url"].strip()
                    view["checksum_download_url"] = urlparse(dl)
                    view["checksum_filename"] = asset["name"].strip()
                    view["checksum_size"] = int(asset["size"])
        except (KeyError, ValueError, OverflowError, OSError, TypeError):
            self.interface.log.error("Could not parse data from Github API.")
            return {}
        else:
            return view

    # Build a string out of most important meta information for presentation to
    # the user. It has options to convert some values to a human readable
    # format. And it is able to shorten the output to be more compact.
    def summary(self, sep: str = "\n", pre: str = " o ") -> str:
        view = self.parse()
        if not view:
            return ""
        title = view.get("title", "")
        desc = view.get("desc", "")
        tag = view.get("tag_name", "")
        file = view.get("download_url", "").geturl()
        html = view.get("html_url", "").geturl()
        fmt = ""
        if self.interface.human_readable:
            date = view.get("date", "").days_ago
            size_int = int(view.get("size", 0))
            size = str(round(size_int / 1024 / 1024)) + " MB"
        else:
            pre = ""
            date = str(view.get("date", ""))
            size = str(view.get("size", 0)) + " Bytes"
        compact = self.interface.compact_view
        if compact:
            fmt = " "
            desc = self.excerpt(desc)
            summary = (
                f"{pre}{title}{sep}"
                f"{pre}{desc}{sep}"
                f"{pre}Tag:{fmt}{tag}{sep}"
                f"{pre}Date:{fmt}{date}{sep}"
                f"{pre}Size:{fmt}{size}"
            )
        else:
            if self.interface.human_readable:
                fmt = "\n\t"
                title += f"{sep}"
                desc += f"{sep}"
                file += f"{sep}"
            else:
                fmt = "\t"
            summary = (
                f"{pre}{title}{sep}"
                f"{pre}{desc}{sep}"
                f"{pre}Releases Page:{fmt}{html}{sep}"
                f"{pre}Tag Name:{fmt}{tag}{sep}"
                f"{pre}Publish Date:{fmt}{date}{sep}"
                f"{pre}Download Size:{fmt}{size}{sep}"
                f"{pre}Download File:{fmt}{file}"
            )
        return summary

    # Creates a short one liner string from a longer text.
    def excerpt(self, text: str, max_length: int = 64) -> str:
        return text[:max_length].replace("\n", " ") + "..."

    # Downloads the archive from download url into a temporary folder. Then
    # unpacks it's content into the given basedir folder.
    def install(self, basedir: File, force: bool) -> FinishStatus:  # noqa:C901
        def cleanup() -> None:
            tempfile.unlink(missing_ok=True)
            temp_checksumfile.unlink(missing_ok=True)
            tempdir.cleanup()
            return None

        view = self.parse()
        if view:
            if view.get("filename", "") == "" or view.get("download_url", "") == "":
                msg = "Installation not possible. No source available."
                self.interface.log.error(msg)
                return FinishStatus.FAILURE
            tag_name: str = view["tag_name"]
            folder: File = basedir / tag_name
            if force:
                if folder.exists():
                    msg = "+-Reinstall"
                else:
                    msg = "+Install"
            else:
                if folder.exists():
                    msg = "Already installed. Operation aborted."
                    self.interface.log.error(msg)
                    return FinishStatus.FAILURE
                else:
                    msg = "+Install"
            msg += f": {tag_name}"
            if not self.interface.compact_view:
                msg += f"\n\t{view['download_url'].geturl()}\n"
            self.interface.log.info(msg)
            if self.interface.ask_to_proceed():
                tempdir = TemporaryDirectory()
                tempfile = File(Path(tempdir.name) / view["filename"])
                if not force:
                    temp_checksumfile = File(
                        Path(tempdir.name) / view["checksum_filename"]
                    )
                self.interface.log.info("Downloading.")
                try:
                    self.download(view["download_url"], tempfile)
                    if force:
                        if GeProtonLocal.is_proton_dir(folder):
                            shutil.rmtree(folder, ignore_errors=False)
                        else:
                            msg = "Can't delete non Proton folder."
                            self.interface.log.error(msg)
                            cleanup()
                            return FinishStatus.FAILURE
                    else:
                        self.download(
                            view["checksum_download_url"],
                            temp_checksumfile,
                            enable_progress_bar=False,
                        )
                except KeyboardInterrupt:
                    self.interface.log.info("Download stopped.")
                    cleanup()
                    return FinishStatus.FAILURE
                except (URLError, HTTPError):
                    msg = "Failed to download. URL or HTTPS request problem."
                    self.interface.log.error(msg)
                    cleanup()
                    return FinishStatus.FAILURE
                if not force and not tempfile.verify_sha512(temp_checksumfile):
                    msg = "Verification of downloaded content failed. Abort."
                    self.interface.log.error(msg)
                    cleanup()
                    return FinishStatus.FAILURE
                self.interface.log.info("Unpacking.")
                try:
                    self.unpack(tempfile, basedir)
                except KeyboardInterrupt:
                    msg = (
                        "Unpacking stopped. GE-Proton folder unfinished, "
                        f"delete manually: {folder}"
                    )
                    self.interface.log.error(msg)
                    cleanup()
                    return FinishStatus.FAILURE
                except subprocess.CalledProcessError:
                    msg = (
                        "Unpacking failed. GE-Proton folder maybe "
                        f"incomplete, delete manually: {folder}"
                    )
                    self.interface.log.error(msg)
                    cleanup()
                    return FinishStatus.FAILURE
                cleanup()
                self.interface.log.info("Done")
                return FinishStatus.SUCCESS
            else:
                self.interface.log.info("Operation cancelled.")
                return FinishStatus.FAILURE
        else:
            return FinishStatus.FAILURE
        return FinishStatus.FAILURE

    # Downloads a file from internet to a given file path as destination. Print
    # and update a live progress bar to stderr stream as well.
    def download(
        self, url: ParseResult, file: File, enable_progress_bar: bool = True
    ) -> bool:
        def progress_bar(count: int, blockSize: int, totalSize: int) -> None:
            percent = int(count * blockSize * 100 / totalSize)
            progress = f"\r ...{percent}%"
            sys.stderr.write(progress)
            sys.stderr.flush()
            return None

        try:
            input = url.geturl()
            output = file.as_posix()
            if enable_progress_bar:
                request.urlretrieve(input, output, reporthook=progress_bar)
            else:
                request.urlretrieve(input, output)
        except ContentTooShortError:
            self.interface.log.error("Download incomplete.")
            file.unlink(missing_ok=True)
            return False
        finally:
            request.urlcleanup()
            if enable_progress_bar:
                sys.stderr.write("\n")
                sys.stderr.flush()
        return True

    # Unpack content of an archive into a destination folder.
    def unpack(self, file: File, basedir: File) -> subprocess.CompletedProcess[bytes]:
        command = ["tar"]
        command.append("xf")
        command.append(file.as_posix())
        command.append("--directory")
        command.append(basedir.as_posix())
        return subprocess.run(command, check=True)


# TypeAlias
LocalEntry = Tuple[str, File]
LocalEntryStatus = Tuple[LocalEntry | Tuple[None, None], FinishStatus]
DatabaseEntryStatus = Tuple[GithubDatabaseEntry | None, FinishStatus]


class App:
    author = "Tuncay D."
    name = "geprotondl"
    version = "0.4"
    license = "MIT"

    def __init__(self, options: argparse.Namespace) -> None:
        # As init can't return anything else, this variable is used to indicate
        # it's success status. Only set this variable within init itself.
        self.status: FinishStatus = FinishStatus.UNKNOWN

        def status_fail(result: FinishStatus) -> bool:
            if result == FinishStatus.FAILURE:
                self.status = result
                return True
            else:
                return False

        # Shortcut to return to main() quickly, as with this option in place
        # the program is intended to exit immediately.
        self.show_version: bool = options.version
        if self.show_version:
            return None

        # Used to indicate if the program should print those variables.
        self.show_dir: bool = options.print_dir
        self.show_cache: bool = options.print_cache

        # Following combination of options are not allowed and can cause pain;
        # they are mutually exclusive in the program. For flexibility reason
        # any the type of listing will automatically forced when in install or
        # remove mode respectively.
        self.show_listing: bool
        self.show_releases: bool
        if options.list and options.install:
            self.show_listing = False
            self.show_releases = True
        elif options.releases and options.remove:
            self.show_listing = True
            self.show_releases = False
        else:
            self.show_listing = options.list
            self.show_releases = options.releases
        self.install_mode: bool = options.install
        self.remove_mode: bool = options.remove
        self.show_test_mode: bool = options.test
        self.show_summary: bool = options.summary
        self.force_recreate: bool = options.force

        # interface requires special handling, as it is a central way of input
        # and output to the user. Any other class or function should use this
        # specific instance created here. Otherwise if they have their own
        # instance, the settings wouldn't be shared anymore.
        # Be careful with changing the be_quiet attribute of interface.
        # Because the logger level depends on that variable.
        self.interface = Interface(be_quiet=options.quiet)
        self.interface.timeout = 20
        self.interface.assume_yes = options.yes
        self.interface.compact_view = options.brief
        self.interface.human_readable = options.human
        self.interface.max_entries = self.max_entries(
            options.max, self.install_mode, self.remove_mode
        )

        # This local structure also contains the path to install folder,
        # therefore no need to create a dedicated variable like cache_dir.
        self.local: GeProtonLocal = GeProtonLocal(options.dir, self.interface)
        if not self.basedir_ready():
            return None

        # This folder should be set before load_releases_db(), as the function
        # builds on this variable.
        self.cache_dir: File = options.cache

        # Both load_releases_db and GithubDatabaseEntry should be run AFTER
        # GithubDatabase is executed.
        self.releases: GithubDatabase | None = None
        if status_fail(self.load_releases_db()):
            return None

        # tag_name should be set before active_entry is loaded, which serves
        # as a default if nothing else is selected.
        self.tag_name: str | None = options.tag

        # This structure contains the selected entry, which includes everything
        # needed to show and operate on a GE-Proton database version. It is
        # expected to load in the data with load_active_entry() later in the
        # application, after several preparation is done beforehand.
        self.active_entry: GithubDatabaseEntry | None = None

    # Get limit for number of maximum elements to display.
    def max_entries(
        self, limit: int | None, install_mode: bool, show_releases: bool
    ) -> int:
        if not limit:
            if install_mode or show_releases:
                return 9
            else:
                # Usually there are not many elements, so it is save to set an
                # arbitrarily high value as max.
                return 999
        else:
            return limit

    # Outputs project name and version.
    def print_version(self) -> str:
        msg = f"{self.name} v{self.version}"
        print(msg)
        return msg

    # Outputs path of base installation folder.
    def print_dir(self) -> str:
        msg = self.local.basedir.as_posix()
        if not self.interface.compact_view:
            msg = "dir " + msg
        print(msg)
        return msg

    # Outputs path of cache folder.
    def print_cache(self) -> str:
        msg = self.cache_dir.as_posix()
        if not self.interface.compact_view:
            msg = "cache " + msg
        print(msg)
        return msg

    # Download releases database from Github API to cache folder. Parse it's
    # content and load it up; ready to be used as a db.
    def load_releases_db(self) -> FinishStatus:
        file = self.cache_dir / "releases.json"
        try:
            self.releases = GithubDatabase(file, self.interface, self.force_recreate)
        except (URLError, HTTPError):
            msg = "Failed connection to Github API. URL or HTTPS " "request problem."
            self.interface.log.critical(msg)
            return FinishStatus.FAILURE
        except (KeyError, ValueError):
            msg = "Could not parse data from Github API database."
            self.interface.log.critical(msg)
            return FinishStatus.FAILURE
        if not self.releases.db:
            self.interface.log.critical("Failed to load database.")
            return FinishStatus.FAILURE
        else:
            return FinishStatus.SUCCESS

    # Helper for load_active_entry() to break the complexity down a bit.
    # Not intended to be used by its own.
    def _update_entry_by_index(self, index: int) -> FinishStatus:
        if self.releases is None:
            return FinishStatus.FAILURE
        elif self.install_mode or self.show_releases:
            self.active_entry, status = self.releases.get_by_index(index)
            return status
        elif not self.remove_mode:
            self.active_entry, status = self.releases.get_by_index(index)
            return status
        elif self.local.installs:
            (entry, _), status = self.local.get_by_index(index)
            if entry:
                self.active_entry, status = self.releases.get(entry)
                return status
            else:
                return FinishStatus.FAILURE
        else:
            return FinishStatus.FAILURE

    # Extract a database sub entry by requested tag_name or by index. Defaults
    # to first entry. Save result into active_entry variable.
    def load_active_entry(
        self, entry: GithubDatabaseEntry | str | int | None = None
    ) -> FinishStatus:
        if self.releases is None:
            return FinishStatus.FAILURE
        elif entry is None:
            entry = self.tag_name
        try:
            status = FinishStatus.UNKNOWN
            msg = ""
            match entry:
                case None:
                    status = self._update_entry_by_index(1)
                case int() as index:
                    status = self._update_entry_by_index(index)
                case str() as tag_name:
                    if tag_name and not tag_name.upper().isupper():
                        tag_name = f"GE-Proton{tag_name}"
                    self.active_entry, status = self.releases.get(tag_name)
                    msg = f"Requested tag not found in database: {tag_name}"
                case GithubDatabaseEntry():
                    self.active_entry = entry
                    status = FinishStatus.SUCCESS
                case _:
                    raise TypeError
            if not status == FinishStatus.SUCCESS or self.active_entry is None:
                if not msg:
                    msg = "Couldn't parse database entry."
                raise TypeError(msg)
        except (
            KeyError,
            AttributeError,
            ValueError,
            OverflowError,
            OSError,
            TypeError,
        ) as e:
            self.interface.log.error(e)
            return FinishStatus.FAILURE
        if self.show_summary:
            print(self.active_entry.summary())
        return FinishStatus.SUCCESS

    # Download current selected TAG entry and unpack into install folder.
    def install_entry(self) -> FinishStatus:
        if self.active_entry:
            return self.active_entry.install(self.local.basedir, self.force_recreate)
        else:
            return FinishStatus.FAILURE

    def remove_entry(self) -> FinishStatus:
        if self.active_entry:
            return self.local.uninstall(self.active_entry)
        else:
            return FinishStatus.FAILURE

    def print_test(self) -> FinishStatus:
        if self.active_entry is None:
            return FinishStatus.FAILURE
        view = self.active_entry.parse()
        tag_name = view.get("tag_name", "")
        if self.interface.compact_view:
            tag_name = tag_name.replace("GE-Proton", "")
        if self.show_listing or self.show_releases:
            print(tag_name)
            return FinishStatus.SUCCESS
        elif tag_name not in self.local.installs:
            print(tag_name)
            return FinishStatus.SUCCESS
        return FinishStatus.FAILURE

    def basedir_ready(self) -> bool:
        if not self.local.basedir.is_dir():
            msg = (
                "Install dir could not be created or can't be accessed: "
                f'"{self.local.basedir}"'
            )
            self.interface.log.critical(msg)
            self.status = FinishStatus.FAILURE
            return False
        else:
            return True


class GeProtonLocal:
    def __init__(self, basedir: File, interface: Interface):
        self.interface = interface
        self.basedir: File = basedir
        self.installs: GeProtonListing = {}

        if not self.create_basedir():
            return None
        self.detect_local_installs()

    def create_basedir(self) -> bool:
        try:
            self.basedir.mkdir(parents=True, exist_ok=True)
        except PermissionError:
            return False
        return self.basedir.is_dir()

    # Find all folders in install directory, which are unmistakenly identified
    # as a GE-Proton installation. Update local_installs accordingly with name
    # of the folder as tag_name and associate it's path to it.
    def detect_local_installs(self) -> bool:
        if not self.basedir.exists():
            self.installs = {}
            return False
        local_list: GeProtonListing = {}
        for folder in self.basedir.iterdir():
            if not GeProtonLocal.is_proton_dir(folder):
                continue
            local_list.update(self.parse_version_file(folder))
        if local_list:
            self.installs = dict(sorted(local_list.items()))
            return True
        else:
            self.installs = {}
            return False

    # Get an iterator from the "installs" dictionary, by respecting the max
    # entries.
    @property
    def iter(self) -> Iterable[LocalEntry]:
        return islice(self.installs.items(), self.interface.max_entries)

    # Print a numbered list of all installed GE-Proton. Include additional
    # information to each entry, if option quiet is not set.
    def print_listing(self) -> int:
        msg = ""
        if not self.interface.compact_view:
            msg += "Installed on: \n\t"
        self.interface.print(msg + self.basedir.as_posix())
        if not self.interface.compact_view:
            msg = "\nsorted by oldest release tag  --  shows day of install\n"
            self.interface.print(msg)
        if not self.installs:
            return 0
        index: int = 0
        for index, (name, file) in enumerate(self.iter, 1):
            line = f"{index: 3d}. {name}"
            if not self.interface.compact_view:
                line += "  --  "
                try:
                    changed = (file / "version").changed
                    if self.interface.human_readable:
                        line += changed.days_ago
                    else:
                        line += str(changed.date())
                except FileNotFoundError:
                    index -= 1
                    # At this stage of the program, a missing version file
                    # should never happen. Because only folders with a version
                    # file are added to the list of folders to process.
                    msg = f"version file is missing for: {file.as_posix()}"
                    self.interface.log.error(msg)
            print(line)
        return index

    # Check if given path and it's content is identified as a Proton
    # installation directory.
    @staticmethod
    def is_proton_dir(path: File) -> bool:
        is_proton = (
            "Proton" in path.name
            and path.is_dir()
            and (path / "proton").is_file()
            and (path / "version").is_file()
            and (path / "protonfixes").is_dir()
        )
        return is_proton

    # Read version file and extract it's tag_name and version component.
    def parse_version_file(self, folder: File) -> GeProtonListing:
        pattern = r"(GE-Proton[0-9]+-[0-9]+)"
        version_file = folder / "version"
        with version_file.open(encoding="utf8") as fp:
            # Expected file content format: 1678925217 GE-Proton7-51
            match = re.findall(pattern, fp.read().strip())
            if match:
                return {match[0]: File(folder)}
        return {}

    # Interactive selection of an entry by entering an index number.
    def choose(self, question: str = "Choose") -> LocalEntryStatus:
        index = 0
        if not self.interface.compact_view:
            question = f"\nEnter number to {question.lower()}"
        question += ":"
        index, status = self.interface.ask_number(question)
        if not status == FinishStatus.SUCCESS:
            return (None, None), FinishStatus.FAILURE
        output, status = self.get_by_index(index)
        if output and status == FinishStatus.SUCCESS:
            return output, FinishStatus.SUCCESS
        else:
            return output, FinishStatus.FAILURE

    # Get an entry from detected installs by an index, starting with 1.
    def get_by_index(self, index: int) -> LocalEntryStatus:
        msg: str | None = None
        if not self.installs:
            msg = "Nothing removable available."
        else:
            match index:
                case value if not isinstance(value, int):
                    msg = "Requested input must be an integer."
                case 0:
                    pass
                case value if value < 0:
                    msg = "Requested index is invalid."
                case value if value > len(self.installs):
                    msg = "Requested index is too high."
                case _:
                    try:
                        eslice = islice(self.installs.items(), index - 1, None)
                        return next(eslice), FinishStatus.SUCCESS
                    except StopIteration:
                        msg = "Requested index not found in local installs."
        if msg:
            self.interface.log.error(msg)
        return (None, None), FinishStatus.FAILURE

    # Get an entry from detected installs by a matching tag name.
    def get(self, tag_name: str) -> LocalEntry | Tuple[None, None]:
        for name, path in self.iter:
            if name == tag_name:
                return (name, path)
        return (None, None)

    # Remove the file structure associated with the matching entry in the
    # detected Proton installs folders.
    def uninstall(self, entry: GithubDatabaseEntry) -> FinishStatus:
        view = entry.parse()
        if view:
            _, file = self.get(view.get("tag_name", ""))
            if not file:
                msg = "Could not find file from requested entry."
                self.interface.log.error(msg)
                return FinishStatus.FAILURE
            msg = f"-Remove: {view['tag_name']}"
            if not self.interface.compact_view:
                msg += f"\n\t{file}/\n"
            self.interface.log.info(msg)
            if self.interface.ask_to_proceed():
                if self.delete_folder(file):
                    self.interface.log.info("Done.")
                    return FinishStatus.SUCCESS
                else:
                    self.interface.log.error("Operation failed.")
            else:
                self.interface.log.info("Operation cancelled.")
        return FinishStatus.FAILURE

    # Delete an entire folder structure on the drive. So be careful what files
    # are given over to this function. It will check to make sure its a Proton
    # folder and won't run if shutil is vulnerable. Still always double check
    # before deleting any folder structure.
    def delete_folder(self, path: File) -> bool:
        if not self.is_proton_dir(path):
            msg = (
                f"({path.as_posix()}) is not a Proton directory. Abort "
                "process without deletion."
            )
            self.interface.log.error(msg)
            return False
        elif not shutil.rmtree.avoids_symlink_attacks:
            msg = (
                "shutil.rmtree routine not save against symlink attacks. "
                "Abort process without deletion."
            )
            self.interface.log.error(msg)
            return False
        else:
            try:
                shutil.rmtree(path, ignore_errors=False)
            except (FileNotFoundError, OSError) as e:
                self.interface.log.error(e)
                return False
            else:
                return True


class GithubDatabase:
    def __init__(self, path: File, interface: Interface, force: bool) -> None:
        self.interface = interface
        self.file: File = path
        project = "GloriousEggroll/proton-ge-custom"
        api_url = f"https://api.github.com/repos/{project}/releases"
        self.source: ParseResult = urlparse(api_url)
        self.url: ParseResult = urlparse(f"https://github.com/{project}")
        self.db: List[Any] | None = None
        self.force = force

        self.load_db()

    # Load up the local database file into db variable. Download or update it
    # if necessary.
    def load_db(self) -> bool:
        self.db = None
        self.file.parent.mkdir(parents=True, exist_ok=True)
        if self.force or self.is_expired():
            self.file.unlink(missing_ok=True)
            self.download()
        elif self.file.exists():
            with open(self.file, "r", encoding="utf8") as local_file:
                self.db = json.load(local_file)
        return bool(self.db)

    # Checks if the current downloaded file on the disk requires an update.
    # Standard is 1 hour time period since last download, as the Github API
    # allows only a certain number of connections per hour.
    def is_expired(self, max_age_minutes: int = 60) -> bool:
        if not self.file.exists():
            return True
        try:
            age_seconds = time.time() - os.path.getctime(self.file)
        except Exception:
            return False
        else:
            age_minutes = int(int(age_seconds) / 60)
            return bool(age_minutes > max_age_minutes)

    # Download the database from Github API as cache file and load it as json
    # into the db variable.
    def download(self) -> bool:
        with request.urlopen(url=self.source.geturl()) as online_file:
            self.db = json.load(online_file)
            with open(self.file, "w", encoding="utf8") as cache_file:
                json.dump(self.db, cache_file)
        return self.file.exists()

    # Request an entry from database by matching tag_name.
    def get(self, tag_name: str) -> DatabaseEntryStatus:
        if self.db is None:
            return None, FinishStatus.FAILURE
        for entry in self.db:
            try:
                if tag_name == entry["tag_name"]:
                    return (
                        GithubDatabaseEntry(entry, self.interface),
                        FinishStatus.SUCCESS,
                    )
                    break
            except KeyError:
                continue
        return None, FinishStatus.FAILURE

    # Request an entry from database by index. Numbering begins with 1.
    def get_by_index(self, index: int) -> DatabaseEntryStatus:
        if self.db is None:
            return None, FinishStatus.FAILURE
        elif len(self.db) < index:
            return None, FinishStatus.FAILURE
        for register, entry in enumerate(self.db, 1):
            try:
                if register == index:
                    return (
                        GithubDatabaseEntry(entry, self.interface),
                        FinishStatus.SUCCESS,
                    )
                    break
            except KeyError:
                continue
        return None, FinishStatus.FAILURE

    # Get an iterator over the database entries, by respecting the max entries.
    # This is a convenience function that allows for start using it without
    # check for None.
    @property
    def iter(self) -> Iterable[List[Any]]:
        if self.db:
            return islice(self.db, self.interface.max_entries)
        else:
            return islice([], 0)

    # Print a numbered list of all online available GE-Protoni. Include
    # additional information to each entry, if option quiet is not set.
    def print_listing(self, local_installs: GeProtonListing) -> int:
        msg = ""
        if not self.interface.compact_view:
            msg += "Available from: \n\t"
        self.interface.print(msg + self.url.geturl())
        if not self.interface.compact_view:
            msg = (
                "\nsorted by newest release tag  --  shows day of publish\n"
                "[x] = locally installed\n"
            )
            self.interface.print(msg)
        if not self.db:
            return 0
        index: int = 0
        for index, entry in enumerate(self.iter, 1):
            line = f"{index: 3d}."
            tag_name: str = entry["tag_name"]  # type: ignore
            if not self.interface.compact_view:
                if tag_name in local_installs:
                    line += " [x]"
                else:
                    line += " [ ]"
            line += f" {tag_name}"
            if not self.interface.compact_view:
                line += "  --  "
                pub: str = entry["published_at"]  # type: ignore
                pub_time = Time.fromisoformat(pub.strip().replace("Z", ""))
                if self.interface.human_readable:
                    line += pub_time.days_ago
                else:
                    line += str(pub_time.date())
            print(line)
        return index

    def choose(self, question: str = "Choose") -> DatabaseEntryStatus:
        index = 0
        if not self.interface.compact_view:
            question = f"\nEnter number to {question.lower()}"
        question += ":"
        index, status = self.interface.ask_number(question)
        if not status == FinishStatus.SUCCESS:
            return None, FinishStatus.FAILURE
        output, status = self.get_by_index(index)
        if output and status == FinishStatus.SUCCESS:
            return output, FinishStatus.SUCCESS
        else:
            return output, FinishStatus.FAILURE


# Find root folder of Steam installation. If one is found, return a complete
# File path with the final component of "compatibilitytools.d" added.
def default_install_dir(
    enable_local: bool = True, enable_flatpak: bool = True, enable_snap: bool = True
) -> Tuple[str | None, FinishStatus]:
    roots: List[str] = []
    if enable_local:
        roots += ["~/.local/share/Steam", "~/.steam/root", "~/.steam/steam"]
    if enable_flatpak:
        roots += ["~/.var/app/com.valvesoftware.Steam/data/Steam"]
    if enable_snap:
        roots += ["~/snap/steam/common/.steam/root"]
    for path in roots:
        steam_root: File = File(path)
        if steam_root.is_dir():
            install_dir: Path = Path(steam_root / "compatibilitytools.d")
            return install_dir.as_posix(), FinishStatus.SUCCESS
    return None, FinishStatus.FAILURE


# The amazing handling of arguments.
def parse_arguments(
    argv: list[str] | None = None,
) -> Tuple[argparse.Namespace, FinishStatus]:
    # Will be overwritten to be used as default value for various options.
    default: str | None = ""

    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=("CLI to download latest or manage your GE-Proton for " "Steam"),
        epilog=(
            "\n\n"
            "Copyright © 2023, 2024 Tuncay D. "
            "<https://github.com/thingsiplay/geprotondl>"
        ),
    )

    parser.add_argument(
        "-v", "--version", action="store_true", help="show version information and exit"
    )

    folders = parser.add_argument_group(title="locations", description=None)

    default, status = default_install_dir()
    if status == FinishStatus.FAILURE:
        return parser.parse_args([]), FinishStatus.FAILURE

    folders.add_argument(
        "-D",
        "--dir",
        metavar="DIR",
        type=File,
        default=default,
        help=("folder to unpack and install GE-Proton into, default: " f'"{default}"'),
    )

    default = File("~/.cache/geprotondl").as_posix()
    folders.add_argument(
        "-C",
        "--cache",
        metavar="DIR",
        type=File,
        default=default,
        help=("folder to save temporary cache files into, default: " f'"{default}"'),
    )

    folders.add_argument(
        "-d",
        "--print-dir",
        action="store_true",
        help="show path of install folder set by -D, can be combined with -b",
    )

    folders.add_argument(
        "-c",
        "--print-cache",
        action="store_true",
        help="show path of cache folder set by -C, can be combined with -b",
    )

    mode = parser.add_argument_group(title="modes", description=None)
    mode_ex = mode.add_mutually_exclusive_group()

    mode_ex.add_argument(
        "-i",
        "--install",
        action="store_true",
        help=(
            "download and unpack latest release, combine with -l or -T to "
            "choose from other available versions"
        ),
    )

    mode_ex.add_argument(
        "-r",
        "--remove",
        action="store_true",
        help=(
            "uninstall oldest local version, combine with -l or -T to "
            "choose from other available versions"
        ),
    )

    mode_ex.add_argument(
        "-t",
        "--test",
        action="store_true",
        help=(
            "show tag name if it's known in database and not installed "
            "locally, default to latest unless combined with -T, when "
            "-l or -L are active then always show selected tag name, "
            "can be combined with -b to output version number only"
        ),
    )

    choose = parser.add_argument_group(title="choose", description=None)

    choose.add_argument(
        "-T",
        "--tag",
        metavar="NAME",
        help=(
            "select a specific version by tag name identifier, in example "
            'as "GE-Proton7-53" or in short "7-53"'
        ),
    )

    listing = parser.add_argument_group(title="listing", description=None)
    listing_ex = listing.add_mutually_exclusive_group()

    listing_ex.add_argument(
        "-l",
        "--list",
        action="store_true",
        help=(
            "show local installed versions, but when combined with -i then "
            "show downloadable releases instead"
        ),
    )

    listing_ex.add_argument(
        "-L",
        "--releases",
        action="store_true",
        help=(
            "show downloadable releases, but when combined with -r then "
            "show local installed versions instead"
        ),
    )

    listing.add_argument(
        "-m",
        "--max",
        metavar="NUM",
        type=int,
        help=(
            "limit max entries to show for listings, defaults to '9' for "
            "install and no limit otherwise"
        ),
    )

    info = parser.add_argument_group(title="info", description=None)

    info.add_argument(
        "-s",
        "--summary",
        action="store_true",
        help="show description and meta information for selected version",
    )

    info.add_argument(
        "-H",
        "--human",
        action="store_true",
        help=(
            "format certain numbers, dates and entire structures into human "
            "readable presentation"
        ),
    )

    info.add_argument(
        "-b",
        "--brief",
        action="store_true",
        help=(
            "reduce some output to be compact, create excerpts from long "
            "descriptions"
        ),
    )

    info.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help=(
            "suppress most informal and error messages, hide interface "
            "parts providing additional context"
        ),
    )

    control = parser.add_argument_group(title="control", description=None)

    control.add_argument(
        "-f",
        "--force",
        action="store_true",
        help=(
            "skip checksum verification, re-download database and files, "
            "re-install and overwrite existing version"
        ),
    )

    control.add_argument(
        "-y",
        "--yes",
        action="store_true",
        help=(
            "don't ask to proceed for download, install or remove, assume " "reply yes"
        ),
    )

    if argv is None:
        return parser.parse_args(), FinishStatus.SUCCESS
    else:
        return parser.parse_args(argv), FinishStatus.SUCCESS


# Run the program main() with predefined set of options, instead arguments
# from commandline. Exit program immediately if return value is a failure.
def run_main(argv: list[str]) -> int:
    if not argv:
        return 1
    exitcode: int = main(argv)
    if not exitcode == 0:
        sys.exit(exitcode)
    return 0


# The mighty main.
def main(argv: list[str] | None = None) -> int:  # noqa: C901
    # Used to indicate return values of functions and operations to determine
    # if it was a success or failure.
    status: FinishStatus = FinishStatus.UNKNOWN

    # Parses the commandline arguments from user or gets default values in
    # preparation for initializing the App later.
    arguments, status = parse_arguments(argv)

    if status == FinishStatus.FAILURE:
        return 1

    # Basically initializes the entire program, it's state and sets up all
    # needed files and options. Unless option "--version" is given; in which
    # case the program will end very early anyway.
    app = App(arguments)
    status = app.status

    if status == FinishStatus.FAILURE:
        return 1

    # With this option in place, no need to further run the program.
    if app.show_version:
        app.print_version()
        return 0

    if app.show_dir:
        app.print_dir()
    if app.show_cache:
        app.print_cache()

    # A user selection from a list can only be done when printing a listing
    # too. But only, if not tag name is set on options already. A cancellation
    # from withing a choose operation should exit application.
    choice: GithubDatabaseEntry | str | int | None = None
    status = FinishStatus.UNKNOWN

    if app.show_listing:
        app.local.print_listing()
        if not app.tag_name and app.local.installs:
            if app.remove_mode:
                (choice, _), status = app.local.choose("Remove")
            elif app.show_summary or app.show_test_mode:
                (choice, _), status = app.local.choose()

    elif app.show_releases and app.releases:
        app.releases.print_listing(app.local.installs)
        if not app.tag_name and app.releases.db:
            if app.install_mode:
                choice, status = app.releases.choose("Install")
            elif app.show_summary or app.show_test_mode:
                choice, status = app.releases.choose()

    if status == FinishStatus.FAILURE:
        return 1

    # Load up the version that was either set in commandline or chosen
    # interactively by the user. Otherwise default to a standard selection
    # (usually top most).
    status = FinishStatus.UNKNOWN
    if choice:
        status = app.load_active_entry(choice)
    elif not app.active_entry:
        status = app.load_active_entry()

    if status == FinishStatus.FAILURE:
        return 1

    # Now do something with the previously set entry, which represents a
    # specific GE-Proton version.
    status = FinishStatus.UNKNOWN

    if app.show_test_mode:
        status = app.print_test()
    elif app.install_mode:
        status = app.install_entry()
    elif app.remove_mode:
        status = app.remove_entry()

    if status == FinishStatus.FAILURE:
        return 1

    return 0


# When no commandline options are available, start a default routine with
# predefined set of options to run main() multiple times for automation.
if __name__ == "__main__":
    sys.exit(main())
