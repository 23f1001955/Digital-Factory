import pytest
from cli.wizard import slugify


def test_slugify():
    assert slugify("Hello World") == "hello-world"
    assert slugify("  Spaces  ") == "spaces"
    assert slugify("Special!@#Chars") == "special-chars"
    assert slugify("") == ""
