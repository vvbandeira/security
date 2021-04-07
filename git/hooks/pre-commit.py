#!/usr/bin/env python3

import argparse
import subprocess
import re
import sys
import os

print("Running pre-commit security hook....")

# Limits for rules
file_add_limit    = 10
file_change_limit = 50

# The following patterns are regular expressions and are matched
# case-insensitive.  They are matched anywhere with the string
# and can have leading or trailing characters and still match.

# Blocked paths (unless allowed below).
blocked_path_patterns = [
    r"flow/",
    r"\.gds",
    r"\.lef",
    r"\.cdl",
    r"\.cal",
    r"\.v",
    r"\.db",
    r"\.lib",
    r"\.t?gz",
    r"\.tar",
    r"tsmc",
    r"gf\d+",
    r"\d+lp",    # Invecas
    r"sc\d+",    # ARM-style names
    r"cln\d+",   # eg CLN65 (for ARM)
    r"scc9gena", # Sky90 library
    r"sky90"     # Sky90
]

# Allowed paths are exceptions to blocked paths above.
allowed_path_patterns = [
    r"^flow/designs",
    r"^flow/docs",
    r"^flow/platforms/nangate45",
    r"^flow/platforms/sky130",
    r"^flow/platforms/asap7",
    r"^flow/scripts",
    r"^flow/test",
    r"^flow/util",
    r"^flow/README.md",
    r"^flow/Makefile",
    r"^(tools/OpenROAD/)?src/FastRoute/test",
    r"^(tools/OpenROAD/)?src/ICeWall/test",
    r"^((tools/OpenROAD/)?src/OpenDB/)?src/lef(56)?/TEST",
    r"^((tools/OpenROAD/)?src/OpenDB/)?test",
    r"^(tools/OpenROAD/)?src/OpenPhySyn/test",
    r"^(tools/OpenROAD/)?src/OpenSTA/examples",
    r"^(tools/OpenROAD/)?src/OpenSTA/test",
    r"^(tools/OpenROAD/)?src/PDNSim/test",
    r"^(tools/OpenROAD/)?src/TritonCTS/test",
    r"^(tools/OpenROAD/)?src/TritonMacroPlace/test",
    r"^(tools/OpenROAD/)?src/antennachecker/test",
    r"^(tools/OpenROAD/)?src/dbSta/test",
    r"^(tools/OpenROAD/)?src/init_fp/test",
    r"^(tools/OpenROAD/)?src/ioPlacer/test",
    r"^(tools/OpenROAD/)?src/opendp/test",
    r"^(tools/OpenROAD/)?src/pdngen/test",
    r"^(tools/OpenROAD/)?src/replace/test",
    r"^(tools/OpenROAD/)?src/resizer/test",
    r"^(tools/OpenROAD/)?src/tapcell/test",
    r"^(tools/OpenROAD/)?src/OpenRCX/test",
    r"^(tools/OpenROAD/)?test",
    r"^tools/yosys",
]

# Files may not contain these patterns in their content anywhere (not
# just the changed portion).  All staged files are checked, even
# "allowed" files - there should still be no bad content in allowed
# files.
#
# Uses compiled expression for performance.
block_content_patterns = \
    re.compile(r"""
       gf\d\d+      # eg gf12, gf14
     | tsmc       # eg tsmc65lp
     | \d+lp      # eg 12LP (for Invecus)
     | \barm\b    # eg ARM
     | cln\d+     # eg CLN65 (for ARM)
     | cypress    # eg Cypress Semiconductor
    """, re.VERBOSE | re.IGNORECASE)

# Files to skip content checks on
skip_content_patterns = [
    r"\.gif$",
    r"\.jpg$",
    r"\.png$",
    r"\.pdf$",
    r"\.gif$",
    r"\.odt$",
    r"\.xlsx$",
    r"\.dat$",  # eg POWV9.dat
    r"\.gds(\.orig)?$",
    r"^README.md$",
    r"^flow/README.md$",
    r"^(tools/TritonRoute)?/README.md$",
    r"^(tools/OpenROAD/)?src/replace/README.md$",
    r"^tools/yosys/",
    r"^\.git/",
    r"^flow/designs/.*/config.mk$",
    r"^flow/designs/.*/wrappers.tcl$",
    r"^flow/designs/.*/macros.v$",
    r"^flow/designs/src/.*\.sv2v\.v$",
    r"^flow/scripts/add_routing_blk.tcl$",
    r"^flow/scripts/floorplan.tcl$",
    r"^flow/test/core_tests.sh$",
    r"^flow/test/smoke.sh$",
    r"^flow/util/cell-veneer/wrap_stdcells.tcl",
    r"^flow/util/cell-veneer/lefdef.tcl",
    r"^flow/Makefile$",
]

# Commits to these repos aren't checked as they are
# never to be made public and are intended for confidential
# data.
repos_secure = set((
    '/home/zf4_projects/OpenROAD-guest/platforms/gf12.git',
    '/home/zf4_projects/OpenROAD-guest/platforms/tsmc65lp.git',
))

def error(msg):
    msg = '\n\nERROR: {}\n\nTo request an exception please contact Tom' \
      .format(msg)
    sys.exit(msg)


def run_command(command):
    r = subprocess.run(command,
                       stdout=subprocess.PIPE,
                       encoding='utf-8',
                       shell=True)
    r.check_returncode()

    # Split the output into lines
    return r.stdout.rstrip().split('\n')


