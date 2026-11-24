"""Small scorer and frontier oracles, using no measured traces."""
from dataclasses import replace
from pathlib import Path
import sys

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from edge_inference.scripts.run_offloading_experiments import descriptive, sim
from edge_inference.scripts.plot_offloading_results import frontier


def test_descriptive_matches_v1_without_mutating_coverage():
    box=sim.Detection((0,0,4,4),'crack',1.)
    false=sim.Detection((5,5,9,9),'crack',.9)
    predictions={'x':[false,replace(box,confidence=.8)]}
    refs={'x':sim.ReferenceFrame(10,10,(box,),complete=False)}
    d=descriptive(predictions,refs)
    assert not refs['x'].complete and sim.evaluate(predictions,refs).map50 is None
    # One higher scoring false detection, then one exact match at every IoU.
    assert d['map50']==d['map50_95']==pytest.approx(.5)
    assert d['per_class']['crack']['recall']==1
    assert d['per_class']['exposed_bar']['ap50'] is None
    # On synthetic exhaustive annotations the separate statistic agrees with v1.
    strict=sim.evaluate(predictions,{'x':replace(refs['x'],complete=True)})
    assert d['map50']==strict.map50 and d['map50_95']==strict.map50_95


def test_frontier_rejects_ties_and_dominated_points():
    assert frontier([(1,.2),(1,.3),(1,.3),(2,.3),(3,.4)])==[(1,.3),(3,.4)]
