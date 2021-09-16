import wx
import sys
import vosk
import sounddevice as sd
import queue
import json
import threading
from time import sleep
from datetime import datetime
from pyautogui import write
from wx.core import Colour

# Settings
typingEnabled = False
preferences = {
    'device': None
}
textUpdateSpeed = 0.5

# Variables for storing speech to text output
q = queue.Queue()
currentText = ''
fullText = str(datetime.now()) + '\n'
saveFilePath = None

# Loading preferences
try:
    f = open('preferences.json', 'r')
    preferences = json.loads(f.read())
    f.close()
except FileNotFoundError:
    f = open('preferences.json', 'w')
    f.write(json.dumps(preferences))
    f.close()

if preferences['device'] == None:
    preferences['device'] = sd.default.device[0]

# Checking input device setting and initializing model
device_info = sd.query_devices(device=preferences['device'], kind='input')
samplerate = int(device_info['default_samplerate'])
model = vosk.Model('Model')

# Callback for the speech to text function
def callback(outdata, frames, time, status):
    """This is called (from a separate thread) for each audio block."""
    if status:
        print(status, file=sys.stderr)
    q.put(bytes(outdata))

# Detects text from speech input


def speechToText():
    with sd.InputStream(samplerate=samplerate, blocksize=8000, device=preferences['device'], dtype='int16',
                        channels=1, callback=callback):
        rec = vosk.KaldiRecognizer(model, samplerate)
        while True:
            data = q.get()
            if rec.AcceptWaveform(data):
                result = rec.Result()[14:-3]
                if result != '':
                    if typingEnabled:
                        write(result + "\n")
                    else:
                        global fullText
                        fullText += result + '\n'

            else:
                global currentText
                currentText = rec.PartialResult()[17:-3]


class MainFrame(wx.Frame):
    """
    The main frame of the application
    """

    def __init__(self, *args, **kw):
        super(MainFrame, self).__init__(*args, **kw)

        pnl = wx.Panel(self)
        pnl.SetBackgroundColour(Colour(32, 32, 32))

        self.st = wx.StaticText(pnl, label="Say Something")
        font = self.st.GetFont()
        font.PointSize += 5
        self.st.SetFont(font)
        self.st.SetForegroundColour(Colour(240, 249, 250))

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self.st, wx.SizerFlags().Border(wx.TOP | wx.LEFT, 25))
        pnl.SetSizer(sizer)

        self.makeMenuBar(self)
        self.CreateStatusBar()
        self.SetStatusText("Welcome to Captionator!")

        self.t = threading.Thread(target=self.updateCaptions)
        self.t.daemon = True
        self.t.start()

    def updateCaptions(self):
        while True:
            self.st.SetLabel(currentText)
            self.st.Wrap(int(self.Size[0] * .9))
            if typingEnabled:
                global fullText
                write(fullText)
                fullText = ''
            sleep(textUpdateSpeed)

    def makeMenuBar(self, sup):
        self.sup = sup

        # Options
        options = wx.Menu()

        save = options.Append(-1, "&Save",
                              "Select captions save location")
        saveAs = options.Append(wx.ID_ANY, "&Save As",
                              "Save captions")
        options.AppendSeparator()
        liveTyping = options.Append(wx.ID_ANY, "Toggle typing", "Toggle Live Typing", kind=wx.ITEM_CHECK)
        options.AppendSeparator()
        exitItem = options.Append(wx.ID_EXIT)

        # Device Selection
        deviceSelect = wx.Menu()

        devicesRaw = sd.query_devices()
        devices = {}
        for x in range(len(devicesRaw)):
            if (devicesRaw[x]['max_input_channels'] > 0):
                devices[x] = devicesRaw[x]['name']

        for x in devices:
            device = deviceSelect.AppendRadioItem(x, "&" + devices[x], "Use " + devices[x])
            if x == preferences['device']:
                device.Check(True)

        menuBar = wx.MenuBar()
        menuBar.Append(options, "&Options")
        menuBar.Append(deviceSelect, "&Device")

        self.SetMenuBar(menuBar)

        self.Bind(wx.EVT_MENU, self.saveToFile, save)
        self.Bind(wx.EVT_MENU, self.selectCaptionSaveFile, saveAs)
        self.Bind(wx.EVT_MENU, self.toggleTyping, liveTyping)
        self.Bind(wx.EVT_MENU, self.OnExit,  exitItem)

        for x in devices:
            self.Bind(wx.EVT_MENU, self.changeDevice, id=x)

    def OnExit(self, event):
        self.Close(True)

    def toggleTyping(self, event):
        global typingEnabled
        typingEnabled = not typingEnabled
        print(typingEnabled)

    def changeDevice(self, event):
        preferences['device'] = event.GetId()
        f = open('preferences.json', 'w')
        f.write(json.dumps(preferences))
        f.close()

    def saveToFile(self, event):
        global saveFilePath
        if saveFilePath == None:
            self.selectCaptionSaveFile(None)
            return

        global fullText
        f = open(saveFilePath, 'a')
        f.write(fullText)
        f.close()

        fullText = ''


    def selectCaptionSaveFile(self, event):
        with wx.FileDialog(self, "Select the save file location", wildcard='TXT files (*.txt)|*.txt', style=wx.FD_FILE_MUST_EXIST) as fileDialog:

            if fileDialog.ShowModal() == wx.ID_CANCEL:
                return     # the user changed their mind
            global saveFilePath
            saveFilePath = fileDialog.GetPath()
            global fullText
            f = open(saveFilePath, 'a')
            f.write(fullText)
            f.close()

            fullText = ''


if __name__ == '__main__':
    # Setting high DPI options
    try:
        from ctypes import OleDLL
        OleDLL('shcore').SetProcessDpiAwareness(1)
    except AttributeError:
        pass
    except OSError:
        pass

    # Starting thread for speech to text
    t = threading.Thread(target=speechToText)
    t.daemon = True
    t.start()

    # Creating and starting app
    app = wx.App(useBestVisual=True)
    frm = MainFrame(None, title='Captionator')
    frm.SetClientSize(frm.FromDIP(wx.Size(400, 300)))
    frm.Show()
    app.MainLoop()
