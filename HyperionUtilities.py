# -*- coding: utf-8 -*-
"""
Created on Mon Oct  5 15:23:36 2020
@author: dmeichle
"""
#
# x[0,:] is contiguous
#
import numpy as np
import matplotlib.pyplot as plt
import os
from pathlib import Path
from datetime import datetime
from matplotlib import cm
DEFAULT_DATA_FOLDER = r"C:/Users/dmeichle/Documents/Micron Optics/ENLIGHT/Data/2020/11/"
DEFAULT_DATAFILE_KEY = 'Responses.'

class HyperionDataset():
    def __init__(self, dataFileName = None, channels = [0], recentFileOffset = 0):
        """
        Data Container for HYPERION data files
        Parameters
        ----------
        dataFileName : TYPE, optional
            DESCRIPTION. The default is None.
            Specifies the (entire) path to the desired data file
            If omitted, will use most recent data file in DEFAULT_DATA_FOLDER
            Ignores files which dont have DEFAULT_DATAFILE_KEY
            Can specify recentfileOffset to select the N-th most recent file
        channels : TYPE, optional
            DESCRIPTION. The default is [0].
            Specifies what channels [0-3] are read

        recentFileOffset : TYPE, optional
            DESCRIPTION. The default is 0.
            Specify recentfileOffset to select the N-th most recent file
            ie if recentfileOffset is 1 the 2'nd most recent file is opened,
               if recentfileOffset is 2 then the 3'rd most recent file is opened etc.'
        """

        if dataFileName is None:

            print("Using {} N'th most recent data file in month: ".format(recentFileOffset), DEFAULT_DATA_FOLDER.split('/')[-2])
            print("From default path: ", DEFAULT_DATA_FOLDER)
            print("Which includes key: ", DEFAULT_DATAFILE_KEY)
            paths = sorted(Path(DEFAULT_DATA_FOLDER).iterdir(), key=os.path.getmtime)
            while(DEFAULT_DATAFILE_KEY not in str(paths[-1]) ):
                del paths[-1]

            dataFileName = paths[-(1+recentFileOffset)]
            print("\n\t",dataFileName)
        self.dataFile = dataFileName
        self.channels = channels
        self.onlyOneChannel = len(self.channels) == 1
        self._load()
        self._generateSampleTimes()
        self._calcStats()
        self.meta = {}

    def addMeta(self, metaName, metaData):
        #add general external metadata like temperature or system state here
        self.meta[metaName] = metaData

    def _generateSampleTimes(self):
        self.datetimeList = []
        for timeStamp in self.timeStampList:
            self.datetimeList.append(datetime.strptime(timeStamp.rstrip(), '%m/%d/%Y %H:%M:%S.%f'))

        timeFromStartList = []
        for dt in self.datetimeList:
            deltaDatetime = dt - self.datetimeList[0]
            timeFromStartList.append( deltaDatetime.total_seconds() )
        self.time = np.array(timeFromStartList)
        

    def _load(self):
        rawDataList = []
        self.timeStampList = []
        self.headerTxt = r''
        self.headerDict = {}
        lineCounter = 0
        channels = [0]

        with open(self.dataFile) as f:
            headerLengthLines = int( f.readline() )
            while( lineCounter < headerLengthLines - 1):
                line = f.readline()
                self.headerTxt += line
                if len(line) > 1:
                    #Split Header lines into key (left of ':') and value (right of ':')
                    self.headerDict[line.split(':')[0] ] = line.split(':')[1]
                lineCounter += 1

            for line in f:
                if len(line) > 1000: #cut out the periodic time stamps and blank lines. this is hacky but works well :)
                    rawDataList.append( np.fromiter(line.split('\t'), dtype = np.float32)) #ugly but get warnings if we use np.fromtext
                elif line != '\n':
                    self.timeStampList.append(line)
                else:
                    pass
        #Dunno why but first measurement seems wonky, just delete for now
        del rawDataList[0]
        del rawDataList[0]
        del rawDataList[0]
        del rawDataList[0]
        del self.timeStampList[0]
        rawData = np.array(rawDataList)
        #data is now loaded, no need to organize into channels

        #note each channel will have 1/4 the number of total rows since all 4 channels are written even if not used
        # rawData.shape[0]/4 is always an int b/c the total number of rows is always a multiple of 4 (because always 4 written)
        #note we still have to do this even if self.onlyOneChannel == True to get rid of the empty data channels (with just noise)
        self.numDataPoints = int( rawData.shape[0] / 4)  #number of data points (in time) for each channel
        self.numSpecBins = rawData.shape[1]     #number of wavelengths read, default is 10000 (could use self.headerDict['Number of Points'])
        data = np.zeros( [len(self.channels), self.numDataPoints, self.numSpecBins] )
        for (i,channel) in enumerate(self.channels):
            data[i,:,:] = rawData[channel::4]

        #WARNING for initial testing to avoid headace of always needing to do data[0,:,:], 
        # I am assuming we want to squeeze the 'empty' first dimension. Need a more elegant soln than .onlyOneChannel eventually
        if self.onlyOneChannel:
            data = data.squeeze()

        self.minWaveLength = float(self.headerDict['Wavelength Start (nm)'])
        self.maxWaveLength = self.minWaveLength + float(self.headerDict['Wavelength Delta (nm)']) * self.numSpecBins
        self.waveLengths   = np.linspace( self.minWaveLength, self.maxWaveLength, self.numSpecBins )
        self.data = data

    def _calcStats(self, indRng = [0,-1]):
        indRng = [0,-1]
        if self.onlyOneChannel:
            self.std = np.std(self.data, axis = 0)
            self.stdMean = np.mean( self.std )
            
            centerOfMass = []
            peakWavelength = []
            for d in self.data:
                
                cm = np.dot( self.waveLengths[ indRng[0]:indRng[1] ], -d[ indRng[0]:indRng[1] ] ) / np.sum(-d[ indRng[0]:indRng[1] ])
                centerOfMass.append(cm)
                peakWavelength.append( np.argmax(d) / 100.0 + 1500.0 ) #converts indicies to wavelength
            
            self.centerOfMass = np.array(centerOfMass)
            self.peakWavelength = np.array(peakWavelength)

        else:
            self.std = []
            self.stdMean = []
            self.centerOfMass   = []
            self.peakWavelength = []
            for i in range(len(self.channels)):
                self.std.append( np.std(self.data[i].squeeze(), axis = 0))
                self.stdMean.append( np.mean(self.std[-1]))
                
                centerOfMass = []
                peakWavelength = []
                for d in self.data[i].squeeze():
                    cm = np.dot( self.waveLengths[ indRng[0]:indRng[1] ], -d[ indRng[0]:indRng[1] ] ) / np.sum(-d[ indRng[0]:indRng[1] ])
                    centerOfMass.append(cm)
                    peakWavelength.append( np.argmax(d) / 100.0 + 1500.0 ) #converts indicies to wavelength
                
                self.centerOfMass.append(     np.array(centerOfMass))
                self.peakWavelength.append( np.array(peakWavelength))


    # def _calcStats(self):
    #     if self.onlyOneChannel:
    #         self.std = np.std(self.data, axis = 0)
    #         self.stdMean = np.mean( self.std )
    #     else:
    #         self.std = []
    #         self.stdMean = []
    #         for i in range(len(self.channels)):
    #             self.std.append( np.std(self.data[i].squeeze(), axis = 0))
    #             self.stdMean.append( np.mean(self.std[-1]))
    def plotSpec(self,skip=1, figNum = 1,wavelengthRng = [1548,1552]):
        #
        if self.onlyOneChannel:
            for i in range(0,self.numDataPoints, skip):
                plt.figure(figNum)
                plt.plot( self.waveLengths, self.data[i,:]) #todo color by time
                plt.title('Channel ' + str(self.channels[0]))
                plt.xlabel('Wavelength (nm)', fontsize = 14)
                plt.ylabel('Reflected Power (dB)', fontsize = 14)
        else:
            for i in range(len(self.channels)):
                plt.figure(figNum + i)
                plt.title('Channel ' + str(self.channels[i]))
                for j in range(0,self.numDataPoints, skip):
                    plt.plot( self.waveLengths, self.data[i,j,:])
                plt.xlabel('Wavelength (nm)', fontsize = 14)
                plt.ylabel('Reflected Power (dB)', fontsize = 14)
        plt.xlim( [wavelengthRng[0], wavelengthRng[1]] )

    def colorTempPlot(self, labelFunction = None, skip = 1, wavelengthRng = [1548,1552], startOffset = 0):
        plt.figure()
        numPlots = (self.data.shape[0] -startOffset) // skip
        color = cm.rainbow( np.linspace(0,1,numPlots+1) )
        color = color[::-1]
        #for (i,cindex) in zip(range(0,self.data.shape[0], skip), range(numPlots)):
        for i in range( numPlots-1):
            specInd = i*skip + startOffset
            if labelFunction is not None: #disable if not passing labels
                plt.legend(prop={'size':10})
                theLabel = labelFunction(self.time[specInd]) #label = '{:3.2f} C'.format(theLabel)
                plt.plot( self.waveLengths, self.data[specInd], color = color[i], label = label)
            else:
                plt.plot( self.waveLengths, self.data[specInd], color = color[i])
        plt.xlim([wavelengthRng[0], wavelengthRng[1]])
        plt.tight_layout()


    def plotBins(self,bins, skip=1, figNum = 1):
        if type(bins) != type([]):
            bins = [bins]
        
        if self.onlyOneChannel:
            for bin_ in bins:
                plt.figure(figNum)
                plt.plot( self.time, self.data[::skip,bin_], label = str(bin_) ) #todo color by time
                plt.title('Channel ' + str(self.channels[0]))
                plt.xlabel('Time (s)', fontsize = 14)
                plt.ylabel('Reflected Power (dB)', fontsize = 14)
                plt.legend()
        else:
            for (i,bin_) in enumerate(bins):
                plt.figure(figNum + i)
                plt.title('Channel ' + str(self.channels[i]))
                plt.plot( self.time, self.data[i,:,bin_], label = str(bin))
                plt.xlabel('Wavelength (nm)', fontsize = 14)
                plt.ylabel('Time (sample)', fontsize = 14)
                plt.legend()
    def plotStd(self):
        plt.figure()
        plt.plot(self.waveLengths, self.std)
        plt.title('Standard Deviation of each Bin')
        plt.ylabel('STD Spectral Power', fontsize = 14)
        plt.xlabel('Wavelength (nm)', fontsize = 14)
