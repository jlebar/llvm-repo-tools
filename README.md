# llvm-port-commits

This repository contains a tool for moving commits from a single-subproject LLVM
repo to a multi-subproject LLVM repo.

At the moment it's not particularly general or friendly.  Please view this as a
proof of concept.

## Usage

We need to define some terms:

 * *subproject repo* -- A git repository that mirrors changes to a subirectory
   of LLVM's SVN.  https://github.com/llvm-mirror/clang is the clang subproject
   repo.
 * *monorepo* (monolithic repository) -- A git repository that contains for many
   llvm subprojects, e.g. https://github.com/llvm-project/llvm-project
 * *repo to port* -- A fork of a subproject repo, e.g.  the CHERI clang fork,
   https://github.com/CTSRD-CHERI/clang.git.

Suppose we want to move the changes in the `master` branch of the CHERI clang
fork to the monorepo.  We would run the following commands:

    # Clone this repository into $filter_dir.
    $ filter_dir=`mktemp -d`
    $ cd $filter_dir
    $ git clone https://github.com/jlebar/llvm-port-commits.git .

    # Create a repository containing the changes from the three repos.
    $ cd `mktemp -d`
    $ git init
    # The monorepo must be the "origin" remote.
    $ git remote add origin https://github.com/llvm-project/llvm-project
    # The subproject repo must be named "old-clang".
    $ git remote add old-clang https://github.com/llvm-mirror/clang.git
    # The name of the repo to port doesn't matter.
    $ git remote add cheri-clang https://github.com/CTSRD-CHERI/clang.git

    $ git fetch origin
    $ git fetch old-clang
    $ git fetch cheri-clang

    # Create a branch named cheri-clang-master based on cheri-clang/master, and
    # port the changes in chery-clang-master but not in old-clang/master to the
    # monorepo.  (The script doesn't care about this branch name, call it
    # whatever you want.)
    $ git checkout -b cheri-clang-master cheri-clang/master
    $ git filter-branch --parent-filter "python $filter_dir/filter.py parent" \
      --index-filter "python $filter_dir/filter.py index" cheri-clang-master \
      ^old-clang/master

The script will run faster if you `pip install pyfscache`, but it's not
required.

The result of running this on the CHERI clang master branch is at
https://github.com/jlebar/llvm-project/tree/cheri-clang-master.

## Known limitations

This script doesn't handle porting subproject repos other than clang.  It also
assumes that the monorepo has the format of
https://github.com/llvm-project/llvm-project.

## Disclaimer

This is not an official Google project.
