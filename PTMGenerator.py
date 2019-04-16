from tkinter import filedialog, messagebox
from tkinter import *
from tkinter.ttk import Frame, Button, Style
from pathlib import Path
import subprocess
import math
import time
import serial
import serial.tools.list_ports
import io
from PIL import ImageTk, Image

import time, os
from win32com.shell import shell, shellcon

#sp_coord_list = [[59,31],[74,43],[65,63],[48,51],[41,18],[55,83],[60,253],[83,245],[54,221],[69,233],
#[75,266],[43,241],[38,293],[80,298],[71,318],[56,306],[50,273],[46,326],[66,286],[21,313],
#[23,176],[13,228],[28,261],[26,38],[17,91],[67,148],[51,136],[30,123],[81,160],[39,156],
#[76,128],[82,23],[32,346],[68,11],[85,330],[77,351],[62,338],[52,358],[79,76],[70,96],
#[61,116],[84,108],[36,71],[44,103],[78,213],[73,181],[34,208],[47,188],[64,201],[58,168]]

sp_coord_list = [[85, 330], [84, 108], [83, 245], [82, 23], [81, 160], [80, 298], [79, 76], [78, 213], [77, 351], [76, 128],
 [75, 266], [74, 43], [73, 181], [71, 318], [70, 96], [69, 233], [68, 11], [67, 148], [66, 286], [65, 63],
 [64, 201], [62, 338], [61, 116], [60, 253], [59, 31], [58, 168], [56, 306], [55, 83], [54, 221], [52, 358],
 [51, 136], [50, 273], [48, 51], [47, 188], [46, 326], [44, 103], [43, 241], [41, 18], [39, 156], [38, 293],
 [36, 71], [34, 208], [32, 346], [30, 123], [28, 261], [26, 38], [23, 176], [21, 313], [17, 91], [13, 228]]

lp_list = []
for [ theta, phi ] in sp_coord_list:
    x = math.cos(math.radians(phi-180)) * math.sin(math.radians(theta))
    y = math.sin(math.radians(phi-180)) * math.sin(math.radians(theta))
    z =  math.cos(math.radians(theta))
    lp_list.append( [x,y,z])

class BusyManager:

    def __init__(self, widget):
        self.toplevel = widget.winfo_toplevel()
        self.widgets = {}

    def busy(self, widget=None):

        # attach busy cursor to toplevel, plus all windows
        # that define their own cursor.

        if widget is None:
            w = self.toplevel # myself
        else:
            w = widget

        if str(w) not in self.widgets:
            try:
                # attach cursor to this widget
                cursor = w.cget("cursor")
                if cursor != "watch":
                    self.widgets[str(w)] = (w, cursor)
                    w.config(cursor="watch")
            except: #TclError:
                pass

        for w in w.children.values():
            self.busy(w)

    def notbusy(self):
        # restore cursors
        for w, cursor in self.widgets.values():
            try:
                w.config(cursor=cursor)
            except: # TclError:
                pass
        self.widgets = {}