def check_content(name, args, whole_file=False):
    for pattern in skip_content_patterns:
        if re.search(pattern, name, re.IGNORECASE):
            if args.verbose:
                print("Skipping content check on {}".format(name))
            return

    # Submodules updates will show up as names to be checked but they
    # should have their contents checked when the submodule itself
    # was committed to. Skip them here.
    if os.path.isdir(name):
        print("Skipping content check on subdir {}".format(name))
        return

    if whole_file:
        with open(name) as f:
            lines = f.readlines()
    else:
        # the : in front of the file name gets the staged version of the
        # file, not what is currently on disk unstaged which could be
        # different (and possibly not contain the keyword).  We check the
        # whole file not just the changed portion.
        lines = run_command('git show :{}'.format(name))
    for cnt, line in enumerate(lines):
        # re.search matches anywhere in the line
        if re.search(block_content_patterns, line):
            msg = "File {} contains blocked content" \
                " on line {} :\n  {}" \
                .format(name,
                        cnt + 1,
                        line)
            error(msg)


def is_blocked(name, args):
    'Is this name blocked by the path patterns?'
    blocked = False
    for pattern in blocked_path_patterns:
        if re.search(pattern, name, re.IGNORECASE):
            blocked = True
            if args.verbose:
                print("{} matches blocked {}".format(name, pattern))
            break
    if blocked:
        for pattern in allowed_path_patterns:
            if re.search(pattern, name, re.IGNORECASE):
                blocked = False
                if args.verbose:
                    print("{} matches allowed {}".format(name, pattern))
                break
    return blocked


def parse_args(args):
    parser = argparse.ArgumentParser(description='Commit checker')
    parser.add_argument('--local', action='store_true')
    parser.add_argument('--report', action='store_true')
    parser.add_argument('--verbose', action='store_true')
    return parser.parse_args(args)


def walk_error(e):
    raise e


def local(top, args):
    """Check the local tree not the git diff.  This is for private to
    public prechecking. """
    for root, dirs, files in os.walk(top,
                                     onerror=walk_error,
                                     followlinks=True):
        assert(root.startswith(top))
        if root == top:
            root = ''
        else:
            root = root[len(top)+1:]
        for name in files:
            full_name = os.path.join(root, name)
            if is_blocked(full_name, args):
                msg = "File name is blocked: {}".format(full_name)
                error(msg)
            check_content(full_name, args, whole_file=True)


def check_remotes_secure():
    repos = run_command('git remote --verbose')
    allowed = True
    # Example line:
    # origin	/home/zf4_projects/OpenROAD-guest/platforms/gf12.git (fetch)
    for line in repos:
        if not line: # local repo (used for testing)
            allowed = False
            break
        (name, url, _) = re.split('\t| \(', line)
        if url not in repos_secure:
            allowed = False
            break
    return allowed

def main(args):
    # subprocess.run doesn't exist before 3.5
    if sys.version_info < (3, 5):
        sys.exit("Python 3.5 or later is required")

    # Make sure this is running from the top level of the repo
    try:
        top = run_command('git rev-parse --show-toplevel')[0]
    except:
        error('Not running in git repo: {}'.format(os.getcwd()))

    # Make sure we are running from the root (always true as a hook
    # but not if run manually)
    if os.getcwd() != top:
        print('Running from {}'.format(top))
        os.chdir(top)

    if args.local:
        local(top, args)
        return

    if check_remotes_secure():
        print('All git remotes are secure, checking skipped')
        return

    # Get status of the staged files
    lines = run_command('git diff --cached --name-status')
    if len(lines[0]) == 0:
        sys.exit('ERROR: Nothing is staged')

    # Split the lines in status & file.  Filenames containing whitespace
    # are problematic so don't do that.
    lines = [l.split() for l in lines]
    for l in lines:
        if l[0].startswith('R'): # Handle renames
            assert(len(l) == 3)
            l[0] = 'R'  # Strip off score
            del l[1]    # remove old name
        assert(len(l) == 2)     # sanity check : <status> <file>
        assert(len(l[0]) == 1)  # sanity check : <status> is one char

    # Newly added files
    added = [f[1] for f in lines if f[0] == 'A']
    num_added = len(added)

    # This is all other changes, including modify, rename, copy, delete
    num_changed = len(lines) - num_added

    if (args.report):
        print("Added {} (limit: {})".format(num_added, file_add_limit))
        for name in added:
            print("   ", name)
        print("Changed {} (limit: {})".format(num_changed, file_change_limit))

    # Check: num added
    if num_added > file_add_limit:
        msg = "too many files added: {} vs limit {}".format(num_added,
                                                            file_add_limit)
        error(msg)

    # Check: num changed
    if num_changed > file_change_limit:
        msg = "too many files changed: {} vs limit {}".format(num_changed,
                                                              file_change_limit)
        error(msg)

    # Check: blocked files
    for status, name in lines:
        if is_blocked(name, args):
            msg = "File name is blocked: {}".format(name)
            error(msg)

    # Check: blocked content
    for status, name in lines:
        if status != 'D': # deleted are always ok
            check_content(name, args)

    print("Passed")


if __name__ == "__main__":
    args = parse_args(sys.argv[1:])
    main(args)
