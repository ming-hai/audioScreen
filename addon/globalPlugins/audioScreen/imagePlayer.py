from __future__ import division

import math
import threading
import time
import colorsys
import libaudioverse
from screenBitmap import rgbPixelBrightness

fadeLength=0.05
sweepGap=0.2
maxBrightness=255

class ImagePlayer_pitchStereoGrey(object):

	reverseBrightness=False
	sweepDuration=4

	def __init__(self,width,height,lowFreq=500,highFreq=5000,sweepDelay=0.5,sweepDuration=4,sweepCount=4,reverseBrightness=False):
		self.width=width
		self.height=height
		self.baseFreq=lowFreq
		self.octiveCount=math.log(highFreq/lowFreq,2)
		self.sweepDelay=sweepDelay
		self.sweepDuration=sweepDuration
		self.sweepCount=sweepCount
		self.reverseBrightness=reverseBrightness
		self.lavSim=libaudioverse.Simulation()
		self.lavPanner=libaudioverse.MultipannerNode(self.lavSim,"default")
		self.lavPanner.strategy=libaudioverse.PanningStrategies.hrtf
		self.lavPanner.should_crossfade=False
		self.lavPanner.connect_simulation(0)
		self.lavWaves=[]
		for x in xrange(self.height):
			lavPanner=libaudioverse.AmplitudePannerNode(self.lavSim)
			lavPanner.should_crossfade=False
			lavPanner.connect_simulation(0)
			lavWave=libaudioverse.SineNode(self.lavSim)
			lavWave.mul=0
			lavWave.frequency.value=self.baseFreq*((2**self.octiveCount)**(x/self.height))
			lavWave.connect(0,lavPanner,0)
			lavWave.connect(0,self.lavPanner,0)
			self.lavWaves.append((lavWave,lavPanner))
		self.lavSim.set_output_device(-1)

	def _playWholeImage(self,imageData):
		self.lavPanner.azimuth.value=0
		self.lavPanner.mul.value=0
		for y in xrange(self.height):
			index=-1-y;
			lavWave,lavPanner=self.lavWaves[index]
			lavPanner.mul.value=1
			left=0
			right=0
			brightest=0
			for x in xrange(self.width):
				rRatio=x/self.width
				lRatio=1-rRatio
				px=rgbPixelBrightness(imageData[y][x])
				if self.reverseBrightness:
					px=maxBrightness-px
				brightest=max(brightest,px)
				left+=px*lRatio
				right+=px*rRatio
			lavWave.mul.value=lavWave.mul.value
			lavWave.mul.value=(brightest/maxBrightness)/self.height
			if left or right:
				lavPanner.azimuth.value=((right-left)/max(left,right))*90
			else:
				lavPanner.azimuth.value=0

	def _sweepImage(self,imageData,delay,duration,count):
		self.lavPanner.mul.value=self.lavPanner.mul.value
		self.lavPanner.mul.set(delay,1)
		self.lavPanner.azimuth.value=self.lavPanner.azimuth.value
		self.lavPanner.azimuth.set(delay,-90)
		offset=delay
		for c in xrange(count):
			self.lavPanner.azimuth.set(offset,-90)
			offset+=sweepGap
			self.lavPanner.azimuth.envelope(time=offset,duration=duration,values=list(xrange(-90,91)))
			offset+=duration
		for y in xrange(self.height):
			index=-1-y;
			lavWave,lavPanner=self.lavWaves[index]
			lavPanner.mul.value=lavPanner.mul.value
			lavPanner.mul.set(delay,0)
			envelopeValues=[0]
			for x in xrange(self.width):
				px=rgbPixelBrightness(imageData[y][x])/maxBrightness
				if self.reverseBrightness:
					px=1-px
				envelopeValues.append(px*0.075)
			envelopeValues.append(0)
			lavWave.mul.value=lavWave.mul.value
			lavWave.mul.set(delay,0)
			offset=delay
			for c in xrange(count):
				lavWave.mul.set(offset,0)
				offset+=sweepGap
				lavWave.mul.envelope(time=offset,duration=duration,values=envelopeValues)
				offset+=duration

	def _stop(self):
		self.lavPanner.azimuth.value=0
		for y in xrange(self.height):
			lavWave=self.lavWaves[y][0]
			lavWave.mul.value=lavWave.mul.value
			lavWave.mul.linear_ramp_to_value(fadeLength,0)

	def setNewImage(self,imageData,detailed=False):
		if not imageData:
			self._stop()
		else:
			if not detailed:
				self._playWholeImage(imageData)
			sweepDelay=0 if detailed else self.sweepDelay
			self._sweepImage(imageData,sweepDelay,self.sweepDuration,self.sweepCount)

	def terminate(self):
		for y in xrange(self.height):
				lavWave=self.lavWaves[y][0]
				lavWave.mul.value=0
		self.lavSim.clear_output_device()

class ImagePlayer_hsv(object):

	def __init__(self,width,height,lowFreq=90,highFreq=4000):
		self.width=width
		self.height=height
		self.lowFreq=lowFreq
		self.highFreq=highFreq
		self.lavSim=libaudioverse.Simulation()
		self.lavWave=libaudioverse.AdditiveSawNode(self.lavSim)
		self.lavWave.mul=0
		self.lavWave.frequency.value=lowFreq
		self.lavWave.connect_simulation(0)
		self.lavWave2=libaudioverse.SineNode(self.lavSim)
		self.lavWave2.mul=0
		self.lavWave2.frequency.value=lowFreq*(highFreq/lowFreq)
		self.lavWave2.connect_simulation(0)
		self.lavNoise=libaudioverse.NoiseNode(self.lavSim)
		self.lavNoise.mul.value=0
		self.lavNoise.noise_type.value=libaudioverse.NoiseTypes.brown
		self.lavNoise.connect_simulation(0)
		self.lavSim.set_output_device(-1)

	def setNewImage(self,imageData,detailed=False):
		r=g=b=0
		if imageData is not None:
			for x in xrange(self.height):
				for y in xrange(self.width):
					px=imageData[y][x]
					r+=px.rgbRed
					g+=px.rgbGreen
					b+=px.rgbBlue
			r/=(self.width*self.height)
			g/=(self.width*self.height)
			b/=(self.width*self.height)
		h,s,v=colorsys.rgb_to_hsv(r/255,g/255,b/255)
		s=1-(10**(1-s)/10)
		iH=1-h
		iH_fromBlue=min(max(iH-0.333,0)/0.666,1)
		iH_imag=min(iH/0.333,1)
		self.lavWave.mul.value=v*s*iH_imag*0.75/(1+(iH_fromBlue*10))
		self.lavWave.frequency.value=self.lowFreq*((self.highFreq/self.lowFreq)**((2**iH_fromBlue)-1))
		self.lavWave.harmonics=int(1+((((1-abs(iH_fromBlue-0.5))*2)-1)*20))
		self.lavWave2.mul.value=v*s*(1-iH_imag)*0.075
		self.lavNoise.mul.value=(1-s)*v*0.4

	def terminate(self):
		self.lavSim.clear_output_device()
