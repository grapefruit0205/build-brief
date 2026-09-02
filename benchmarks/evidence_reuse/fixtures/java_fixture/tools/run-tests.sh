#!/bin/sh
set -eu

rm -rf build
mkdir -p build
javac -d build src/App.java src/Shared.java src/Config.java tests/AppTest.java
java -cp build AppTest