class LEDDialog(Toplevel):

    def __init__(self, parent, title = None):

        Toplevel.__init__(self, parent)
        self.transient(parent)

        if title:
            self.title(title)

        self.parent = parent

        self.result = None

        body = Frame(self)
        self.initial_focus = self.body(body)
        body.pack(padx=5, pady=5)

        self.buttonbox()

        self.grab_set()

        if not self.initial_focus:
            self.initial_focus = self

        self.protocol("WM_DELETE_WINDOW", self.cancel)

        self.geometry("+%d+%d" % (parent.winfo_rootx()+50,
                                  parent.winfo_rooty()+50))

        self.initial_focus.focus_set()

        self.wait_window(self)
        #print("hello")

    #
    # construction hooks

    def intvar_callback(self,*args):
        print("variable changed!")
        self.on()
        #self.parent.sendSerial("OFF")

    def body(self, master):
        # create dialog body.  return widget that should have
        # initial focus.  this method should be overridden

        pass

    def buttonbox(self):
        # add standard button box. override if you don't want the
        # standard buttons

        box = Frame(self)

        self.LEDidx = IntVar()
        self.LEDidx.trace("w", self.intvar_callback)
        self.LEDidx.set(1)  # initialize

        for i in range(50):
            b = Radiobutton(box, text=str(i+1), width=3,height=1,
                            variable=self.LEDidx, value=i+1).grid(row=int(i/10),column=int(i%10))
            #b.pack(anchor=W)

        w = Button(box, text="On", width=10, command=self.on, default=ACTIVE).grid(row=5,column=1,columnspan=2)
        w = Button(box, text="Off", width=10, command=self.off, default=ACTIVE).grid(row=5,column=3,columnspan=2)
        w = Button(box, text="Shoot", width=10, command=self.shoot, default=ACTIVE).grid(row=5,column=5,columnspan=2)
        #w.pack(side=LEFT, padx=5, pady=5)
        w = Button(box, text="Close", width=10, command=self.close).grid(row=5,column=7,columnspan=2)
        #w.pack(side=LEFT, padx=5, pady=5)

        self.bind("<Return>", self.close)
        self.bind("<Escape>", self.cancel)

        box.pack()

    #
    # standard button semantics
    def sendmessage(self,msg):
        print("<"+msg+">")
        return

    def off(self, event=None):
        idx = self.LEDidx.get()
        ret_msg = self.parent.sendSerial( "OFF")
        return

    def on(self, event=None):
        idx = self.LEDidx.get()
        ret_msg = self.parent.sendSerial( "ON,"+str(idx))
        return

    def shoot(self, event=None):
        idx = self.LEDidx.get()
        ret_msg = self.parent.sendSerial( "SHOOT,"+str(idx))
        return

    def close(self, event=None):
        self.parent.sendSerial("OFF")

        if not self.validate():
            self.initial_focus.focus_set() # put focus back
            return

        self.withdraw()
        self.update_idletasks()

        self.apply()

        self.cancel()

    def cancel(self, event=None):

        # put focus back to the parent window
        self.parent.focus_set()
        self.destroy()

    #
    # command hooks

    def validate(self):

        return 1 # override

    def apply(self):

        pass # override


