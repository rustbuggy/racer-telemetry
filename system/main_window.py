import logging
logg = logging.getLogger(__name__)

import os
from sdl2 import *
from OpenGL.GL import *

import gltext
from aniplot import graph_window
from aniplot import graph_renderer

import buggy_visualization


class MainWindow:
	def __init__(self, conf, telemetry_channels=None, graph_channels=None):
		self.conf = conf
		self.telemetry_channels = telemetry_channels
		self.graph_channels = graph_channels
		self._w, self._h = 0., 0.
		self.gltext = gltext.GLText(os.path.join(conf.path_data, 'font_proggy_opti_small.txt'))
		# renders graphs, grids, legend, scrollbar, border.
		self.grapher = graph_renderer.GraphRenderer(self.gltext)
		self.graph_window = None

		self.buggy_vis = buggy_visualization.BuggyVisualization()

	def init(self):
		self.gltext.init()
		self.grapher.setup(self.graph_channels)
		# converts input events to smooth zoom/movement of the graph.
		self.graph_window = graph_window.GraphWindow(self, font=self.gltext, graph_renderer=self.grapher, keys=None, x=0, y=0, w=10, h=10)

	def tick(self, dt):
		#self.buggy_vis.set_sensor_values(dist_left, dist_left_front, dist_front, dist_right_front, dist_right)

		if self.telemetry_channels and self.telemetry_channels[0].size():
			minv, maxv, left        = self.telemetry_channels[0].get(-1)
			minv, maxv, right       = self.telemetry_channels[1].get(-1)
			minv, maxv, left_front  = self.telemetry_channels[2].get(-1)
			minv, maxv, right_front = self.telemetry_channels[3].get(-1)
			minv, maxv, front       = self.telemetry_channels[4].get(-1)

			minv, maxv, mc_angle    = self.telemetry_channels[7].get(-1)
			minv, maxv, mc_dist     = self.telemetry_channels[8].get(-1)
			self.buggy_vis.set_sensor_values(left, left_front, front, right, right_front)
			self.buggy_vis.set_drivealgo_introspection_values(mc_angle, mc_dist)
		else:
			self.buggy_vis.set_sensor_values(0.8, 0.5, 0.2, 0.6, 0.9)
			self.buggy_vis.set_drivealgo_introspection_values(-10, 1.)

		self.buggy_vis.tick(dt)

	def render(self, window_w, window_h, fps):
		self._w, self._h = window_w, window_h

		w, h = window_w, window_h
		if w <= 20 or h <= 20:
			return

		self.grapher.tick()
		self.graph_window.tick()

		#glClearColor(0.3, 0.3, 0.3, 1.0)
		#glClearColor(0.2, 0.2, 0.2, 1.0)
		glClearColor(.25, .25, .25, 1.0)
		glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)


		# render buggy visualization window
		#glDisable(GL_DEPTH_TEST)
		#glDisable(GL_LIGHTING)

		glViewport(0, int(h / 2.), w, int(h / 2.))
		self.buggy_vis.render(w, int(h/2.))



		# render graph window


		glViewport(0, 0, w, h)

		glMatrixMode(GL_PROJECTION)
		glLoadIdentity()
		glOrtho(0., w, h, 0., -100, 100)

		glDisable(GL_DEPTH_TEST)
		glDisable(GL_TEXTURE_2D)
		glDisable(GL_LIGHTING)

		glMatrixMode(GL_MODELVIEW)
		glLoadIdentity()
		glScalef(1.,1.,-1.)

		self.graph_window.x = -1
		self.graph_window.y = int(h / 2.)
		self.graph_window.w = w + 2
		self.graph_window.h = int(h / 2.) + 2

		# render 2d objects

		glDisable(GL_DEPTH_TEST)
		glDisable(GL_TEXTURE_2D)

		self.graph_window.render()

		glEnable(GL_TEXTURE_2D)
		self.gltext.drawbr("fps: %.0f" % fps, w, h, fgcolor = (.9, .9, .9, 1.), bgcolor = (0.3, 0.3, 0.3, .0))
		self.gltext.drawbm("usage: arrows, shift, mouse", w/2, h-3, fgcolor = (.5, .5, .5, 1.), bgcolor = (0., 0., 0., .0))

	def handle_controls(self, dt, keys):
		d = 1. * dt
		if keys[SDL_SCANCODE_LSHIFT] or keys[SDL_SCANCODE_RSHIFT]:
			if keys[SDL_SCANCODE_LEFT]:  self.graph_window.zoom_out(d, 0.)
			if keys[SDL_SCANCODE_RIGHT]: self.graph_window.zoom_in(d, 0.)
			if keys[SDL_SCANCODE_UP]:    self.graph_window.zoom_in(0., d)
			if keys[SDL_SCANCODE_DOWN]:  self.graph_window.zoom_out(0., d)
		else:
			if keys[SDL_SCANCODE_LEFT]:  self.graph_window.move_by_ratio(-d, 0.)
			if keys[SDL_SCANCODE_RIGHT]: self.graph_window.move_by_ratio(d, 0.)
			if keys[SDL_SCANCODE_UP]:    self.graph_window.move_by_ratio(0., -d)
			if keys[SDL_SCANCODE_DOWN]:  self.graph_window.move_by_ratio(0., d)

	def event_sdl(self, event):
		pass

	def gl_coordinates(self, x, y):
		""" used by graph_renderer for some unremembered reason """
		return x, self._h - y
