#!/bin/bash
fetch() {
    if [[ -f $1 ]]; then
        curl -z $1 -o $1 $2 -#
    else
        curl -o $1 $2 -#
    fi
}

STATIC_DIR=$(dirname $(dirname $0))/static/vendor/
set -e -v

pushd $STATIC_DIR

  fetch bootstrap.zip http://twitter.github.com/bootstrap/assets/bootstrap.zip
  if [[ -f bootstrap.zip ]]; then
    unzip -u bootstrap.zip
    rm bootstrap.zip
  fi

  mkdir -p jquery
  pushd jquery/
    fetch jquery.min.js http://code.jquery.com/jquery-1.9.0.min.js
  popd

popd
