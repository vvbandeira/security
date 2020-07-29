#!/usr/bin/env python3

import unittest
import os
import shutil
import subprocess

precommit = __import__("pre-commit")


def run_command(command):
    "Run a shell command and ensure it didn't error"
    r = subprocess.run(command, stdout=subprocess.PIPE, encoding='utf-8',
                       shell=True)
    r.check_returncode()


# Dummy arguments object to pass to the precommit script
args = precommit.parse_args([])


class TestBlock(unittest.TestCase):
    def setUp(self):
        'Setup a dummy repo to test in'
        os.mkdir("test_area")
        run_command("git init test_area")
        os.chdir("test_area")

    def tearDown(self):
        os.chdir("..")
        shutil.rmtree("test_area")
        pass

    ## Helpers ##
    def add_file(self, path, content=''):
        'Commit a file to the repo with given contents'
        dirs = os.path.dirname(path)
        if dirs:
            os.makedirs(dirs)
        with open(path, 'w') as f:
            print(content, file=f)
        run_command("git add {}".format(path))

    def add_files(self, cnt):
        'Add cnt files to the repo'
        for i in range(cnt):
            self.add_file('file{}'.format(i))

    def do_test_bad_file(self, path):
        'Create a file and make sure it is blocked by precommit path check'
        self.add_file(path)
        with self.assertRaises(SystemExit) as e:
            precommit.main(args)
        self.assertIn('name is blocked', str(e.exception))

    def do_test_good_file(self, path):
        'Create a file and make sure it is allowed by precommit'
        self.add_file(path)
        # passes if no exception raised
        precommit.main(args)

    def do_test_bad_content(self, content=''):
        'Create a file and make sure it is block by precommit content check'
        self.add_file("test_file", content)
        with self.assertRaises(SystemExit) as e:
            precommit.main(args)
        self.assertIn('blocked content pattern', str(e.exception))

    ## Blocked / allowed paths tests ##
    def test_gf12_fails(self):
        self.do_test_bad_file('dir/some_gf12_data')

    def test_new_platform_fails(self):
        self.do_test_bad_file('flow/platforms/7nm')

    def test_verilog_fails(self):
        self.do_test_bad_file('foo.v')

    def test_gds_fails(self):
        self.do_test_bad_file('foo.gds2')

    def test_lef_fails(self):
        self.do_test_bad_file('foo.lef.gz')

    def test_cal_fails(self):
        self.do_test_bad_file('foo.cal')

    def test_cdl_fails(self):
        self.do_test_bad_file('a/b/foo.cdl')

    def test_lib_fails(self):
        self.do_test_bad_file('foo.lib')

    def test_tsmc_fails(self):
        self.do_test_bad_file('tsmc65lp')

    def test_arm_fails(self):
        self.do_test_bad_file('sc9mcpp84_12lp_base_rvt')

    def test_flow_allowed_only_if_at_start_of_path(self):
        self.do_test_bad_file('gf14/flow/designs')

    def test_nangate_update_ok(self):
        self.do_test_good_file('flow/platforms/nangate45/netlist.v')

    def test_design_verilog_ok(self):
        self.do_test_good_file('flow/designs/foo.v')

    ## Size of adds / changes tests ##
    def test_too_many_adds_fails(self):
        cnt = precommit.file_add_limit + 1
        self.add_files(cnt)
        with self.assertRaises(SystemExit) as e:
            precommit.main(args)
        self.assertIn('too many files added', str(e.exception))

    def test_too_many_changes_fails(self):
        # setup by committing files
        cnt = precommit.file_change_limit + 1
        self.add_files(cnt)
        run_command("git commit -m 'msg' --no-verify")

        # Continue setup by modifying the files
        for i in range(cnt):
            with open('file{}'.format(i), 'w') as f:
                print('modified', file=f)

        # Finish setup by staging all the modified files
        run_command("git add .")

        # now test
        with self.assertRaises(SystemExit) as e:
            precommit.main(args)
        self.assertIn('too many files changed', str(e.exception))

    ## Blocked content tests ##
    def test_gf_content_fails(self):
        self.do_test_bad_content('gf12 secrets')

    def test_arm_content_fails(self):
        self.do_test_bad_content('ARM Limited')

    def test_invecus_content_fails(self):
        self.do_test_bad_content('data for 12LP')

    def test_tsmc_content_fails(self):
        self.do_test_bad_content('\n\n\n  tsmc')


if __name__ == '__main__':
    unittest.main()
