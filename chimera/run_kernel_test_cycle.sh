#!/bin/bash

# Script to automate the test cycle for setup_surface_kernel_py.py and cbuild

# Exit immediately if a command exits with a non-zero status.
set -e

# Get the directory where this script is located (chimera/)
# and cd to the project root (one level up)
SCRIPT_PARENT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." &> /dev/null && pwd)"
cd "$SCRIPT_PARENT_DIR" || exit 1

echo "--- Starting Kernel Test Cycle (from $PWD) ---"

echo ""
echo "STEP 1: Pulling latest changes from git..."
git pull

echo ""
echo "STEP 2: Running setup_surface_kernel_py.py generator (chimera/py/setup_surface_kernel_py.py)..."
python chimera/py/setup_surface_kernel_py.py --kernel-version "6.8.1" --surface-archive-tag "v6.8.1-arch1" --output-name "linux-surface-generated" --force # Path relative to project root

echo ""
echo "STEP 3: Changing to cports directory (chimera/cports/)..."
cd chimera/cports # Path relative to project root

echo ""
echo "STEP 4: Running cbuild prepare-upgrade to update checksums..."
# We don't use set -e for this one as it's expected to "fail" if checksum is a placeholder
set +e
./cbuild prepare-upgrade main/linux-surface-generated
PREPARE_UPGRADE_STATUS=$?
set -e

if [ $PREPARE_UPGRADE_STATUS -ne 0 ]; then
    echo "INFO: './cbuild prepare-upgrade' exited with status $PREPARE_UPGRADE_STATUS."
    echo "      This is expected if the checksum was a placeholder and got updated."
    echo "      If it was another error, please check the output above."
fi

echo ""
echo "STEP 5: Attempting to build the package with './cbuild pkg'..."
./cbuild pkg main/linux-surface-generated

echo ""
echo "--- Kernel Test Cycle Complete ---"
echo "Check the output above for any build errors from cbuild."

# Return to the project root directory
cd "$SCRIPT_PARENT_DIR"