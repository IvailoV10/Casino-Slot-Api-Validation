import requests

import pytest

product = [
    (2,3,6),
    (1,99,99)
]

@pytest.mark.parametrize('a,b, product', product)
def test_multiplication (a, b, product):
    assert a * b == product