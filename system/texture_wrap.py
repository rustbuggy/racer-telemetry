"""
opengl texture object wrapper

    def upload_image(self, imagestring, rgb=GL_RGBA)
    def draw(self, x, y, z=0., w=None, h=None, flipy=False)

"""

from OpenGL.GL import *


class TextureWrap:
    """
    opengl texture wrapper
    """

    def __init__(self, w, h):
        self.w = w
        self.h = h
        self.texture_id = None

    def upload_image(self, imagestring, rgb=GL_RGBA):
        """
        using PIL:

            image = Image.open("hello.bmp")
            image = image.convert('RGBA') # TODO: this is necessary?
            #imagestring = image.tostring("raw", "RGBX", 0, -1) # -1 - swap y
            imagestring = image.tostring("raw", "RGBA", 0)
        """
        if self.texture_id is None:
            self.texture_id = glGenTextures(1)
            glBindTexture(GL_TEXTURE_2D, self.texture_id)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP)
            glTexParameterf(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST)
            glTexParameterf(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
        else:
            glBindTexture(GL_TEXTURE_2D, self.texture_id)

        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, self.w, self.h, 0, rgb, GL_UNSIGNED_BYTE, imagestring)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)

        # old notes: if use_mipmaps:
        #gluBuild2DMipmaps(GL_TEXTURE_2D, GL_RGBA8, self.w, self.h, rgb, GL_UNSIGNED_BYTE, imagestring)
        #glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR_MIPMAP_LINEAR)
        #self._gltexsubimage2d(GL_TEXTURE_2D, 0, s.pixpos[0], s.pixpos[1], \
        #                      iw, ih, rgb, GL_UNSIGNED_BYTE, imagebuffer)

    def draw(self, x, y, z=0., w=None, h=None, flipy=False):
        if self.texture_id == None: return
        if w == None: w = self.w
        if h == None: h = self.h
        glEnable(GL_TEXTURE_2D)
        glBindTexture(GL_TEXTURE_2D, self.texture_id)

        glBegin(GL_QUADS)

        if flipy:
            glTexCoord2f(0., 1.)
            glVertex3f(x, y, z)
            glTexCoord2f(1., 1.)
            glVertex3f(x + w, y, z)
            glTexCoord2f(1., 0.)
            glVertex3f(x + w, y + h, z)
            glTexCoord2f(0., 0.)
            glVertex3f(x, y + h, z)
        else:
            glTexCoord2f(0., 0.)
            glVertex3f(x, y, z)
            glTexCoord2f(1., 0.)
            glVertex3f(x + w, y, z)
            glTexCoord2f(1., 1.)
            glVertex3f(x + w, y + h, z)
            glTexCoord2f(0., 1.)
            glVertex3f(x, y + h, z)

        glEnd()
