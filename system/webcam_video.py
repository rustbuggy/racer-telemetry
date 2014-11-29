#!/usr/bin/env python2.7
#



# http://phoboslab.org/log/2009/07/uvc-camera-control-for-mac-os-x



# camera.py -- by Trevor Bentley (02/04/2011)
#
# This work is licensed under a Creative Commons Attribution 3.0 Unported License.
#
# Run from the command line on an Apple laptop running OS X 10.6, this script will
# take a single frame capture using the built-in iSight camera and save it to disk
# using three methods.
#

# PyObjC 2.2 and MachSignals
# http://comments.gmane.org/gmane.comp.python.pyobjc.devel/5581
#
# this installInterrupt doesn't do anything, because pyobjc tries to import MachSignals
# which is in an non-importable location. And it wouldn't work anyway, because MachSignals
# tries to import _machsignals, which does not exist at all.
#   AppHelper.runConsoleEventLoop(installInterrupt=True)
# so there really IS no way to get keyboard interrupts from objc to python.
#

import logging
logg = logging.getLogger(__name__)


import sys
import time
#t = time.time()

from OpenGL.GL import *

import os
import math
#print "importing objc"
import objc
#print "importing QTKit"
import QTKit

#print "importing AppKit"
from AppKit import NSApplication
from AppKit import NSApp

#print "importing NSObject"
from Foundation import NSObject
#print "importing NSTimer"
from Foundation import NSTimer
#print "importing AppHelper"
from PyObjCTools import AppHelper
#print "importing Quartz"
import Quartz
#print "importing sdl2"
from sdl2 import *

#print "importing ctypes"
#from ctypes import Structure, sizeof, pointer, c_uint32, c_uint8
import ctypes
#print "importing PIL"
from PIL import Image

#print "everything imported in %.02f seconds" % (time.time() - t)
#print


#WANTED_FPS = 60. # logitech camera depends on lighting conditions. max 5 fps at night.

import PyObjCTools.Debugging as d
d.installVerboseExceptionHandler()
#d.installPythonExceptionHandler()
objc.setVerbose(1)


# these are overriden from WebcamVideo object
#CAMERA_NAME = "Logitech Camera" # Pro 9000
CAMERA_NAME = "Built-in iSight"
CAMERA_NAME = "FaceTime HD Camera"
CAMERA_NAME = "Logitech Camera"
#WANTED_RESOLUTION = (640, 480)
WANTED_RESOLUTION = (320, 240)
#WANTED_RESOLUTION = (160, 120)


class FpsCounter:
	def __init__(self, update_interval_seconds=0.5):
		""" read self.fps for output """
		self.fps = 0.
		self.interval = update_interval_seconds
		self._counter = 0.
		self._age     = 0.
		self._last_output_age = 0.

	def tick(self, dt):
		self._age     += dt
		self._counter += 1.
		if self._age > self.interval:
			self.fps = self._counter / self._age
			self._age     = 0.
			self._counter = 0.
			print "camera fps: %.1f" % self.fps


class MyAppDelegate(NSObject):
	pass

