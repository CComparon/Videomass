# -*- coding: UTF-8 -*-
"""
Name: video_stabilization.py
Porpose: FFmpeg long processing vidstab
Compatibility: Python3, wxPython4 Phoenix
Author: Gianluca Pernigotto <jeanlucperni@gmail.com>
Copyright: (c) 2018/2022 Gianluca Pernigotto <jeanlucperni@gmail.com>
license: GPL3
Rev: Feb.14.2022
Code checker:
    flake8: --ignore F821, W504
    pylint: --ignore E0602, E1101

This file is part of Videomass.

   Videomass is free software: you can redistribute it and/or modify
   it under the terms of the GNU General Public License as published by
   the Free Software Foundation, either version 3 of the License, or
   (at your option) any later version.

   Videomass is distributed in the hope that it will be useful,
   but WITHOUT ANY WARRANTY; without even the implied warranty of
   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
   GNU General Public License for more details.

   You should have received a copy of the GNU General Public License
   along with Videomass.  If not, see <http://www.gnu.org/licenses/>.
"""
import os
from threading import Thread
import time
import itertools
import subprocess
import platform
import wx
from pubsub import pub
from videomass.vdms_utils.utils import Popen
from videomass.vdms_io.make_filelog import logwrite
if not platform.system() == 'Windows':
    import shlex


