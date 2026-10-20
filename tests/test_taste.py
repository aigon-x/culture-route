from cultureroute.taste import TasteProfile


def test_like_raises_weight_and_dislike_lowers_it():
    t = TasteProfile()
    t.observe(["Ambient"], liked=True)
    assert t.weights["ambient"] > 0
    t.observe(["ambient"], liked=False)
    assert t.weights["ambient"] < 0.25


def test_weight_is_bounded():
    t = TasteProfile()
    for _ in range(20):
        t.observe(["slow"], liked=True)
    assert t.weights["slow"] == 1.0


def test_affinity_of_unknown_tags_is_zero():
    assert TasteProfile().affinity(["never-seen"]) == 0.0


def test_round_trip_json():
    t = TasteProfile(); t.observe(["science"], liked=True)
    assert TasteProfile.from_json(t.to_json()).weights == t.weights