class NSWebcamCapture(NSObject):
	def init(self):
		self = super(NSWebcamCapture, self).init()
		if self is None:
			return None

		self.session = None
		self.frame_count = 0

		self._last_pic = None
		self.prev_time = 0.

		self.fps_counter = FpsCounter(5.)

		return self

	def captureOutput_didOutputVideoFrame_withSampleBuffer_fromConnection_(
			self, captureOutput, videoFrame, sampleBuffer, connection):

		t = t0 = time.time()
		if t == self.prev_time:
			print "PREV_TIME %f time %f" % (self.prev_time, t)
			t += 0.00001

		#print "got frame: %.2f" % time.time()
		self.frame_count += 1
		self.fps_counter.tick(t - self.prev_time)

		image_len = WANTED_RESOLUTION[0] * WANTED_RESOLUTION[1] * 4
		bitbufbytes = ctypes.string_at(sampleBuffer.bytesForAllSamples(), image_len)

		if 0 and self.frame_count == 5:
			print "saving image"

			pixels = bitbufbytes

			#    img = Image.open(self._default_image)
			#img = open(self._default_image, "rb").read()
			#pilimg = Image.open(self._default_image)
			img = Image.frombuffer('RGBA', WANTED_RESOLUTION, pixels, 'raw', 'BGRA', 0, 1)
			#img = Image.frombuffer('RGBX', WANTED_RESOLUTION, pixels, 'raw', 'RGBX', 0, 1)
			img2 = img.save("temp_delme.jpg", quality=90)

			if 0:
				 # write slot_nr onto image

				 draw     = ImageDraw.Draw(pilimg)
				 iw, ih   = pilimg.size
				 size_dpi = int(ih / 96. * 72 * .7 * 2.0)
				 font     = ImageFont.truetype("arial.ttf", size_dpi)
				 txt      = str(slot_num)
				 w, h     = font.getsize(txt)
				 x, y     = (iw - w) / 2., (ih - h) / 2.

				 draw.text((x+2, y+2), txt, font=font, fill=(0,0,0))
				 draw.text((x, y), txt, font=font, fill=(255,50,50))

				 img = pilimg.save("temp_delme.jpg", quality=20)

		t1 = time.time()
		self._last_pic = ("pic", t, WANTED_RESOLUTION, bitbufbytes)

		self.prev_time = t

	def get_pic(self):
		pic = self._last_pic
		self._last_pic = None
		return pic

	def startImageCapture(self, sender):
		print "searching for camera named '%s'" % CAMERA_NAME
		# get a list of connected QTCaptureDevice instances
		devices = QTKit.QTCaptureDevice.inputDevicesWithMediaType_(QTKit.QTMediaTypeVideo)
		for cam in devices:
			print "  found cam:", cam

		# find the camera we are looking for
		dev = None
		for cam in devices:
			if str(cam) == CAMERA_NAME or not CAMERA_NAME:
				dev = cam
				break
		if not dev:
			print "camera not found. exiting."
			return

		print "supported device attributes:"
		print dev.deviceAttributes()
		for a in dev.deviceAttributes():
			print " ", a

		print "opening '%s'" % dev
		# - (BOOL)open:(NSError **)errorPtr
		error = None
		if not dev.open_(error):
			print "Couldn't open capture device."
			return

		# Create an input instance with the device we found.
		input_ = QTKit.QTCaptureDeviceInput.alloc().initWithDevice_(dev)

		# Create a QT Capture session
		self.session = QTKit.QTCaptureSession.alloc().init()

		if not self.session.addInput_error_(input_, error):
			print "Couldn't add input device."
			return

		print "supported device attributes:"
		print dev.deviceAttributes()
		for a in dev.deviceAttributes():
			print " ", a

		# Create an output instance with a delegate for callbacks and add to session
		output = QTKit.QTCaptureDecompressedVideoOutput.alloc().init()

		# logitech 9000 available formats:
		#   kCVPixelFormatType_32BGRA
		# unavailable formats:
		#   kCVPixelFormatType_24RGB
		#   kCVPixelFormatType_32RGBA
		# http://markmail.org/message/ytlakzsqtzc3ggnr

		# trunk/pyobjc/pyobjc-framework-Quartz/PyObjCTest/test_cvpixelbuffer.py
		output.setPixelBufferAttributes_({Quartz.kCVPixelBufferHeightKey: WANTED_RESOLUTION[1],
										  Quartz.kCVPixelBufferWidthKey: WANTED_RESOLUTION[0],
										  Quartz.kCVPixelBufferPixelFormatTypeKey: Quartz.kCVPixelFormatType_32BGRA})

		output.setDelegate_(self)
		if not self.session.addOutput_error_(output, error):
			print "Failed to add output delegate."
			return

		# Start the capture
		print "Initiating capture..."
		self.session.startRunning()
		return dev

	def stop(self):
		if self.session:
			self.session.stopRunning()


class WebcamVideo:
	def __init__(self):
		self.capturer = None

	def init(self, camera_name, wanted_resolution=(640,480)):
		if camera_name:
			global CAMERA_NAME
			global WANTED_RESOLUTION
			CAMERA_NAME = camera_name
			WANTED_RESOLUTION = wanted_resolution
			#WANTED_RESOLUTION = (640, 480)
			#WANTED_RESOLUTION = (320, 240)
			#WANTED_RESOLUTION = (160, 120)
			logg.info("NSWebcamCapture.alloc().init()")
			self.capturer = NSWebcamCapture.alloc().init()

	def start(self):
		logg.info("startImageCapture")
		# Turn on the camera and start the capture
		if not self.capturer.startImageCapture(None):
			logg.error("opening camera failed")
			sys.exit(1)

	def get_pic(self):
		"""Return image. or None if no new image yet from the last call"""
		if self.capturer:
			picdata = self.capturer.get_pic()
			if picdata:
				_, timestamp, resolution, bitbufbytes = picdata
				return timestamp, resolution, bitbufbytes
			else:
				return None
		else:
			return None

	def stop(self):
		if self.capturer:
			self.capturer.stop()