# #%%###########################################################################
def calcDetSignal(q, dotRng_ind = [4200,5100], toPlot=True):
    dots0 = np.dot(q.data[0,dotRng_ind[0]:dotRng_ind[1] ],q.data[0,dotRng_ind[0]:dotRng_ind[1]])
    dots = []
    legends = [str(x) for x in range(len(q.data))]
    for i in range(len(q.data)):
        dots.append( np.dot(q.data[0,dotRng_ind[0]:dotRng_ind[1]], q.data[i,dotRng_ind[0]:dotRng_ind[1]]) / dots0 )

    if toPlot:
        plt.figure()
        for i in range(len(dots)):
            plt.plot(q.time[i],dots[i],'b.',label=legends[i])
        plt.ylabel("Dimensionless Temp Detection Signal", fontsize = 14)
        plt.xlabel("Time (s)",fontsize = 14)
    return dots
# q = HyperionDataset(channels = [0], recentFileOffset=1); #heating
# q.plotSpec()
# #%%
# q = HyperionDataset(channels = [0], recentFileOffset=0); #cooling
# q.plotSpec()
# #%%
# dotRng = [4750,5150]
# dots0 = np.dot(q.data[0,dotRng[0]:dotRng[1] ],q.data[0,dotRng[0]:dotRng[1]])
# dots = []
# legends = [str(x) for x in range(len(q.data))]
# for i in range(len(q.data)):
#     dots.append( np.dot(q.data[0,dotRng[0]:dotRng[1]], q.data[i,dotRng[0]:dotRng[1]]) / dots0 )
# for i in range(len(dots)):
#     plt.plot(q.time[i],dots[i],'x',label=legends[i])
#     #plt.plot(q.data[i],label=legends[i])

