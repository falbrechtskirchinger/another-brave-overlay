# SPDX-FileCopyrightText: Copyright 2025 Florian Albrechtskirchinger <falbrechtskirchinger@gmail.com>
#
# SPDX-License-Identifier: MIT

import glob
import json
import os
import re
import subprocess

import requests

CHANNELS_WITH_TITLE = [
    ("stable", "Release "),
    ("beta", "Beta "),
    ("nightly", "Nightly "),
]
CHANNELS = [channel for channel, _ in CHANNELS_WITH_TITLE]
BRAVE_TO_CHROME_CHANNELS = {
    "stable": "stable",
    "beta": "beta",
    "nightly": "unstable",
}

GH_API_ACTION_JOBS = "https://api.github.com/repos/{repo}/actions/runs/{run_id}/jobs"

GENTOO_REPO = "/var/db/repos/gentoo"
GENTOO_PORTAGE_MIRROR = "rsync://rsync.gentoo.org/gentoo-portage/"

_JOB_NAME_RE = re.compile(r"^Test ebuild \((.+?)\) \[(.+?)\]$")
_VERSION_REGEX = re.compile(r"-\d[\d\.-r]+")  # TODO


def extract_version(path):
    filename = os.path.basename(path)
    assert filename.endswith(".ebuild")

    base_name = filename.rsplit(".ebuild", 1)[0]
    match = _VERSION_REGEX.search(base_name)
    if not match:
        raise ValueError(f"Could not find a valid version in '{filename}'.")

    return match.group(0)[1:]


def version_key(path):
    revision = 0
    version = version_full = extract_version(path)
    if "-r" in version:
        parts = version_full.rsplit("-r", 1)
        version = parts[0]
        revision = int(parts[1])
    return [int(part) for part in version.split(".")] + [revision]


def make_name_from_channel(channel, base_name="brave-browser"):
    suffix = "" if channel == "stable" else f"-{channel}"
    name = f"{base_name}{suffix}"
    return name


def get_ebuilds(
    channel,
    base_name="brave-browser",
    repo_dir=None,
    only_latest=False,
    relative_paths=False,
):
    repo_dir = repo_dir or os.getcwd()

    name = make_name_from_channel(channel, base_name=base_name)
    ebuild_dir = os.path.join(repo_dir, f"www-client/{name}")
    ebuilds = sorted(glob.glob(os.path.join(ebuild_dir, "*.ebuild")), key=version_key)

    if only_latest:
        ebuilds = [ebuilds[-1]]

    if relative_paths:
        ebuilds = [os.path.relpath(ebuild, repo_dir) for ebuild in ebuilds]

    return ebuilds, ebuild_dir


def gh_get(url, require_auth=False, **kwargs):
    headers = {"Accept": "application/vnd.github.v3+json"}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"token {token}"
    if not token and require_auth:
            raise RuntimeError("GITHUB_TOKEN environment variable unset or empty.")

    response = requests.get(url, headers=headers, **kwargs)
    response.raise_for_status()

    return response


def require_gha():
    if "GITHUB_ACTIONS" not in os.environ:
        raise RuntimeError("Not running in a GitHub Action workflow.")


def get_run_id(from_event=False):
    if from_event:
        event_path = os.environ.get("GITHUB_EVENT_PATH")
        if not event_path:
            raise RuntimeError("GITHUB_EVENT_PATH environment variable unset or empty.")

        with open(event_path, "r") as f:
            event = json.load(f)
            return event["workflow_run"]["id"]
    else:
        run_id = os.environ.get("GITHUB_RUN_ID")
        if not run_id:
            raise RuntimeError("GITHUB_RUN_ID environment variable unset or empty.")
        return run_id


def get_run_jobs(run_id):
    repo = os.environ.get("GITHUB_REPOSITORY")
    if not repo:
        raise RuntimeError("GITHUB_REPOSITORY environment variable unset or empty.")

    response = gh_get(GH_API_ACTION_JOBS.format(repo=repo, run_id=run_id), require_auth=True)
    return response.json()["jobs"]


def set_output(name, value):
    output = os.environ.get("GITHUB_OUTPUT")
    if not output:
        raise RuntimeError("GITHUB_OUTPUT environment variable unset or empty.")

    with open(output, "a") as f:
        f.write(f"{name}<<-EOF\n{value}\n-EOF\n")


def gh_get_variable(var, default=None, raw=False):
    if os.environ.get("GH_TOKEN") is None:
        raise RuntimeError("GH_TOKEN environment variable unset or empty.")

    try:
        result = subprocess.run(
            [
                "gh",
                "variable",
                "get",
                var,
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        value = result.stdout.strip()
    except subprocess.CalledProcessError as e:
        if e.returncode != 1:
            raise e
        value = None

    if not raw:
        value = json.loads(value) if value else default

    return value


def gh_set_variable(var, value, raw=False):
    if os.environ.get("GH_TOKEN") is None:
        raise RuntimeError("GH_TOKEN environment variable unset or empty.")

    value = value if raw else json.dumps(value)

    subprocess.run(
        [
            "gh",
            "variable",
            "set",
            var,
        ],
        check=True,
        input=str(value).encode(),
    )


def collect_test_results(from_event=False, read_variables=False, write_variables=False):
    run_id = get_run_id(from_event=from_event)
    jobs = get_run_jobs(run_id)
    test_results = {}
    for job in jobs:
        if job["conclusion"] == "skipped":
            continue
        job_name = job.get("name", "")
        assert "${{" not in job_name
        match = _JOB_NAME_RE.match(job_name)
        if match:
            ebuild_path, channel = match.groups()
            test_results[channel] = {
                "conclusion": job.get("conclusion"),
                "ebuild_path": ebuild_path,
                "version": extract_version(ebuild_path),
            }

    for channel in CHANNELS:
        var = f"TEST_RESULT_{channel.upper()}"
        if channel in test_results:
            if write_variables and test_results[channel]["conclusion"] in (
                "success",
                "failure",
            ):
                gh_set_variable(var, test_results[channel])
            test_results[channel]["cached"] = False
        elif read_variables:
            if result := gh_get_variable(var):
                test_results[channel] = result
                test_results[channel]["cached"] = True

    return test_results
