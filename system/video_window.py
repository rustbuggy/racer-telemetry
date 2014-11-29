import logging
logg = logging.getLogger(__name__)

from picpack import picpack_reader
import texture_wrap

import webcam_video
import pic_mem

from copengl import *


class VideoWindow:
	def __init__(self, conf):
		self.conf = conf
		self.webcam_video = webcam_video.WebcamVideo()
		self.teximg = None # texture_wrap.TextureWrap()

		self.pic_mem = pic_mem.PicMem()

		# show this image from history
		self.visible_telemetry_sample = -1
		self.telemetry_sample_num_last = None

	def set_visible_telemetry_sample(self, telemetry_sample_num):
		self.visible_telemetry_sample = telemetry_sample_num
		if self.teximg:
			bitbufbytes = self.pic_mem.get_by_timestamp(telemetry_sample_num)
			if bitbufbytes:
				self.teximg.upload_image(bitbufbytes, rgb=GL_BGRA)

	def tick(self, telemetry_sample_num):
		if telemetry_sample_num != self.telemetry_sample_num_last:
			self.telemetry_sample_num_last = telemetry_sample_num

			web_pic_struct = self.webcam_video.get_pic()
			if web_pic_struct:
				timestamp, resolution, bitbufbytes = web_pic_struct

				# send timestamp as metadata. use telemetry_sample_num as the index.
				self.pic_mem.append_pic(telemetry_sample_num, bitbufbytes, timestamp)

				if not self.teximg:
					self.teximg = texture_wrap.TextureWrap(resolution[0], resolution[1])

	def init(self):
		self.webcam_video.init(self.conf.camera_name, self.conf.camera_resolution)
		self.webcam_video.start()

	def stop(self):
		self.webcam_video.stop()

	def render(self, x, y, w, h):

		if self.teximg:
			glColor4f(1.,1.,1.,1.)
			#self.teximg.draw(x, y)
			ww, hh = self.teximg.w, self.teximg.h
			if h < hh:
				d = float(h) / hh
				self.teximg.draw(x, y, 0., d * ww, d * hh)
			else:
				self.teximg.draw(x, y)

	def load_from_disk(self):
		""" turns off the realtime view. sadly.. """
		pass
