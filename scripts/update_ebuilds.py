#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright 2025 Florian Albrechtskirchinger <falbrechtskirchinger@gmail.com>
#
# SPDX-License-Identifier: MIT

import argparse
import glob
import hashlib
import json
import os
import subprocess

import requests

BRAVE_RELEASES = "https://api.github.com/repos/brave/brave-browser/releases"
MANIFEST_HASH_ALGOS = ("BLAKE2B", "SHA512")


def extract_version(path):
    return os.path.basename(path).split("-")[-1].rsplit(".", 1)[0]


# For sorting ebuilds by version
def version_key(path):
    version = extract_version(path)
    return [int(part) for part in version.split(".")]


def get_latest_releases():
    releases = {
        "stable": None,
        "beta": None,
        "nightly": None,
    }
    releases_found = 0

    headers = {"Accept": "application/vnd.github.v3+json"}
    response = requests.get(BRAVE_RELEASES, headers=headers)
    response.raise_for_status()
    for release in response.json():
        for key, name in (
            ("stable", "Release "),
            ("beta", "Beta "),
            ("nightly", "Nightly "),
        ):
            suffix = "" if key == "stable" else f"-{key}"
            if not releases[key] and release["name"].startswith(name):
                tag = release["tag_name"]
                assert tag[0] == "v"
                version = tag[1:]
                source_file = f"brave-browser{suffix}_{version}_amd64.deb"
                asset_files = {asset["name"] for asset in release["assets"]}
                if source_file in asset_files:
                    releases[key] = tag[1:]
                    releases_found += 1

        if releases_found == len(releases):
            break

    if not releases_found == len(releases):
        raise RuntimeError("Could not find latest release for all channels.")

    return releases


def get_new_releases(releases, repo_dir):
    new_releases = dict()
    for key, version in releases.items():
        suffix = "" if key == "stable" else f"-{key}"
        ebuild_path = os.path.join(
            repo_dir,
            f"www-client/brave-browser{suffix}/brave-browser{suffix}-{version}.ebuild",
        )
        if not os.path.exists(ebuild_path):
            new_releases[key] = releases[key]

    return new_releases


def update_ebuilds(new_releases, repo_dir, commit_changes=False):
    new_ebuilds = dict()
    for key, version in new_releases.items():
        suffix = "" if key == "stable" else f"-{key}"
        name = f"brave-browser{suffix}"
        source_file = f"{name}_{version}_amd64.deb"
        url = f"https://github.com/brave/brave-browser/releases/download/v{version}/{source_file}"
        ebuild_dir = os.path.join(repo_dir, f"www-client/brave-browser{suffix}")
        ebuilds = sorted(
            glob.glob(os.path.join(ebuild_dir, "*.ebuild")), key=version_key
        )

        if len(ebuilds) == 0:
            raise RuntimeError(f"No ebuilds in '{ebuild_dir}'.")

        added = [f"{version}"]
        dropped = [extract_version(ebuilds[-1])]

        new_ebuild = os.path.join(ebuild_dir, f"{name}-{version}.ebuild")
        os.rename(ebuilds[-1], new_ebuild)
        new_ebuilds[key] = os.path.relpath(new_ebuild, repo_dir)

        for ebuild in ebuilds[:-1]:
            os.unlink(ebuild)
            dropped.append(extract_version(ebuild))

        update_manifest(ebuild_dir, name)

        if commit_changes:
            message = ", ".join(
                filter(
                    None,
                    [
                        "added: " + ", ".join(added) if added else None,
                        "dropped: " + ", ".join(dropped) if dropped else None,
                    ],
                )
            )

            subprocess.run(["git", "add", ebuild_dir], check=True)
            subprocess.run(
                ["git", "commit", "-m", f"www-client/{name}: {message}"], check=True
            )

    return new_ebuilds


def update_manifest(ebuild_dir, name):
    ebuilds = glob.glob(os.path.join(ebuild_dir, "*.ebuild"))
    versions = set(extract_version(ebuild) for ebuild in ebuilds)
    versions_in_manifest = set()
    sources = [
        {
            "file": (filename := f"{name}_{version}_amd64.deb"),
            "url": f"https://github.com/brave/brave-browser/releases/download/v{version}/{filename}",
            "version": version,
        }
        for version in versions
    ]
    sources_by_filename = {source["file"]: source for source in sources}
    sources_by_version = {source["version"]: source for source in sources}
    with open(os.path.join(ebuild_dir, "Manifest"), "r") as f:
        lines = f.readlines()
        new_lines = []
        for line in lines:
            parts = line.split(" ")
            if parts[0] == "DIST":
                if parts[1] in sources_by_filename:
                    print("  keep")
                    # Keep DIST lines for current ebuilds
                    new_lines.append(line)
                    versions_in_manifest.append(
                        sources_by_filename[parts[1]]["version"]
                    )
            else:
                new_lines.append(line)

    # Add DIST lines for new ebuilds
    for version in versions - versions_in_manifest:
        source = sources_by_version[version]
        hashers = {algo: hashlib.new(algo.lower()) for algo in MANIFEST_HASH_ALGOS}
        size = 0
        with requests.get(source["url"], stream=True, timeout=300) as r:
            r.raise_for_status()
            for chunk in r.iter_content(chunk_size=8192):
                size += len(chunk)
                for hasher in hashers.values():
                    hasher.update(chunk)

        digests = {algo: hasher.hexdigest() for algo, hasher in hashers.items()}
        new_lines.append(
            f"DIST {source['file']} {size} {' '.join([f'{algo} {digest}' for algo, digest in digests.items()])}\n"
        )

    with open(os.path.join(ebuild_dir, "Manifest"), "w") as f:
        f.writelines(new_lines)


def main():
    parser = argparse.ArgumentParser(
        description="Update ebuilds for Brave browser releases."
    )
    parser.add_argument(
        "--commit",
        action="store_true",
        default=False,
        help="Commit changes to the repository.",
    )
    args = parser.parse_args()

    repo_dir = os.path.join(os.path.dirname(__file__), "..")

    releases = get_latest_releases()
    new_releases = get_new_releases(releases, repo_dir)
    new_ebuilds = update_ebuilds(new_releases, repo_dir, commit_changes=args.commit)

    if "GITHUB_OUTPUT" in os.environ:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True
        )
        new_ebuilds["commit_hash"] = result.stdout.strip()

        with open(os.environ["GITHUB_OUTPUT"], "a") as f:
            print(f"new_ebuilds<<EOF\n{json.dumps(new_ebuilds)}\nEOF\n", file=f)

    if "GITHUB_STEP_SUMMARY" in os.environ:
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as f:
            f.write("### 🚀 Update Ebuilds Results\n\n")

            if new_ebuilds:
                f.write("✨ New ebuilds were added:\n\n")
                for key, ebuild in new_ebuilds.items():
                    f.write(f"- **{key.capitalize()}**: `{ebuild}`\n")
            else:
                f.write("✅ No new releases were found.\n")


if __name__ == "__main__":
    main()
