import pytest

from datos.dga.fetch_caudales import (
    Comunas,
    aggregate,
    clip_line,
    dp_simplify,
    join_lines,
    rio_name,
    river_key,
)

SQUARE = [[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]]
HOLE = [[4, 4], [6, 4], [6, 6], [4, 6], [4, 4]]
COMUNAS = Comunas(
    [
        {
            "properties": {"codigo": "A"},
            "geometry": {"type": "Polygon", "coordinates": [SQUARE, HOLE]},
        },
        {
            "properties": {"codigo": "B"},
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[20, 0], [30, 0], [30, 10], [20, 10]]],
            },
        },
    ]
)


def test_point_in_polygon_respects_holes_and_bounds():
    assert COMUNAS.code_at(1, 1) == "A"
    assert COMUNAS.code_at(25, 5) == "B"
    assert COMUNAS.code_at(5, 5) is None  # inside the hole
    assert COMUNAS.code_at(15, 5) is None


def months(year, n, value):
    return {(year, m): value for m in range(1, n + 1)}


def test_aggregate_valid_years_and_indicators():
    data = {}
    for y in range(1980, 2010):
        data.update(months(y, 12, 10.0))
    for y in range(2010, 2014):
        data.update(months(y, 12, 5.0))
    data.update(months(2014, 9, 99.0))  # 9 months: not a valid year
    agg = aggregate(data)
    assert agg["annual"][1980] == 10.0 and 2014 not in agg["annual"]
    assert agg["valid_years"] == 34 and agg["valid_years_drought"] == 4
    assert agg["base"] == 10.0 and agg["sequia"] == 5.0 and agg["cambio"] == -50.0
    assert len(agg["regime"]) == 12 and agg["cv"] > 0


def test_aggregate_base_needs_ten_years_and_ignores_out_of_period():
    data = {}
    for y in range(2001, 2010):
        data.update(months(y, 12, 1.0))
    data.update(months(2010, 12, 2.0))
    data.update(months(2018, 12, 500.0))  # outside 1980-2017
    agg = aggregate(data)
    assert agg["base"] is None and agg["cambio"] is None
    assert 2018 not in agg["annual"]


@pytest.mark.parametrize(
    "station, expected",
    [
        ("Rio Maipo En El Manzano", "Río Maipo"),
        ("Estero Arrayan En La Montosa", "Estero Arrayán"),
        ("Rio Mapocho Antes Junta Estero Arrayan", "Río Mapocho"),
        ("Rio Angostura En Valdivia De Paine", "Río Angostura"),
        ("Estero Puangue en Boqueron", "Estero Puangue"),
    ],
)
def test_rio_name(station, expected):
    assert rio_name(station) == expected


def test_river_key_ignores_accents_case_and_rio_prefix():
    assert river_key("Río Maipo") == river_key("RIO maipo") == "maipo"
    assert river_key("Estero Arrayán") == "esteroarrayan"


def test_join_lines_keeps_direction_and_clip_splits_outside_parts():
    joined = join_lines([[(5, 5), (8, 8)], [(1, 1), (5, 5)], [(50, 50), (51, 51)]])
    assert [(1, 1), (5, 5), (8, 8)] in joined and len(joined) == 2
    runs = clip_line([(1, 1), (2, 2), (15, 5), (16, 5), (22, 5), (24, 5)], COMUNAS)
    assert runs == [[(1, 1), (2, 2), (15, 5)], [(22, 5), (24, 5)]]


def test_dp_simplify_drops_collinear_points():
    line = [(0, 0), (1, 0.0001), (2, 0), (3, 5)]
    assert dp_simplify(line, 0.001) == [(0, 0), (2, 0), (3, 5)]