class VidStab(Thread):
    """
    This class represents a separate thread which need
    to read the stdout/stderr in real time mode for
    different tasks.

    NOTE capturing output in real-time (Windows, Unix):

    https://stackoverflow.com/questions/1388753/how-to-get-output-
    from-subprocess-popen-proc-stdout-readline-blocks-no-dat?rq=1

    """
    get = wx.GetApp()  # get videomass wx.App attribute
    appdata = get.appset
    OS = appdata['ostype']
    SUFFIX = appdata['filesuffix']
    NOT_EXIST_MSG = _("Is 'ffmpeg' installed on your system?")

    def __init__(self, varargs, duration, logname, timeseq):
        """
        The 'volume' attribute may have an empty value, but it will
        have no influence on the type of conversion.
        """
        self.stop_work_thread = False  # process terminate
        self.filelist = varargs[1]  # list of files (elements)
        self.passlist = varargs[5]  # comand list set for double-pass
        self.makeduo = varargs[4]  # one more process for the duo file
        self.outputdir = varargs[3]  # output path
        self.extoutput = varargs[2]  # format (extension)
        self.duration = duration  # duration list
        self.time_seq = timeseq  # a time segment
        self.volume = varargs[7]  # volume compensation data
        self.count = 0  # count first for loop
        self.countmax = len(varargs[1])  # length file list
        self.logname = logname  # title name of file log
        self.nul = 'NUL' if VidStab.OS == 'Windows' else '/dev/null'

        spl = varargs[6].split('-vf ')[1]
        addspl = ','.join([x for x in spl.split(',') if '-vf' not
                           in x and 'vidstabtransform' not in x and
                           'unsharp' not in x])  # if other filters
        self.addflt = '' if addspl == '' else '%s,' % (addspl)

        Thread.__init__(self)
        self.start()  # start the thread (va in self.run())

    def run(self):
        """
        Subprocess initialize thread.
        """
        filedone = []
        for (files,
             folders,
             volume,
             duration) in itertools.zip_longest(self.filelist,
                                                self.outputdir,
                                                self.volume,
                                                self.duration,
                                                fillvalue='',
                                                ):
            basename = os.path.basename(files)  # nome file senza path
            filename = os.path.splitext(basename)[0]  # nome senza ext
            source_ext = os.path.splitext(basename)[1].split('.')[1]  # ext
            outext = source_ext if not self.extoutput else self.extoutput
            outputfile = os.path.join(folders, '%s%s.%s' % (filename,
                                                            VidStab.SUFFIX,
                                                            outext))

            # --------------- first pass
            pass1 = ('"%s" %s %s %s -i "%s" %s %s '
                     '-y %s' % (VidStab.appdata['ffmpeg_cmd'],
                                VidStab.appdata['ffmpegloglev'],
                                VidStab.appdata['ffmpeg+params'],
                                self.time_seq,
                                files,
                                self.passlist[0],
                                VidStab.appdata['ffthreads'],
                                self.nul,
                                ))
            self.count += 1
            count = ('File %s/%s - Pass One\n'
                     'Video stabilization detect...' % (self.count,
                                                        self.countmax)
                     )
            cmd = ('%s\nSource: "%s"\nDestination: "%s"\n\n'
                   '[COMMAND]:\n%s' % (count, files, self.nul, pass1))

            wx.CallAfter(pub.sendMessage,
                         "COUNT_EVT",
                         count=count,
                         fsource='Source:  "%s"' % files,
                         destination='Destination:  "%s"' % self.nul,
                         duration=duration,
                         end='',
                         )
            logwrite(cmd, '', self.logname)  # write n/n + command only

            if not VidStab.OS == 'Windows':
                pass1 = shlex.split(pass1)
            try:
                with Popen(pass1,
                           stderr=subprocess.PIPE,
                           bufsize=1,
                           universal_newlines=True,
                           ) as proc1:

                    for line in proc1.stderr:
                        wx.CallAfter(pub.sendMessage,
                                     "UPDATE_EVT",
                                     output=line,
                                     duration=duration,
                                     status=0
                                     )
                        if self.stop_work_thread:  # break second 'for' loop
                            proc1.terminate()
                            break

                    if proc1.wait():  # will add '..failed' to txtctrl
                        wx.CallAfter(pub.sendMessage,
                                     "UPDATE_EVT",
                                     output=line,
                                     duration=duration,
                                     status=proc1.wait(),
                                     )
                        logwrite('',
                                 "Exit status: %s" % proc1.wait(),
                                 self.logname,
                                 )  # append exit error number

            except (OSError, FileNotFoundError) as err:
                excepterr = "%s\n  %s" % (err, VidStab.NOT_EXIST_MSG)
                wx.CallAfter(pub.sendMessage,
                             "COUNT_EVT",
                             count=excepterr,
                             fsource='',
                             destination='',
                             duration=0,
                             end='error',
                             )
                break

            if self.stop_work_thread:  # break first 'for' loop
                proc1.terminate()
                break  # fermo il ciclo for, altrimenti passa avanti

            if proc1.wait() == 0:  # will add '..terminated' to txtctrl
                wx.CallAfter(pub.sendMessage,
                             "COUNT_EVT",
                             count='',
                             fsource='',
                             destination='',
                             duration='',
                             end='ok'
                             )
            # --------------- second pass ----------------#
            pass2 = ('"%s" %s %s %s -i "%s" %s %s %s '
                     '-y "%s/%s%s.%s"' % (VidStab.appdata['ffmpeg_cmd'],
                                          VidStab.appdata['ffmpegloglev'],
                                          VidStab.appdata['ffmpeg+params'],
                                          self.time_seq,
                                          files,
                                          self.passlist[1],
                                          volume,
                                          VidStab.appdata['ffthreads'],
                                          folders,
                                          filename,
                                          VidStab.SUFFIX,
                                          outext,
                                          ))
            count = ('File %s/%s - Pass Two\nVideo transform...' % (
                     self.count, self.countmax,))

            cmd = ('%s\nSource: "%s"\nDestination: "%s"\n\n'
                   '[COMMAND]:\n%s' % (count, files, outputfile, pass2))

            wx.CallAfter(pub.sendMessage,
                         "COUNT_EVT",
                         count=count,
                         fsource='Source:  "%s"' % files,
                         destination='Destination:  "%s"' % outputfile,
                         duration=duration,
                         end='',
                         )
            logwrite(cmd, '', self.logname)

            if not VidStab.OS == 'Windows':
                pass2 = shlex.split(pass2)

            with Popen(pass2,
                       stderr=subprocess.PIPE,
                       bufsize=1,
                       universal_newlines=True,
                       ) as proc2:

                for line2 in proc2.stderr:
                    wx.CallAfter(pub.sendMessage,
                                 "UPDATE_EVT",
                                 output=line2,
                                 duration=duration,
                                 status=0,
                                 )
                    if self.stop_work_thread:
                        proc2.terminate()
                        break

                if proc2.wait():  # will add '..failed' to txtctrl
                    wx.CallAfter(pub.sendMessage,
                                 "UPDATE_EVT",
                                 output=line,
                                 duration=duration,
                                 status=proc2.wait(),
                                 )
                    logwrite('',
                             "Exit status: %s" % proc2.wait(),
                             self.logname,
                             )  # append exit status error

            if self.stop_work_thread:  # break first 'for' loop
                proc2.terminate()
                break  # fermo il ciclo for, altrimenti passa avanti

            if proc2.wait() == 0:  # will add '..terminated' to txtctrl
                filedone.append(files)
                wx.CallAfter(pub.sendMessage,
                             "COUNT_EVT",
                             count='',
                             fsource='',
                             destination='',
                             duration='',
                             end='ok'
                             )

            # --------------- make duo ----------------#
            if self.makeduo:
                outduo = os.path.join(folders, '%s%s_DUO.%s' % (filename,
                                                                VidStab.SUFFIX,
                                                                outext))
                pass3 = ('"%s" %s %s %s -i "%s" %s -vf "[in] %spad=2*iw:ih '
                         '[left]; movie=%s [right]; '
                         '[left][right] overlay=main_w/2:0 [out]" -y '
                         '"%s"' % (VidStab.appdata['ffmpeg_cmd'],
                                   VidStab.appdata['ffmpegloglev'],
                                   VidStab.appdata['ffmpeg+params'],
                                   self.time_seq,
                                   files,
                                   VidStab.appdata['ffthreads'],
                                   self.addflt,
                                   outputfile,
                                   outduo,
                                   ))
                count = 'File %s/%s\nMake duo...' % (self.count, self.countmax)
                cmd = ('%s\nSource: "%s"\nDestination: "%s"\n\n'
                       '[COMMAND]:\n%s' % (count, files, outputfile, pass3))

                wx.CallAfter(pub.sendMessage,
                             "COUNT_EVT",
                             count=count,
                             fsource='Source:  "%s"' % files,
                             destination='Destination: "%s"' % outduo,
                             duration=duration,
                             end='',
                             )
                logwrite(cmd, '', self.logname)

                if not VidStab.OS == 'Windows':
                    pass3 = shlex.split(pass3)

                with Popen(pass3,
                           stderr=subprocess.PIPE,
                           bufsize=1,
                           universal_newlines=True,
                           ) as proc3:

                    for line3 in proc3.stderr:
                        wx.CallAfter(pub.sendMessage,
                                     "UPDATE_EVT",
                                     output=line3,
                                     duration=duration,
                                     status=0,
                                     )
                        if self.stop_work_thread:
                            proc3.terminate()
                            break

                    if proc3.wait():  # will add '..failed' to txtctrl
                        wx.CallAfter(pub.sendMessage,
                                     "UPDATE_EVT",
                                     output=line,
                                     duration=duration,
                                     status=proc3.wait(),
                                     )
                        logwrite('',
                                 "Exit status: %s" % proc3.wait(),
                                 self.logname,
                                 )  # append exit error number

                if self.stop_work_thread:  # break first 'for' loop
                    proc3.terminate()
                    break  # fermo il ciclo for, altrimenti passa avanti

                if proc3.wait() == 0:  # will add '..terminated' to txtctrl
                    wx.CallAfter(pub.sendMessage,
                                 "COUNT_EVT",
                                 count='',
                                 fsource='',
                                 destination='',
                                 duration='',
                                 end='ok'
                                 )
        time.sleep(.5)
        wx.CallAfter(pub.sendMessage, "END_EVT", msg=filedone)
    # --------------------------------------------------------------------#

    def stop(self):
        """
        Sets the stop work thread to terminate the process
        """
        self.stop_work_thread = True
