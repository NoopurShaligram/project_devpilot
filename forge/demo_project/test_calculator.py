from calculator import add, multiply


def test_add_positive_numbers():
    assert add(2, 3) == 5


def test_add_negative_number():
    assert add(-2, 3) == 1


def test_multiply():
    assert multiply(4, 5) == 20
