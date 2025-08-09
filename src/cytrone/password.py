#!/usr/bin/python3

#############################################################################
# Classes related to the CyTrONE password management
#############################################################################

import getpass
import sys

# Used by the passlib-based implementation (default, RECOMMENDED)
from passlib.hash import pbkdf2_sha256

# Used by the built-in implementation (NOT recommended)
import hashlib
import random

from . import config

class Password:

    @classmethod
    def encode(cls, raw_password: str) -> str:
        """
        Encodes a given raw password using pbkdf2_sha256.
        """
        # The insecure implementation has been removed. We always use passlib.
        return pbkdf2_sha256.hash(raw_password)

    @classmethod
    def verify(cls, raw_password: str, enc_password: str) -> bool:
        """
        Verifies a given raw password against an encrypted one.
        """
        # The insecure implementation has been removed. We always use passlib.
        try:
            return pbkdf2_sha256.verify(raw_password, enc_password)
        except (ValueError, TypeError):
            # Passlib can raise errors on malformed hashes
            return False

def main():
    """
    Command-line tool to generate an encoded password for use in the database.
    """
    print("* INFO: Password manager for CyTrONE: Please follow the instructions below.")
    try:
        raw_password = getpass.getpass("* INFO: Enter the password to be encoded: ")
        if not raw_password:
            print("* ERROR: Empty passwords are not considered valid, please retry.")
            sys.exit(1)

        raw_password2 = getpass.getpass("* INFO: Retype the password to be encoded: ")
        if raw_password == raw_password2:
            enc_password = Password.encode(raw_password)
            print("\n* INFO: Copy the string displayed below into the password database:")
            print(enc_password)
        else:
            print("\n* ERROR: Passwords do not match, please retry.")
            sys.exit(1)
    except KeyboardInterrupt:
        print("\n* INFO: Password entry cancelled.")
        sys.exit(1)


#############################################################################
# Run
if __name__ == "__main__":
    main()
