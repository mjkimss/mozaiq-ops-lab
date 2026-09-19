"""The business result must not drift, and the heatmap's base cell must equal it. Uses the committed OSRM cache (no network)."""
from src.make_outputs import heatmap_breakeven
from src.sensitivity import solve_with


def test_base_business_result_is_outsource_first():
    assert solve_with("current")["hub_names"] == []                         # 0 hubs: everything outsourced
    assert solve_with("expansion")["hub_names"] == ["Hongcheon", "Jeju City"]


def test_heatmap_base_cell_equals_the_business_result(tmp_path):
    out = tmp_path / "h.png"
    grids = heatmap_breakeven([1.0, 2.0], [1.0, 0.5], out)                   # tiny grid; base assumptions are the top-left cell
    assert out.exists() and out.stat().st_size > 10_000
    assert grids["current"][0][0] == 0 and grids["expansion"][0][0] == 2
    assert grids["expansion"][0][1] >= grids["expansion"][0][0]              # a dearer vendor never opens fewer hubs here


def test_static_map_png_is_written(tmp_path):
    from src.hub_map import hub_map_png
    res = solve_with("current")
    out = tmp_path / "m.png"
    hub_map_png(res["inst"], res["exact"]["assign"], "title", "subtitle", out)
    assert out.exists() and out.stat().st_size > 20_000
