"""Pruefe OpenGL-Kontext, Shader-Kompilierung und Rendering."""
import math
import pyglet
from pyglet import gl
from pyglet.graphics import shader

print("Creating window...")
w = pyglet.window.Window(320, 240, visible=True, resizable=True)
print(f"width={w.width}, height={w.height}")

# OpenGL-Info
print(f"GL_VERSION: {gl.gl_info.get_version()}")
print(f"GL_RENDERER: {gl.gl_info.get_renderer()}")

# Shader-Kompilierung testen
VERT_SRC = """
#version 330 core
in vec3 position;
uniform mat4 u_mvp;
void main() {
    gl_Position = u_mvp * vec4(position, 1.0);
}
"""
FRAG_SRC = """
#version 330 core
out vec4 out_color;
void main() {
    out_color = vec4(1.0, 0.0, 0.0, 1.0);
}
"""
print("Compiling shaders...")
try:
    prog = shader.ShaderProgram(
        shader.Shader(VERT_SRC, "vertex"),
        shader.Shader(FRAG_SRC, "fragment"),
    )
    print(f"Shader program ID: {prog.ID}")
    
    # Ein rotes Dreieck zeichnen
    vlist = prog.vertex_list(3, gl.GL_TRIANGLES,
        position=("f", [0.0, 0.5, 0.0, -0.5, -0.5, 0.0, 0.5, -0.5, 0.0]))
    
    print("Drawing red triangle...")
    w.clear()
    prog.use()
    # Einfache MVP Matrix (Identity)
    identity = [1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0]
    prog["u_mvp"] = identity
    vlist.draw(gl.GL_TRIANGLES)
    gl.glFlush()
    gl.glFinish()
    w.flip()
    
    # Pixel lesen
    buf = (gl.GLubyte * (w.width * w.height * 3))()
    gl.glReadBuffer(gl.GL_BACK)
    gl.glReadPixels(0, 0, w.width, w.height, gl.GL_RGB, gl.GL_UNSIGNED_BYTE, buf)
    nonzero = sum(1 for i in range(0, len(buf), 3) if buf[i] != 0 or buf[i+1] != 0 or buf[i+2] != 0)
    total = w.width * w.height
    print(f"Red triangle pixels: {nonzero}/{total} ({100.0*nonzero/total:.1f}%)")
    
except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()

w.close()
print("OK")

