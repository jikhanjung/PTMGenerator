from tkinter import Tk, RIGHT, LEFT, BOTTOM, BOTH, X,Y, RAISED, filedialog, Listbox, messagebox, Label, Entry, END
from tkinter.ttk import Frame, Button, Style
from pathlib import Path
import subprocess
import math
import time
import serial
from PIL import ImageTk, Image
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

        frame1 = Frame(self, relief=RAISED, borderwidth=1)
        frame1.pack(fill=BOTH, expand=True)
        self.listbox = Listbox(frame1)
        self.listbox.pack(side=LEFT,fill=Y,padx=5,pady=5,ipadx=5,ipady=5)
        self.imageview = Label(frame1)
        self.imageview.pack(side=LEFT, fill=BOTH, expand=True)
        self.listbox.bind('<<ListboxSelect>>', self.onselect )

        frame2 = Frame(self, relief=RAISED, borderwidth=1)
        frame2.pack(fill=X)
        self.workdir_label = Label(frame2, text='Work Dir')
        self.workdir_label.pack(side=LEFT,fill=X,padx=5,pady=5)
        self.workdir_text = Entry(frame2,text='')
        self.workdir_text.pack(side=LEFT,fill=X,expand=True,padx=5,pady=5)
        self.workdirButton = Button(frame2, text="Open Dir", command=self.opendir)
        self.workdirButton.pack(side=LEFT, fill=X,padx=5,pady=5)

        frame3 = Frame(self)
        self.fitter_label = Label(frame3, text='PTMFitter')
        self.fitter_label.pack(side=LEFT,fill=X,padx=5,pady=5)
        self.fitter_text = Entry(frame3,text='',textvariable = self.fitter_filepath_str)
        self.fitter_text.pack(side=LEFT,fill=X,expand=True,padx=5,pady=5)
        self.ptmButton = Button(frame3, text="PTMFitter", command=self.PTMfitter)
        self.ptmButton.pack(side=LEFT, fill=X,padx=5,pady=5)
        frame3.pack(fill=X)


        frame4 = Frame(self)
        self.takePicturesButton = Button(frame4, text="Take Pictures",command=self.takePictures)
        self.takePicturesButton.pack( side=LEFT, fill=X,padx=5, pady=5)
        self.generateButton = Button(frame4, text="Generate PTM File",command=self.generatePTM)
        self.generateButton.pack( side=LEFT, fill=X,padx=5, pady=5)
        frame4.pack(fill=X)

        self.pack(fill=BOTH, expand=True)
        options = {}
        options['initialdir'] = 'C:\\'
        options['mustexist'] = False
        options['parent'] = self.parent
        options['title'] = 'This is a title'

        self.filelist = []
        fitter = Path.cwd().joinpath("ptmfitter.exe")
        if fitter.exists():
            self.fitter_filepath = fitter
            self.fitter_text.delete(0, END)
            self.fitter_text.insert(0, str(fitter))

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
    def opendir(self):
        #print( "open")
        dirname = filedialog.askdirectory(initialdir="\\", title="Select directory")
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
    def takePictures(self):
        self.serial = serial.Serial()
        self.serial.port='/dev/ttyUSB4'
        self.serial.baudrate=9600
        self.serial.parity=serial.PARITY_ODD
        self.serial.stopbits=serial.STOPBITS_TWO
        self.serial.bytesize=serial.SEVENBITS

        try:
            self.serial.open()
        except Exception as e:
            print( "error open serial port: " + str(e) )
            return

        for i in range(1,51):
            self.serial.write(str(i)+'\r\n')


    def onselect(self,evt):
        w = evt.widget
        index = int(w.curselection()[0])
        value = w.get(index)
        #print('You selected item %d: "%s"' % (index, value))
        self.setimage( self.workingpath.joinpath( value ) )

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
        #print( orig_w, orig_h, new_w, new_h )
        scale_w = orig_w / new_w
        scale_h = orig_h / new_h
        new_img = img.resize((new_w, new_h-4))
        ts_middle2 = time.time()
        tkImg= ImageTk.PhotoImage(new_img)

        self.imageview.configure( image=tkImg )
        self.imageview.image = tkImg
        new_w2 = self.imageview.winfo_width()
        new_h2 = self.imageview.winfo_height()
        #print( orig_w, orig_h, new_w, new_h, new_w2, new_h2 )
        ts_end = time.time()
        #print( "1, 2, 3", ts_middle1 - ts_start, ts_middle2 - ts_middle1, ts_end - ts_middle2, ts_end - ts_start )
        manager.notbusy()
#root=None
#def main():
root = Tk()
manager = BusyManager(root)
root.geometry("640x480+300+300")
app = PTMFrame(root)
root.mainloop()


#if __name__ == '__main__':
#    main()