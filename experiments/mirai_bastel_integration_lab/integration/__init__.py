"""Integrations-Viewport des Integration Labs (pyglet, interaktiv).

Diese Schicht ist bewusst dünn: Sie bündelt `CoreRenderBinding`
(adapter/core_to_render) mit der V0.2-Render-Klassik (RenderMesh,
PygletStore, ShaderProgram) und der Lab-Kamera. Sie gehört nicht zu
`src/core` und ist kein Production-Viewport.
"""

from .lab_viewport import IntegrationLabWindow

__all__ = ["IntegrationLabWindow"]