import logging
#logg = logging.getLogger(__name__)
logg = logging.getLogger("main")
if __name__=="__main__":
	logging.basicConfig(level=logging.NOTSET, format="%(asctime)s %(name)s %(levelname)-5s: %(message)s")

import os
import sys
import time
import math
import datetime
import argparse
import struct
import serial
import ctypes

from sdl2 import *
from OpenGL.GL import *

from PIL import Image


import fps_counter

sys.path.append('extlib/common/python/lib')
sys.path.append('extlib/libaniplot')
sys.path.append('extlib/libcopengl')
sys.path.append('extlib/libgltext/pywrapper')

import hdlc
import gltext

from aniplot import graph_window
from aniplot import graph_renderer
from aniplot import graph_channel


parser = argparse.ArgumentParser(description="RustTelemetry", formatter_class=argparse.ArgumentDefaultsHelpFormatter)
parser.add_argument("--port", type=str, default="/dev/tty.usbserial-A8008iwL", help="usb serial port device eg. /dev/ttyUSB0")
args = parser.parse_args()



try:
	s = serial.Serial(args.port, 57600, timeout=0);
	s.flushInput()
	s.flushOutput()
except:
	logg.exception("using fake serial")
	class DummySerial:
		def read(self, n): return ""
		def write(self, data): pass
	s = DummySerial()


# header bytes
BC_TELEMETRY = 0x00
CB_MOTOR_COMMAND = 0x01


def send_packet(data):
	data = hdlc.add_checksum(data)
	data = hdlc.escape_delimit(data)
	s.write(data)


class Telemetry:
	""" Read telemetry from the given serial port. """
	def __init__(self, serial):
		self.serial = serial # opened serial port. here used for reading ONLY.
		self.parser = hdlc.HdlcChecksummed()

	def tick(self, dt):
		# read serial
		data = self.serial.read(200)
		self.parser.put(data)

		for packet in self.parser:
			header, = struct.unpack("<B", packet[:1])
			if header == BC_TELEMETRY:
				left, right, front_left, front_right = struct.unpack("<BBBB", packet[1:])
				#llog.info("l %u r %u fl %u fr %u", left, right, front_left, front_right)
				# TODO: create channels. append every sample.


class BuggyDrive:
	def __init__(self, serial):
		self.serial = serial # opened serial port. here used for sending ONLY.
		self.thrust_max = 10.
		self.thrust_min = -10.
		self.steering_max = 45. # degrees
		self.steering_min = -self.steering_max

		self.steering_max_pwm = 140.
		self.steering_min_pwm = 40.
		self.thrust_max_pwm = 135.
		self.thrust_min_pwm = 255.

		self.steering_cur = 0. # current front wheel steering pos degrees
		self.thrust_cur = 0.

		self.log_raw_data = False

	def tick(self, dt):
		# send motor commands
		steering_pwm = self._steering_to_servopwm(self.steering_cur)
		drive_pwm = self._thrust_to_motorpwm(self.thrust_cur)
		motor_command = struct.pack("<BBB", CB_MOTOR_COMMAND, steering_pwm, drive_pwm)
		self._send_packet(motor_command)

	def handle_controls(self, dt, keys):
		acceleration = 5.
		friction_deceleration = .5 # deceleration when no accelerate button is pressed
		steering_speed = 20. # degrees per second
		steering_back_speed = 20. # how fast to restore the zero-steer if no left/right button is pressed

		if keys[SDL_SCANCODE_LEFT] or keys[SDL_SCANCODE_RIGHT]:
			if keys[SDL_SCANCODE_LEFT]:
				self.steering_cur -= steering_speed * dt
			if keys[SDL_SCANCODE_RIGHT]:
				self.steering_cur += steering_speed * dt
		else:
			self.steering_cur = self._ease_linear_to(0, self.steering_cur, dt * steering_back_speed)

		if keys[SDL_SCANCODE_UP] or keys[SDL_SCANCODE_DOWN]:
			if keys[SDL_SCANCODE_UP]:
				self.thrust_cur += acceleration * dt
			if keys[SDL_SCANCODE_DOWN]:
				self.thrust_cur -= acceleration * dt
		else:
			self.thrust_cur = self._ease_linear_to(0, self.thrust_cur, dt * friction_deceleration)

		# limits

		self.steering_cur = min(self.steering_cur, self.steering_max)
		self.steering_cur = max(self.steering_cur, self.steering_min)

		self.thrust_cur = min(self.thrust_cur, self.thrust_max)
		self.thrust_cur = max(self.thrust_cur, self.thrust_min)

	def _send_packet(self, data):
		data = hdlc.add_checksum(data)
		data = hdlc.escape_delimit(data)
		if self.log_raw_data:
			logg.info("snd %02i: %s", len(data), data.encode("hex").upper())
		self.serial.write(data)

	def _ease_linear_to(self, dest, src, amount):
		if dest >= src:
			return src + amount if src + amount < dest else dest
		else:
			return src - amount if src - amount > dest else dest

	def _thrust_to_motorpwm(self, speed):
		motorpwm = self.thrust_min_pwm + (self.thrust_cur - self.thrust_min) / (self.thrust_max - self.thrust_min) * (self.thrust_max_pwm - self.thrust_min_pwm)
		assert motorpwm < 256.
		assert motorpwm > 134.
		return motorpwm

	def _steering_to_servopwm(self, angle):
		servopwm = self.steering_min_pwm + (self.steering_cur - self.steering_min) / (self.steering_max - self.steering_min) * (self.steering_max_pwm - self.steering_min_pwm)
		assert servopwm < 141.
		assert servopwm > 39.
		return servopwm


