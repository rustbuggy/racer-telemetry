import math
from copengl import *
import draw


class BuggyVisualization:
	def __init__(self):
		# sensors
		self.dist_left = 0.
		self.dist_left_front = 0.
		self.dist_front = 0.
		self.dist_right_front = 0.
		self.dist_right = 0.

		self.car_width = 0.11
		self.car_length = 0.175

		# calculated values?
		self.wheel_angle = 0.
		self.mc_angle = 0.
		self.mc_dist = 0.

		# default zoom is 2 meters per window width
		self.zoom = 5.

		self.stipple_pattern = 0x00FF

	def tick(self, dt):
		pass

	def render(self, w, h):
		""" w, h - window size in pixels """

		glPushAttrib(GL_ENABLE_BIT)
		glPushMatrix()

		glDisable(GL_TEXTURE_2D)
		glEnable(GL_LINE_SMOOTH)

		glMatrixMode(GL_PROJECTION)
		glLoadIdentity()
		world_w_2 = self.zoom / 2.
		world_h   = self.zoom * h / w
		#glOrtho(-w_2, w_2, -h_2, h_2, -100, 100)
		# move the world center to the bottom third of the view area
		glOrtho(-world_w_2, world_w_2, -world_h/4., world_h/4.*3., -100, 100)


		glMatrixMode(GL_MODELVIEW)
		glLoadIdentity()
		glScalef(1.,1.,-1.)

		# render sensor values
		glLineWidth(3.)

		if self.stipple_pattern & 1:
			self.stipple_pattern >>= 1
			self.stipple_pattern |= 0x8000
		else:
			self.stipple_pattern >>= 1

		glLineStipple(1, self.stipple_pattern);
		glEnable(GL_LINE_STIPPLE)

		self._render_sensor_line(0., 0., -90., self.dist_left)
		self._render_sensor_line(0., 0., -45., self.dist_left_front)
		self._render_sensor_line(0., 0.,   0., self.dist_front)
		self._render_sensor_line(0., 0.,  45., self.dist_right)
		self._render_sensor_line(0., 0.,  90., self.dist_right_front)

		# render calculated algo values
		self._render_sensor_line(0., 0., self.mc_angle, self.mc_dist, color=(0.3,0.3,1.0,0.8))

		# draw the car
		glLineWidth(1.)
		self._render_wheels()
		draw.filled_rectmid3d(0., 0., self.car_width, self.car_length, color=(0.5,0.5,0.5,0.4))


		glPopMatrix()
		glPopAttrib()

	def _render_sensor_line(self, x, y, sensor_angle, distval, color=(0.8,0.4,0.2, 1.)):
		x2, y2 = x + math.sin(math.radians(sensor_angle)) * distval, y + math.cos(math.radians(sensor_angle)) * distval
		glDisable(GL_LINE_STIPPLE)
		color_bg = list(color)
		#color_bg = (0., 0., 0., 1.)
		color_bg[-1] = 0.7
		draw.line(x, y, x2, y2, color=color_bg)
		glEnable(GL_LINE_STIPPLE)
		draw.line(x, y, x2, y2, color=color)

	def _render_wheels(self):
		x = self.car_width / 2. * .9
		y = self.car_length / 2. * .7
		wheel_w = self.car_width * .2
		wheel_h = self.car_width * .4
		wheel_color = (0.1,0.1,0.1,1.)

		# rear wheels
		draw.filled_rectmid3d(-x, -y, wheel_w, wheel_h, color=wheel_color)
		draw.filled_rectmid3d( x, -y, wheel_w, wheel_h, color=wheel_color)

		# front wheels
		glPushMatrix()
		glTranslatef(-x, y, 0.)
		glRotatef(-self.wheel_angle, 0., 0., 1.)
		draw.filled_rectmid3d(0., 0., wheel_w, wheel_h, color=wheel_color)
		glPopMatrix()

		glPushMatrix()
		glTranslatef(x, y, 0.)
		glRotatef(-self.wheel_angle, 0., 0., 1.)
		draw.filled_rectmid3d(0., 0., wheel_w, wheel_h, color=wheel_color)
		glPopMatrix()

	def event_sdl(self, event):
		pass

	def handle_controls(self, dt, keys):
		pass

	def set_sensor_values(self, dist_left, dist_left_front, dist_front, dist_right_front, dist_right):
		self.dist_left = dist_left
		self.dist_left_front = dist_left_front
		self.dist_front = dist_front
		self.dist_right_front = dist_right_front
		self.dist_right = dist_right

	def set_drivealgo_introspection_values(self, mc_angle, mc_dist):
		self.mc_angle = mc_angle
		self.mc_dist = mc_dist
		self.wheel_angle = mc_angle
