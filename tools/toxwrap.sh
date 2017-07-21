#!/usr/bin/env bash

set -o pipefail

ARGS=$1

if [[ "$ARGS" =~ ^"pdb " ]]; then
    # Run tests in the foreground, allowing pdb to break
    set -- $ARGS
    PATTERN="$2"
    if ! [ $PATTERN ]; then
        PATTERN=.
    fi
    python -m testtools.run `testr list-tests "$PATTERN" | grep "$PATTERN"`
elif [[ "$ARGS" =~ "until-failure" ]]; then
    # --until-failure is not compatible with --subunit see:
    #
    # https://bugs.launchpad.net/testrepository/+bug/1411804
    #
    # this work around exists until that is addressed
    python setup.py testr --slowest --testr-args="$ARGS"
else
    python setup.py testr --slowest --testr-args="--subunit $ARGS" | subunit-trace -f
fi