class MainWindow:
	def __init__(self, conf, graph_channels=None):
		self.conf = conf
		self._w, self._h = 0., 0.
		self.gltext = gltext.GLText(os.path.join(conf.path_data, 'font_proggy_opti_small.txt'))
		# renders graphs, grids, legend, scrollbar, border.
		self.grapher = graph_renderer.GraphRenderer(self.gltext)
		self.channels = []
		self.graph_window = None

		self.ch1 = self.create_channel(frequency=60, value_min=0., value_min_raw=-1., value_max=5., value_max_raw=1., legend="fast data")
		#self.ch2 = self.aniplot.create_channel(frequency=5, value_min=0., value_min_raw=0., value_max=3.3, value_max_raw=255., legend="slow data", color=QtGui.QColor(0, 238, 0))

	def init(self):
		self.gltext.init()
		self.grapher.setup(self.channels)
		# converts input events to smooth zoom/movement of the graph.
		self.graph_window = graph_window.GraphWindow(self, font=self.gltext, graph_renderer=self.grapher, keys=None, x=0, y=0, w=10, h=10)

	def tick(self, dt):
		t = time.time()
		self.ch1.append( math.sin(t / 0.1) )

	def render(self, window_w, window_h, fps):
		self._w, self._h = window_w, window_h
		#glClearColor(0.8,0.8,1.8,1.0)
		#glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
		##glColor(1,0,0,1)

		#glMatrixMode(GL_PROJECTION)
		#glLoadIdentity()
		z_near, z_far = 101., 100000.
		#glViewport(0, 0, self.w, self.h)
		#glOrtho(0., self.w, self.h, 0., z_near, z_far)

		#glMatrixMode(GL_MODELVIEW)
		#glLoadIdentity()
		#glScale(1., 1., -1.)

		if self.graph_window:
			w, h = window_w, window_h
			if w <= 20 or h <= 20:
				return

			self.grapher.tick()
			self.graph_window.tick()

			glClearColor(0.2, 0.2, 0.2, 1.0)
			glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

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
			self.graph_window.y = h / 2.
			self.graph_window.w = w + 2
			self.graph_window.h = h / 2. + 2

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
		return

	def gl_coordinates(self, x, y):
		""" used by graph_renderer for some unremembered reason """
		return x, self._h - y

	def create_channel(self, frequency=1000, value_min=0., value_min_raw=0., value_max=5., value_max_raw=255., legend="graph", unit="V", color=(0.5, 1., 0.5, 1.)):
		''' Returns GraphChannel object.

		    "frequency"     : sampling frequency
		    "value_min"     : is minimum real value, for example it can be in V
		    "value_min_raw" : is minimum raw value from ADC that corresponds to real "value_min"
		    "value_max"     : is maximum real value, for example it can be in V
		    "value_max_raw" : is maximum raw value from ADC that corresponds to real "value_max"

		    For example with 10 bit ADC with AREF of 3.3 V these values are: value_min=0., value_min_raw=0., value_max=3.3, value_max_raw=1023.

		    Use case:
		        plotter = AniplotWidget()
		        ch1 = plotter.create_channel(frequency=1000, value_min=0., value_min_raw=0., value_max=5., value_max_raw=255.)
		        ch2 = plotter.create_channel(frequency=500, value_min=0., value_min_raw=0., value_max=3.3, value_max_raw=1023.)
		        plotter.start()

		        while 1:
		            sample1 = some_source1.get()
		            sample2 = some_source2.get()
		            if sample1:
		                ch1.append(sample1)
		            if sample2:
		                ch2.append(sample2)

		    Data can be appended also with custom timestamp: ch1.append(sample1, time.time())
		'''
		channel = graph_channel.GraphChannel(frequency=frequency, legend=legend, unit=unit, color=color)
		channel.set_mapping(value_min=value_min, value_min_raw=value_min_raw, value_max=value_max, value_max_raw=value_max_raw)
		self.channels.append(channel)
		return channel


