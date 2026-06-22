import os, subprocess

def move_to_repo_root():
    os.chdir(subprocess.check_output(["git", "rev-parse", "--show-toplevel"]).decode().strip())