class PTMFrame(Frame):
    def __init__(self, parent):
        Frame.__init__(self, parent)

        self.parent = parent
        self.initUI()

    def initUI(self):
        self.parent.title("PTM Generator v0.2")
        self.style = Style()
        self.style.theme_use("default")
        self.fitter_filepath_str = ""

        self.currlistidx = -1

        frame1 = Frame(self, relief=RAISED, borderwidth=1)
        frame1.pack(fill=BOTH, expand=True)
        self.listbox = Listbox(frame1,width=40)
        self.listbox.pack(side=LEFT,fill=Y,padx=5,pady=5,ipadx=5,ipady=5)
        self.imageview = Label(frame1)
        self.imageview.pack(side=LEFT, fill=BOTH, expand=True)
        frame11 = Frame(frame1 )
        self.selectFilesButton = Button(frame11, text="Select Files", command=self.selectfiles)
        self.selectFilesButton.pack(fill=X,padx=5,pady=5)
        self.shootAgainButton = Button(frame11, text="Shoot Again", command=self.shootAgain)
        self.shootAgainButton.pack(fill=X,padx=5,pady=5)
        self.listbox.bind('<<ListboxSelect>>', self.onselect )
        frame11.pack(fill=X)

        frame2 = Frame(self, relief=RAISED, borderwidth=1)
        frame2.pack(fill=X)
        self.workdir_label = Label(frame2, text='Folder to Watch')
        self.workdir_label.pack(side=LEFT,fill=X,padx=5,pady=5)
        self.workdir_text = Entry(frame2,text='')
        self.workdir_text.pack(side=LEFT,fill=X,expand=True,padx=5,pady=5)
        self.workdirButton = Button(frame2, text="Select Folder", command=self.selectworkdir)
        self.workdirButton.pack(side=LEFT, fill=X,padx=5,pady=5)
        self.workdir_text.delete(0, END)
        dirname =shell.SHGetFolderPath(0, shellcon.CSIDL_MYPICTURES, None, 0)
        self.workdir_text.insert(0, dirname)
        p = Path(dirname)
        self.workingpath = p

        frame3 = Frame(self, relief=RAISED, borderwidth=1)
        self.fitter_label = Label(frame3, text='PTMFitter')
        self.fitter_label.pack(side=LEFT,fill=X,padx=5,pady=5)
        self.fitter_text = Entry(frame3,text='',textvariable = self.fitter_filepath_str)
        self.fitter_text.pack(side=LEFT,fill=X,expand=True,padx=5,pady=5)
        self.ptmButton = Button(frame3, text="PTMFitter", command=self.PTMfitter)
        self.ptmButton.pack(side=LEFT, fill=X,padx=5,pady=5)
        frame3.pack(fill=X)


        frame4 = Frame(self, relief=RAISED, borderwidth=1)
        self.COM_label = Label(frame4, text='Port')
        self.COM_label.pack(side=LEFT,fill=X,padx=5,pady=5)

        # Create a Tkinter variable
        self.varSerialPort = StringVar(root)

        # Dictionary with options
        choices = []

        arduino_ports = [
            p.device
            for p in serial.tools.list_ports.comports()
            if 'CH340' in p.description
        ]
        #for p in serial.tools.list_ports.comports():
        #    pass #print( p.description)
        for p in arduino_ports:
            choices.append( p )
        if len(arduino_ports) > 0:
            self.varSerialPort.set(choices[0])  # set the default option
            self.serial_exist = True
        else:
            choices.append( "NONE")
            self.varSerialPort.set(choices[0])  # set the default option
            self.serial_exist = False

        self.popupMenu = OptionMenu(frame4, self.varSerialPort, *choices)
        self.popupMenu.pack( side=LEFT, fill=X,padx=5, pady=5)

        self.shootButton = Button(frame4, text="Shoot",command=self.shoot)
        self.shootButton.pack( side=LEFT, fill=X,padx=5, pady=5)

        self.shootAllButton = Button(frame4, text="Shoot All",command=self.shootAll)
        self.shootAllButton.pack( side=LEFT, fill=X,padx=5, pady=5)

        self.generateButton = Button(frame4, text="Generate PTM File",command=self.generatePTM)
        self.generateButton.pack( side=LEFT, fill=X,padx=5, pady=5)

        self.testButton = Button(frame4, text="",command=self.test)
        self.testButton.pack( side=LEFT, fill=X,padx=5, pady=5)

        if( not self.serial_exist ):
            self.shootAllButton["state"] = "disabled"
            self.shootButton["state"] = "disabled"
        self.shootAgainButton["state"] = "disabled"


        # on change dropdown value

        frame4.pack(fill=X)

        self.pack(fill=BOTH, expand=True)
        options = {}
        options['initialdir'] = 'C:\\'
        options['mustexist'] = False
        options['parent'] = self.parent
        options['title'] = 'This is a title'

        #self.serial = serial.Serial()

        self.filelist = []
        fitter = Path.cwd().joinpath("ptmfitter.exe")
        if fitter.exists():
            self.fitter_filepath = fitter
            self.fitter_text.delete(0, END)
            self.fitter_text.insert(0, str(fitter))

        print(  )

    def shoot(self):
        if( not self.serial_exist ):
            return
        self.openSerial()
        d = LEDDialog(self)
        self.closeSerial()

        return

    def shootAgain(self):
        if( not self.serial_exist ):
            return
        if self.currlistidx < 0:
            return

        manager.busy()
        before = dict([(f, None) for f in os.listdir(str(self.workingpath))])
        self.openSerial()
        msg = "SHOOT," + str(self.currlistidx + 1)
        self.sendSerial(msg)
        time.sleep(7)
        ret_msg = self.receiveSerial()
        after = dict([(f, None) for f in os.listdir(str(self.workingpath))])
        added = [f for f in after if not f in before]
        filename = Path(self.workingpath, fn)
        self.listbox.delete(self.currlistidx)
        self.filelist.insert(self.currlistidx,filename)
        self.setimage(filename)
        self.update()

        self.closeSerial()

        return

    def PTMfitter(self):
        filename = filedialog.askopenfilename(initialdir=".", title="Select file")
        filepath = Path( filename )
        if filepath.exists():
            self.fitter_filepath = filepath
            self.fitter_filepath_str = str( filepath )
            #print( self.fitter_filepath_str )
            self.fitter_text.delete(0, END)
            self.fitter_text.insert(0, str(filepath))
            #self.fitter_label.text = str( filepath )
            #self.fitter_text.text = str( filepath )

    def selectworkdir(self):
        #print( "open")
        currdir = str(self.workingpath)
        dirname = filedialog.askdirectory(initialdir=currdir, title="Select folder")
        p = Path(dirname)
        self.currdirname = p.parts[-1]
        #self.workingdir = str(p)
        self.workingpath = p
        #self.workdir_text.text = str(p)
        self.workdir_text.delete(0, END)
        self.workdir_text.insert(0, str(p))
        self.imageview.image = None
        self.filelist = []
        self.listbox.delete(0, 'end')

    def selectfiles(self):
        #print( "open")
        currdir = str(self.workingpath)
        filenames = filedialog.askopenfilenames(initialdir=currdir, title="Select files")
        lst = list(filenames)
        #lst.sort()
        self.filelist = []
        self.listbox.delete(0, 'end')
        if len(lst)>0:
            i = 1
            for fn in lst:
                print(str(fn))
                self.listbox.insert( i, str(fn) )
                self.filelist.append( fn )
                #self.text_input3.text += ",".join([str(coord) for coord in lp[i-1]])
                i+=1

    def opendir(self):
        currdir = str(self.workingpath)
        dirname = filedialog.askdirectory(initialdir=currdir, title="Select directory")
        p = Path(dirname)
        self.currdirname = p.parts[-1]
        #self.workingdir = str(p)
        self.workingpath = p
        #self.workdir_text.text = str(p)
        self.workdir_text.delete(0, END)
        self.workdir_text.insert(0, str(p))
        self.imageview.image = None

        self.filelist = []
        if p.is_dir():
            self.listbox.delete(0, 'end')
            i = 1
            for x in p.iterdir():
                if not x.is_dir() :
                    if x.suffix in ['.JPG','.jpg']:
                        new_x = x.with_suffix('.jpg')
                        self.listbox.insert( i, str(new_x.name) )
                        self.filelist.append( new_x )
                        #self.text_input3.text += ",".join([str(coord) for coord in lp[i-1]])
                        i+=1
                    else:
                        pass #print( x.suffix)
        #print(dirname)

    def generatePTM(self):
        if self.listbox.size() != 50:
            messagebox.showerror(message="Must be 50 image files!")
            #print( "must be 50 files")
            return
        ret_str = "50\n"
        for i in range(50):
            ret_str += str(self.filelist[i]) + " " + " ".join( [ str(f) for f in lp_list[i] ] ) + "\n"
        options = {}
        options['initialdir'] = 'C:\\'
        options['mustexist'] = False
        options['parent'] = self
        options['title'] = 'Save light position file'
        netfilename = self.workingpath.parts[-1]
        lpfilename = Path( self.workingpath,  netfilename + ".lp" ) #
        file = open( str(lpfilename), 'w')
        file.write( ret_str )
        file.close()
        saveoptions = {}
        saveoptions['defaultextension'] = '.ptm'
        saveoptions['filetypes'] = [('all files', '.*'), ('PTM files', '.ptm')]
        saveoptions['initialdir'] = self.workingpath
        saveoptions['initialfile'] = netfilename + '.ptm'
        ptmfilename = Path( filedialog.asksaveasfilename(**saveoptions) )  # mode='w',**options)
        #print( ptmfilename )
        execute_string = " ".join( [ str( self.fitter_filepath ),"-i", str(lpfilename), "-o", str(ptmfilename) ] )
        #print( execute_string )
        subprocess.call([ str( self.fitter_filepath ),"-i", str(lpfilename), "-o", str(ptmfilename) ])

    def openSerial(self):
        if( not self.serial_exist ):
            return
        self.serial = serial.Serial(self.varSerialPort.get(), 9600, timeout=2)
        time.sleep(2)

        return

    def closeSerial(self):
        self.serial.close()

        return

    def sendSerial(self,msg):
        msg = "<" + msg + ">"
        print( msg )
        self.serial.write( msg.encode() )

    def receiveSerial(self):
        return_msg = self.serial.readline()
        print( return_msg )
        return return_msg

    def test(self):
        manager.busy()
        before = dict([(f, None) for f in os.listdir(str(self.workingpath))])
        print( before)

        for i in range(10):
            time.sleep(5)
            after = dict([(f, None) for f in os.listdir(str(self.workingpath))])
            added = [f for f in after if not f in before]
            removed = [f for f in before if not f in after]
            if added:
                print( "Added: ", ", ".join(added) )
                for fn in added:
                    filename = Path(self.workingpath, fn )
                    self.listbox.insert(END, filename)
                    self.filelist.append(filename)
                    self.setimage(filename)
                    self.update()
            else:
                self.listbox.insert(END, 'NONE')
                self.filelist.append('NONE')
                self.update()
            before = after
        manager.notbusy()

    def shootAll(self):
        if( not self.serial_exist ):
            return

        manager.busy()
        before = dict([(f, None) for f in os.listdir(str(self.workingpath))])
        self.openSerial()
        for i in range(50):
            msg = "SHOOT," + str(i+1)
            self.sendSerial(msg)
            time.sleep(7)
            ret_msg = self.receiveSerial()
            after = dict([(f, None) for f in os.listdir(str(self.workingpath))])
            added = [f for f in after if not f in before]
            if added:
                #print( "Added: ", ", ".join(added) )
                for fn in added:
                    filename = Path(self.workingpath, fn )
                    self.listbox.insert(END, filename)
                    self.filelist.append(filename)
                    self.setimage(filename)
                    self.update()
            else:
                self.listbox.insert(END, 'NONE')
                self.filelist.append('NONE')
                self.update()
            before = after
            #print(ret_msg)
        self.sendSerial("OFF")
        self.closeSerial()
        manager.notbusy()

    def onselect(self,evt):
        w = evt.widget
        index = int(w.curselection()[0])
        #print( "index=",index)
        value = w.get(index)
        #print('You selected item %d: "%s"' % (index, value))
        if( value == 'NONE'):
            self.currlistidx = index
            return
        self.setimage( value )

        self.shootAgainButton["state"] = "normal"

    def busy(self):
        #print( "busy")
        self.parent.config(cursor="wait")
        self.parent.update()

    def notbusy(self):
        #print( "not busy")
        self.parent.config(cursor="")
        self.parent.update()

    def setimage(self,filename):
        manager.busy()
        ts_start = time.time()
        img = Image.open(filename)

        ts_middle1 = time.time()
        orig_w, orig_h = img.size
        new_w = self.imageview.winfo_width()
        new_h = self.imageview.winfo_height()
        print( orig_w, orig_h, new_w, new_h )
        scale_w = orig_w / new_w
        scale_h = orig_h / new_h
        new_img = img.resize((new_w-4, new_h-4))
        ts_middle2 = time.time()
        tkImg= ImageTk.PhotoImage(new_img)

        self.imageview.configure( image=tkImg )
        self.imageview.image = tkImg
        new_w2 = self.imageview.winfo_width()
        new_h2 = self.imageview.winfo_height()
        #print( orig_w, orig_h, new_w, new_h, new_w2, new_h2 )
        ts_end = time.time()
        print( "1, 2, 3", ts_middle1 - ts_start, ts_middle2 - ts_middle1, ts_end - ts_middle2, ts_end - ts_start )
        manager.notbusy()

#root=None
#def main():
root = Tk()
manager = BusyManager(root)
root.geometry("1024x768+150+150")
app = PTMFrame(root)
root.mainloop()


#if __name__ == '__main__':
#    main()