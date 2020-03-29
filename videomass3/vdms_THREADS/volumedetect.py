 # -*- coding: UTF-8 -*-

#########################################################
# Name: volumedetect.py
# Porpose: Audio Peak level volume analyzes
# Compatibility: Python3, wxPython Phoenix
# Author: Gianluca Pernigoto <jeanlucperni@gmail.com>
# Copyright: (c) 2018/2020 Gianluca Pernigoto <jeanlucperni@gmail.com>
# license: GPL3
# Rev: Dec.27.2018. Sept.05.2019
#########################################################
# This file is part of Videomass.

#    Videomass is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.

#    Videomass is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.

#    You should have received a copy of the GNU General Public License
#    along with Videomass.  If not, see <http://www.gnu.org/licenses/>.

#########################################################
import wx
from pubsub import pub
import subprocess
from threading import Thread
from videomass3.vdms_IO.make_filelog import write_log # write initial log

########################################################################
# path to the configuration directory:
get = wx.GetApp()
DIRconf = get.DIRconf
OS = get.OS
ffmpeg_url = get.ffmpeg_url
#########################################################################
if not OS == 'Windows':
    import shlex

class PopupDialog(wx.Dialog):
    """ 
    A pop-up dialog box for temporary user messages that tell the user 
    the load in progress (required for large files).
    
    Usage:
            loadDlg = PopupDialog(None, ("Videomass - Loading..."), 
                        ("\nAttendi....\nSto eseguendo un processo .\n")
                                )
            loadDlg.ShowModal() 

            loadDlg.Destroy()
    """
    def __init__(self, parent, title, msg):
        # Create a dialog
        wx.Dialog.__init__(self, parent, -1, title, size=(350, 150), 
                            style=wx.CAPTION)
        # Add sizers
        box = wx.BoxSizer(wx.VERTICAL)
        box2 = wx.BoxSizer(wx.HORIZONTAL)
        # Add an Info graphic
        bitmap = wx.Bitmap(32, 32)
        bitmap = wx.ArtProvider.GetBitmap(wx.ART_INFORMATION, 
                                          wx.ART_MESSAGE_BOX, (32, 32)
                                          )
        graphic = wx.StaticBitmap(self, -1, bitmap)
        box2.Add(graphic, 0, wx.EXPAND | wx.ALIGN_CENTER | wx.ALL, 10)
        # Add the message
        message = wx.StaticText(self, -1, msg)
        box2.Add(message, 0, wx.EXPAND | wx.ALIGN_CENTER 
                                    | wx.ALIGN_CENTER_VERTICAL | wx.ALL, 10
                                    )
        box.Add(box2, 0, wx.EXPAND)
        # Handle layout
        self.SetAutoLayout(True)
        self.SetSizer(box)
        self.Fit()
        self.Layout()

        pub.subscribe(self.getMessage, "RESULT_EVT")
        
    def getMessage(self, status):
        """
        Riceive msg and status from thread.
        All'inizio usavo self.Destroy() per chiudere il dialogo modale
        (con modeless ritornava dati None), ma dava warning e critical
        e su OsX non chiudeva affatto. Con EndModal ho risolto tutti
        i problemi e funziona bene. Ma devi ricordarti di eseguire
        Destroy() dopo ShowModal() nel chiamante.
        vedi: https://github.com/wxWidgets/Phoenix/issues/672
        Penso sia fattibile anche implementare un'interfaccia GetValue
        su questo dialogo, ma si perderebbe un po' di portabilità.
        
        """
        #self.Destroy() # do not work
        self.EndModal(1)
##############################################################################
class VolumeDetectThread(Thread):
    """
    This class represents a separate subprocess thread to get 
    audio volume peak level when required for audio normalization 
    process.
    
    NOTE: all error handling (including verification of the 
    existence of files) is entrusted to ffmpeg, except for the 
    lack of ffmpeg of course.
    
    """
    def __init__(self, timeseq, filelist, audiomap, OS):
        """
        Replace /dev/null with NUL on Windows.
        
        self.status: None, if nothing error,
                     'str error' if errors.
        self.data: it is a tuple containing the list of audio volume 
                   parameters and the self.status of the error output,
                   in the form: 
                   ([[maxvol, medvol], [etc,etc]], None or "str errors") 
        
        """
        Thread.__init__(self)
        """initialize"""
        self.filelist = filelist
        self.time_seq = timeseq
        self.audiomap = audiomap
        self.status = None
        self.data = None
        self.nul = 'NUL' if OS == 'Windows' else '/dev/null'

        self.logf = "%s/log/%s" %(DIRconf, 'Videomass_volumedected.log')
        
        write_log('Videomass_volumedected.log', "%s/log" % DIRconf) 
        # set initial file LOG
        
        self.start() # start the thread (va in self.run())
        
    #----------------------------------------------------------------#
    def run(self):
        """
        Audio volume data is getted by the thread's caller using 
        the thread.data method (see IO_tools).
        NOTE: wx.callafter(pub...) do not send data to pop-up 
              dialog, but a empty string that is useful to get 
              the end of the process to close of the pop-up .
        
        """
        volume = list()

        for files in self.filelist:
            cmd = ('{0} {1} -i "{2}" -hide_banner {3} -af volumedetect '
                    '-vn -sn -dn -f null {4}').format(ffmpeg_url, 
                                                      self.time_seq,
                                                      files,
                                                      self.audiomap,
                                                      self.nul)
            self.logWrite(cmd)
            
            if not OS == 'Windows':
                cmd = shlex.split(cmd)
                info = None
            else: # Hide subprocess window on MS Windows
                info = subprocess.STARTUPINFO()
                info.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            try:
                p = subprocess.Popen(cmd, 
                                     stdout=subprocess.PIPE, 
                                     stderr=subprocess.STDOUT,
                                     universal_newlines=True,
                                     startupinfo=info,
                                     )
                output =  p.communicate()
            
            except OSError as e:# if ffmpeg do not exist
                self.status = e
                break
            
            else:
                
                if p.returncode: # if error occurred
                    self.status = output[0]
                    break
                
                else:
                    raw_list = output[0].split() # splitta tutti gli spazi 
                    if 'mean_volume:' in raw_list:
                        mean_volume = raw_list.index("mean_volume:")
                        #mean_volume is indx integear
                        medvol = "%s dB" % raw_list[mean_volume + 1]
                        max_volume = raw_list.index("max_volume:")
                        #max_volume is indx integear
                        maxvol = "%s dB" % raw_list[max_volume + 1]
                        volume.append([maxvol, medvol])
                
        self.data = (volume, self.status)
        
        if self.status:
            self.logError()
            
        wx.CallAfter(pub.sendMessage, 
                     "RESULT_EVT",  
                      status=''
                      )
        
    #----------------------------------------------------------------#    
    def logWrite(self, cmd):
        """
        write ffmpeg command log
        
        """
        with open(self.logf, "a") as log:
            log.write("%s\n\n" % (cmd))
            
    #----------------------------------------------------------------# 
    def logError(self):
        """
        write ffmpeg volumedected errors
        
        """
        with open(self.logf,"a") as logerr:
            logerr.write("[FFMPEG] volumedetect "
                         "ERRORS:\n%s\n\n" % (self.status))
    #----------------------------------------------------------------#
    
