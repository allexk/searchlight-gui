#!/bin/bash

SCIDB_VER="14.12"
SCIDB4PY_BUILD_DIR="scidb4py-build"
SCIDB4PY_PROTO_FILE="_scidb_msg_pb2.py"

# Exit on error
set -e

# First, setup virtualenv. We need system packages due to PyQt
virtualenv --system-site-packages venv-sl
source venv-sl/bin/activate

# pre-reqs
pip install 'requests>=2.6.0' # SSLv3 on Debian error
pip install 'protobuf==2.4.1'

# copy scidb4py into the build dir
if [ ! -d $SCIDB4PY_BUILD_DIR ]; then
    mkdir "$SCIDB4PY_BUILD_DIR"
fi
cp -r scidb4py/* $SCIDB4PY_BUILD_DIR

# patching scidb4py
pushd $SCIDB4PY_BUILD_DIR > /dev/null
SCIDB4PY_PATCH_FILE="scidb4py-$SCIDB_VER.patch"
if [ ! -r $SCIDB4PY_PATCH_FILE ]; then
    if [ ! "$SCIDB_VER" == "14.3" ]; then # SciDB 14.3 should be fine
        echo "Cannot find scidb4py patch file for SciDB $SCIDB_VER..."
        popd > /dev/null
        exit 3
    fi
else
    echo "Patching scidb4py with $SCIDB4PY_PATCH_FILE..."
    patch -p1 < $SCIDB4PY_PATCH_FILE
fi
popd > /dev/null

# Check if we can use generated protobuf file
if [ $SCIDB_VER == "14.12" ]; then
    echo "Using pre-compiled .proto file for scidb4py..."
    PROTO_PREGEN_PATH="scidb4py/scidb4py/pregen-proto-2.4.1/scidb14.12"
    if [ -r "$PROTO_PREGEN_PATH/$SCIDB4PY_PROTO_FILE" ]; then
        # copy pre-generated file
        cp $PROTO_PREGEN_PATH/$SCIDB4PY_PROTO_FILE $SCIDB4PY_BUILD_DIR/scidb4py
        touch $SCIDB4PY_BUILD_DIR/scidb4py/$SCIDB4PY_PROTO_FILE
    else
        # Check if we have the correct protoc version
        echo "Pre-generated file $PROTO_PREGEN_PATH/$SCIDB4PY_PROTO_FILE not found. Will use protoc"
        echo "Checking for the proper protoc..."
        PROTOC_BIN=`which protoc`
        if [ -z "$PROTOC_BIN" ]; then
            echo "protoc not found"
            exit 1
        fi
        PROTOC_VERSION=`$PROTOC_BIN --version |awk -F" " '{print $2}'`
        if [ "x$PROTOC_VERSION" != "x2.4.1" ]; then
            echo "protoc must be of version 2.4.1"
            exit 2
        fi
    fi
fi

# Do the actual install via pip
pushd $SCIDB4PY_BUILD_DIR > /dev/null
pip install .
popd > /dev/null

# generate the GUI
if [ ! -r "main_window.py" ]; then
    echo "Generating the window class via PyUIC..."
    pyuic5 sl.ui > main_window.py
fi
