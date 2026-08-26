from viewport.constraints import Constraint, constraint_from_key


def test_axis_constraints():
    assert constraint_from_key("x") is Constraint.X
    assert constraint_from_key("y") is Constraint.Y
    assert constraint_from_key("z") is Constraint.Z


def test_plane_constraints():
    assert constraint_from_key("x", shift=True) is Constraint.XY
    assert constraint_from_key("y", shift=True) is Constraint.YZ
    assert constraint_from_key("z", shift=True) is Constraint.XZ


def test_unknown_key_is_unconstrained():
    assert constraint_from_key("a") is Constraint.NONE
    assert constraint_from_key("a", shift=True) is Constraint.NONE
