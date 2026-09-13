"""Tweak Lab — four activation variants for artist comparison."""

from playground.experiments.tweak.variant_1_hold_key import TweakV1HoldKey
from playground.experiments.tweak.variant_2_silo import TweakV2Silo
from playground.experiments.tweak.variant_3_hold_click import TweakV3HoldClick
from playground.experiments.tweak.variant_4_hold_ctrl import TweakV4HoldCtrl

__all__ = [
    "TweakV1HoldKey",
    "TweakV2Silo",
    "TweakV3HoldClick",
    "TweakV4HoldCtrl",
]