class Main:
	def __init__(self, conf, serial):
		self.conf = conf
		self.serial = serial
		self.w = 800
		self.h = 600
		self.keys = None

		self.buggy_drive = BuggyDrive(self.serial)
		self.telemetry = Telemetry(self.serial)
		self.mainwindow = MainWindow(conf)

		t = time.time()

		# take a screenshot every minute. but start at 10 seconds (does not work in frozen mode)
		self.autoscreenshot_period = 60.
		self.autoscreenshot_time = t + 10.
		self.fpscounter = fps_counter.FpsCounter()
		self.fps_log_period = 60.
		self.fps_log_time = t + 5.

	def _init(self):
		self._init_gl()
		self.mainwindow.init()

	def run(self):
		""" this is the entry-point """

		logg.info("initializing sdl")
		if SDL_Init(SDL_INIT_VIDEO) != 0:
			logg.error(SDL_GetError())
			return -1

		SDL_GL_SetAttribute(SDL_GL_MULTISAMPLEBUFFERS, 1);
		SDL_GL_SetAttribute(SDL_GL_MULTISAMPLESAMPLES, 4);

		logg.info("creating window")
		window = SDL_CreateWindow(b"telemetry/drive", SDL_WINDOWPOS_UNDEFINED, SDL_WINDOWPOS_UNDEFINED, self.w, self.h, SDL_WINDOW_OPENGL)
		if not window:
			logg.error(SDL_GetError())
			return -1

		logg.info("creating context for the window")
		context = SDL_GL_CreateContext(window)

		glClearColor(0., 0., 0., 1.0)
		glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

		if SDL_GL_SetSwapInterval(-1):
			logg.error(SDL_GetError())
			if SDL_GL_SetSwapInterval(1):
				logg.error("SDL_GL_SetSwapInterval: %s", SDL_GetError())
				logg.error("vsync failed completely. will munch cpu for lunch.")

		self.keys = SDL_GetKeyboardState(None)
		self._init()

		#
		# init done. start the mainloop!
		#

		logg.info("starting mainloop")
		last_t = time.time()

		event = SDL_Event()
		running = True
		while running:
			while SDL_PollEvent(ctypes.byref(event)) != 0:
				if event.type == SDL_QUIT:
					running = False

				if event.type == SDL_KEYDOWN:
					if event.key.keysym.scancode == SDL_SCANCODE_ESCAPE:
						running = False

				if event.type == SDL_WINDOWEVENT:
					if event.window.event == SDL_WINDOWEVENT_SIZE_CHANGED:
						self.w, self.h = event.window.data1, event.window.data2

				self.mainwindow.event_sdl(event)

			t = time.time()
			self._tick(t - last_t)
			last_t = t

			#glFinish()
			SDL_GL_SwapWindow(window)
			#SDL_Delay(10)

		SDL_GL_DeleteContext(context)
		SDL_DestroyWindow(window)
		SDL_Quit()
		logg.info("quit ok")

	def _init_gl(self):
		glDisable(GL_TEXTURE_2D)
		glDisable(GL_DEPTH_TEST)
		glDisable(GL_FOG)
		glDisable(GL_DITHER)
		glDisable(GL_LIGHTING)
		glShadeModel(GL_FLAT)
		glEnable(GL_BLEND)
		glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
		glEnable(GL_LINE_SMOOTH)
		glDisable(GL_LINE_STIPPLE)

	def _tick(self, dt):
		self.telemetry.tick(dt)
		self.buggy_drive.handle_controls(dt, self.keys)
		self.buggy_drive.tick(dt)
		self.mainwindow.handle_controls(dt, self.keys)
		self.mainwindow.tick(dt)
		self.fpscounter.tick(dt)

		# render frame

		glViewport(0, 0, self.w, self.h)
		self.mainwindow.render(self.w, self.h, self.fpscounter.fps)

		t = time.time()

		# just log fps.
		if self.fps_log_time < t:
			self.fps_log_time = t + self.fps_log_period
			logg.info("fps: %i", self.fpscounter.fps)

		# save screenshot if the time cas come, but only save when working from source.
		if self.autoscreenshot_time < t and not hasattr(sys, "frozen"):
			self.autoscreenshot_time = t + self.autoscreenshot_period
			self._save_screenshot("autoscreenshot_")

	def _save_screenshot(self, filename_prefix="screenshot_"):
		"""saves screenshots/filename_prefix20090404_120211_utc.png"""
		utc = time.gmtime(time.time())
		filename = filename_prefix + "%04i%02i%02i_%02i%02i%02i_utc.png" % \
				(utc.tm_year, utc.tm_mon, utc.tm_mday, utc.tm_hour, utc.tm_min, utc.tm_sec)
		logg.info("saving screenshot '%s'", filename)
		px = glReadPixels(0, 0, self.w, self.h, GL_RGB, GL_UNSIGNED_BYTE)
		im = Image.frombuffer("RGB", (self.w, self.h), px, "raw", "RGB", 0, -1)

		im.save(os.path.join(self.conf.path_screenshots, filename))


# example on how to show a message box. of course we'll need it someday!
#SDL_ShowSimpleMessageBox(SDL_MESSAGEBOX_ERROR,
#                     "Missing file",
#                     "File is missing. Please reinstall the program.",
#                     None);
class Conf: pass


def main(py_path):
	conf = Conf()
	conf.path_data = os.path.normpath( os.path.join(py_path, "data") )
	conf.path_screenshots = os.path.normpath( os.path.join(py_path, "screenshots") )
	w = Main(conf, s)
	w.run()


#if __name__=="__main__":
#	main()
#	sys.exit(w.run())