# plt.legend()
# print(dots)
# #%%
# plt.plot(q.time,dots, '.')
# plt.xlabel('Time (s)', fontsize = 14)
# plt.ylabel('Dimensionless Detection Signal', fontsize = 14)
# plt.title('Heat gun applied right before 100 s')
# #%%
# # For heating data set
# plt.figure()
# plt.plot(q.waveLengths, q.data[0], 'r', label = 'Ambient (start)')
# plt.plot(q.waveLengths, q.data[18], 'g', label = 'Approx 40 C ~ 100 sec')
# plt.plot(q.waveLengths, q.data[-1], 'b', label = 'Amgient (end) ~745 sec')
# plt.legend()
# plt.xlim([1548, 1552])
# plt.xlabel("Wavelength (nm)", fontsize = 14)
# plt.ylabel("Reflected Power (dB)", fontsize = 14)
# #%%

# #%%
# from matplotlib import cm
# color = cm.rainbow(np.linspace(0,1,q.data.shape[0]))
# for spec,c in zip(q.data, color[::-1]):
#     plt.plot(q.waveLengths, spec, c=c)
#     plt.xlim([1548, 1552])
# plt.xlabel('Wavelength (nm)', fontsize = 14)
# plt.ylabel('Reflected Power (dB)', fontsize = 14)