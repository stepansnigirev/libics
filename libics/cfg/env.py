# System Imports
import inspect
import os


###############################################################################
# Package metadata
###############################################################################


LIBICS_VERSION_MAJOR = 0
LIBICS_VERSION_MINOR = 0
LIBICS_VERSION_DEV = "dev"
LIBICS_VERSION = (
    str(LIBICS_VERSION_MAJOR) + "."
    + str(LIBICS_VERSION_MINOR)
    + LIBICS_VERSION_DEV
)


###############################################################################
# Directories
###############################################################################


DIR_SRCROOT = os.path.dirname(os.path.dirname(os.path.abspath(
    inspect.getfile(inspect.currentframe())
)))
DIR_PKGROOT = os.path.dirname(DIR_SRCROOT)
DIR_USER = os.environ["USERPROFILE"]
DIR_DOCUMENTS = os.path.join(DIR_USER, "Documents")


###############################################################################
# File format
###############################################################################


FORMAT_JSON_INDENT = 4
