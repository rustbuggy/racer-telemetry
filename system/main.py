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

sys.path.append('extlib/common/python/lib')
sys.path.append('extlib/libaniplot')
sys.path.append('extlib/libcopengl')
sys.path.append('extlib/libgltext/pywrapper')

import hdlc
import fps_counter

import buggy_drive
import main_window
import telemetry_stream


parser = argparse.ArgumentParser(description="RustTelemetry", formatter_class=argparse.ArgumentDefaultsHelpFormatter)
parser.add_argument("--port", type=str, default="/dev/tty.usbserial-A8008iwL", help="usb serial port device eg. /dev/ttyUSB0")
args = parser.parse_args()



try:
	s = serial.Serial(args.port, 57600, timeout=0);
	s.flushInput()
	s.flushOutput()
	g_fake_serial = False
except:
	logg.exception("using fake serial and fake telemetry")
	class DummySerial:
		def read(self, n): return ""
		def write(self, data): pass
	s = DummySerial()
	g_fake_serial = True


def int16_to_float(int16):
    return int16 / 32768.


class Main:
	def __init__(self, conf, serial):
		self.conf = conf
		self.serial = serial
		self.w = 800
		self.h = 600
		self.keys = None
		self.joystick = None

		self.buggy_drive = buggy_drive.BuggyDrive(conf, serial)
		self.telemetry = telemetry_stream.TelemetryStream(self.serial, fake_telemetry=g_fake_serial)
		self.mainwindow = main_window.MainWindow(conf, self.telemetry, self.telemetry.get_telemetry_channels(), self.telemetry.get_graphing_telemetry_channels())

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

	def _open_joystick(self, joystick_index):
		n = SDL_NumJoysticks()
		logg.info("num joysticks: %u" % (n))
		if n:
			for i in range(n):
				logg.info("  %s%s" % (SDL_JoystickNameForIndex(i), " (gamecontroller)"*SDL_IsGameController(i)))

			#j = SDL_GameControllerOpen(self.conf.joystick_index)
			#if not j:
			#    print("Could not open gamecontroller %i: %s" % (i, SDL_GetError()));

			joy = SDL_JoystickOpen(self.conf.joystick_index)

			if joy:
				logg.info("")
				logg.info("opened joystick %i (%s)" % (joystick_index, SDL_JoystickName(joy)))
				logg.info("  num axes   : %d" % SDL_JoystickNumAxes(joy))
				logg.info("  num buttons: %d" % SDL_JoystickNumButtons(joy))
				logg.info("  num balls  : %d" % SDL_JoystickNumBalls(joy))
				logg.info("")
			else:
				logg.info("Could not open Joystick %i: %s" % (self.conf.joystick_index, SDL_GetError()))

			return joy
		else:
			return None

	def run(self):
		""" this is the entry-point """

		logg.info("initializing sdl")
		if SDL_Init(SDL_INIT_VIDEO|SDL_INIT_JOYSTICK) != 0:
			logg.error(SDL_GetError())
			return -1

		self.joystick = self._open_joystick(self.conf.joystick_index)

		SDL_GL_SetAttribute(SDL_GL_MULTISAMPLEBUFFERS, 1);
		SDL_GL_SetAttribute(SDL_GL_MULTISAMPLESAMPLES, 4);

		logg.info("creating window")
		window = SDL_CreateWindow(b"telemetry/drive", SDL_WINDOWPOS_UNDEFINED,
		        SDL_WINDOWPOS_UNDEFINED, self.w, self.h, SDL_WINDOW_OPENGL|SDL_WINDOW_RESIZABLE)

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
				self.buggy_drive.event_sdl(event)

			if running:
				t = time.time()
				self._tick(t - last_t)
				last_t = t

				#glFinish()
				SDL_GL_SwapWindow(window)
				#SDL_Delay(10)

		self.mainwindow.stop()
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
		self.mainwindow.tick(dt, self.telemetry.get_packet_count())
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


def main(py_path):
	class Conf: pass
	c = Conf()

	c.path_data = os.path.normpath( os.path.join(py_path, "data") )
	c.path_screenshots = os.path.normpath( os.path.join(py_path, "screenshots") )
	c.camera_name = "Logitech Camera"
	c.camera_resolution = (640, 480)

	c.joystick_index = 0
	c.joystick_roll_axis = 0
	c.joystick_pitch_axis = 1

	c.joystick_b_strafe_left = 13
	c.joystick_b_strafe_right = 14
	c.joystick_b_move_forward = 11
	c.joystick_b_move_backward = 12

	w = Main(c, s)
	w.run()


#if __name__=="__main__":
#	main()
#	sys.exit(w.run())
