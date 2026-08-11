"""Imports a folder that is not on this machine until this import fetches it.

The declaration a directory above says which repository holds it and which
version to take, so there is nothing to install and nothing to call here either.
The folder's own modules import each other as though the interpreter ran from
inside the folder, which is as true of a folder fetched from a repository as of
one sitting in this one.
"""

from packagify.identifiers.checksum import valid

CARDS = ["4137 8947 1175 5904", "4137 8947 1175 5905"]

for card in CARDS:
    print(f"{card}: {'valid' if valid(card) else 'invalid'}")
