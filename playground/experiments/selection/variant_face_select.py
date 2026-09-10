"""AP-03 Phase 1 — Face Select (Replace-Modus, Baseline).

LMB-Click wählt die getroffene Face aus (Replace). Miss leert die Selektion.
Kein Add/Remove/Toggle (kommt in Phase 2).
"""

from playground.experiment import Experiment


class FaceSelectExperiment(Experiment):
    id = "selection"
    name = "Selection"
    variant = "Face Select (Replace)"
