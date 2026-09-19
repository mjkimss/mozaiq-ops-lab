import numpy as np

from src.geo import haversine_km


def test_zero_distance():
    assert haversine_km(37.5, 127.0, 37.5, 127.0) == 0


def test_one_degree_of_longitude_on_the_equator():
    # 2 * pi * R / 360 = 111.195 km with R = 6371.0088
    assert abs(haversine_km(0, 0, 0, 1) - 111.195) < 0.01


def test_seoul_to_busan():
    # City-centre to city-centre, straight line is about 325 km (road is longer, which is v2's point)
    assert 320 < haversine_km(37.5665, 126.9780, 35.1796, 129.0756) < 330


def test_symmetric_and_broadcasts():
    a = haversine_km(np.array([37.0, 35.0]), np.array([127.0, 129.0]), 36.0, 128.0)
    b = haversine_km(36.0, 128.0, np.array([37.0, 35.0]), np.array([127.0, 129.0]))
    assert a.shape == (2,) and np.allclose(a, b)
