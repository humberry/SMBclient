# You need the impacket python module (http://corelabs.coresecurity.com)
# Extract the impacket directory to site-packages (https://pypi.python.org/packages/source/i/impacket/)
# and you also need a copy of ntpath.py in your site-package directory

import ui, os
import sys
import string
import time
from impacket import smb, version, smb3, nt_errors
from impacket.dcerpc.v5 import samr, transport, srvs
from impacket.dcerpc.v5.dtypes import NULL
from impacket.smbconnection import *
import time

class SMBclient(ui.View):

  def __init__(self):
    self.fileName = ''
    self.localFile = ''
    self.remoteFile = ''
    self.smb = None
    self.pwd = ''
    self.share = None
    self.loggedIn = False
    self.password = None
    self.username = None
    self.host = None 
    self.root = os.path.expanduser('~')
    self.path = os.getcwd()
    self.view = ui.load_view('SMBclient')
    self.view['bt_connect'].action = self.bt_connect
    self.view['bt_upload'].action = self.bt_upload
    self.view['bt_download'].action = self.bt_download
    self.view['bt_local_rename'].action = self.bt_local_rename
    self.view['bt_local_delete'].action = self.bt_local_delete
    self.view['bt_local_mkdir'].action = self.bt_local_mkdir
    self.view['bt_remote_rename'].action = self.bt_remote_rename
    self.view['bt_remote_delete'].action = self.bt_remote_delete
    self.view['bt_remote_mkdir'].action = self.bt_remote_mkdir
    self.view['bt_remote_rmdir'].action = self.bt_remote_rmdir
    root_len = len(self.root)
    self.view['lb_local'].text = self.path[root_len:]
    self.tv_local = self.view['tv_local']
    self.tv_remote = self.view['tv_remote']
    self.tv_info = self.view['tv_info']
    all = self.get_dir()
    self.lst_local = ui.ListDataSource(all)
    self.tv_local.data_source = self.lst_local
    self.tv_local.delegate = self.lst_local
    self.tv_local.editing = False
    self.lst_local.font = ('Courier',14)
    self.lst_local.action = self.table_local_tapped
    self.lst_local.delete_enabled = False 
    self.lst_remote = ui.ListDataSource([''])
    self.tv_remote.data_source = self.lst_remote
    self.tv_remote.delegate = self.lst_remote
    self.tv_remote.editing = False
    self.lst_remote.font = ('Courier',14)
    self.lst_remote.action = self.table_remote_tapped
    self.lst_remote.delete_enabled = False 
    self.view.present('fullscreen')

  def bt_local_rename(self, sender):
    pos = self.localFile.rfind('/')
    self.fileName = self.localFile[pos+1:]
    self.view_po = ui.load_view('popover')
    self.view_po.name = 'Rename'
    self.view_po.present('popover',popover_location=(self.view.width/2,self.view.height/2))
    self.view_po['lb_old_name'].text = self.fileName
    self.view_po['tf_new_name'].text = self.fileName
    self.view_po['bt_okay'].action = self.bt_local_rename_okay
    self.view_po['bt_cancel'].action = self.bt_cancel

  def bt_local_rename_okay(self, sender):
    os.rename(self.fileName, self.view_po['tf_new_name'].text)
    self.view_po.close()
    all = self.get_dir()
    self.refresh_table(self.tv_local,self.lst_local,all)

  def bt_cancel(self, sender):
    self.view_po.close()

  def bt_local_delete(self, sender):
    pos = self.localFile.rfind('/')
    self.fileName = self.localFile[pos+1:]
    self.view_po = ui.load_view('select')
    self.view_po.name = 'Delete local file?'
    self.view_po.present('popover',popover_location=(self.view.width/2,self.view.height/2))
    pos = self.localFile.rfind('/')
    fileName = self.localFile[pos+1:]
    self.view_po['tf_name'].text = self.fileName
    self.view_po['tf_name'].enabled = False
    self.view_po['bt_okay'].action = self.bt_select_okay_local_delete
    self.view_po['bt_cancel'].action = self.bt_cancel

  def bt_select_okay_local_delete(self, sender):
    def delete_files(filter=None):
      files =[]
      if filter == None:
        files = [self.view_po['tf_name'].text]
      else:
        #check filter
        if filter[0] == '*' and filter[1] == '.':
          filter = filter[1:]
        else:
          self.tv_info.text += "\nFilter not valid! It has to start with *."
          return
        files = []
        for entry in sorted(os.listdir(self.path)):
            if os.path.isfile(self.path + '/' + entry):
                if filter == '.*':
                  files.append(entry)
                else:
                  filter_len = len(filter)
                  entry_len = len(entry)
                  if entry.find(filter) == entry_len-filter_len:
                    files.append(entry)
      for file in files:
        os.remove(self.path + '/' + file)
    rang = self.view_po['sc_range'].selected_index
    if rang == 0: # selected file
      delete_files()
    elif rang == 1: # all files
      delete_files(filter='*.*')
    elif rang == 2: # filter
      delete_files(filter=self.view_po['tf_filter'].text)
    all = self.get_dir()
    self.refresh_table(self.tv_local,self.lst_local,all)
    self.view_po.close()

  def bt_local_mkdir(self, sender):
    self.view_po = ui.load_view('popover')
    self.view_po.name = 'Make Directory'
    self.view_po['lb_old_name'].hidden = True 
    self.view_po['lb_on'].hidden = True
    self.view_po.present('popover',popover_location=(self.view.width/2,self.view.height/2))
    self.view_po['lb_nn'].text = 'New Dir:'
    self.view_po['bt_cancel'].action = self.bt_cancel
    self.view_po['bt_okay'].action = self.bt_local_mkdir_okay

  def bt_local_mkdir_okay(self, sender):
    directory = self.view_po['tf_new_name'].text
    os.mkdir(self.path + '/' + directory)
    self.view_po.close()
    all = self.get_dir()
    self.refresh_table(self.tv_local,self.lst_local,all)

  def bt_remote_rename(self, sender):
    if self.loggedIn:
      pos = self.remoteFile.rfind('\\')
      self.fileName = self.remoteFile[pos+1:]
      self.view_po = ui.load_view('popover')
      self.view_po.present('popover',popover_location=(self.view.width/2,self.view.height/2))
      self.view_po['lb_old_name'].text = self.fileName
      self.view_po['tf_new_name'].text = self.fileName
      self.view_po['bt_okay'].action = self.bt_remote_rename_okay
      self.view_po['bt_cancel'].action = self.bt_cancel

  def bt_remote_rename_okay(self, sender):
    self.smb.rename(self.share, self.remoteFile, self.pwd + '\\' + self.view_po['tf_new_name'].text)
    self.view_po.close()
    all = self.get_remote_dir()
    self.refresh_table(self.tv_remote,self.lst_remote,all)

  def bt_remote_delete(self, sender):
    if self.loggedIn:
      pos = self.remoteFile.rfind('\\')
      self.fileName = self.remoteFile[pos+1:]
      self.view_po = ui.load_view('select')
      self.view_po.name = 'Delete remote file?'
      self.view_po.present('popover',popover_location=(self.view.width/2,self.view.height/2))
      self.view_po['tf_name'].text = self.fileName
      self.view_po['tf_name'].enabled = False
      self.view_po['bt_okay'].action = self.bt_select_okay_remote_delete
      self.view_po['bt_cancel'].action = self.bt_cancel

  def bt_select_okay_remote_delete(self, sender):
    def delete_files(filter=None):
      files =[]
      if filter == None:
        files = [self.view_po['tf_name'].text]
      else:
        #check filter
        if filter[0] != '*' and filter[1] != '.':
          self.tv_info.text += "\nFilter not valid! It has to start with *."
          return
        entries = self.smb.listPath(self.share, self.pwd + '\\' + filter)
        filter = filter[1:]
        for e in entries:
          if e.is_directory() == 0:
            entry = str(e.get_longname())
            if filter == '.*':
              files.append(entry)
            else:
              filter_len = len(filter)
              entry_len = len(entry)
              if entry.find(filter) == entry_len-filter_len:
                files.append(entry)
      for file in files:
        self.smb.deleteFile(self.share, self.pwd + '\\' + file)
    rang = self.view_po['sc_range'].selected_index
    if rang == 0: # selected file
      delete_files()
    elif rang == 1: # all files
      delete_files(filter='*.*')
    elif rang == 2: # filter
      delete_files(filter=self.view_po['tf_filter'].text)
    all = self.get_remote_dir()
    self.refresh_table(self.tv_remote,self.lst_remote,all)
    self.view_po.close()

  def bt_remote_rmdir(self, sender):
    if self.loggedIn:
      self.view_po = ui.load_view('popover')
      self.view_po.name = 'Remove Directory'
      self.view_po['lb_old_name'].text = self.pwd + '\\'
      self.view_po['lb_on'].text = 'Path:'
      self.view_po.present('popover',popover_location=(self.view.width/2,self.view.height/2))
      self.view_po['lb_nn'].text = 'Remove Dir:'
      self.view_po['bt_cancel'].action = self.bt_cancel
      self.view_po['bt_okay'].action = self.bt_remote_rmdir_okay

  def bt_remote_rmdir_okay(self, sender):
    directory = self.view_po['tf_new_name'].text
    if self.pwd == '\\' and directory == '':
      self.tv_info.text += "\nSorry, root directory is not removable."
    else:
      try:
        self.smb.deleteDirectory(self.share,self.pwd + '\\' + directory)
      except Exception, e:
        self.tv_info.text += '\n' + str(e)
    self.view_po.close()
    all = self.get_remote_dir()
    self.refresh_table(self.tv_remote,self.lst_remote,all)

  def bt_remote_mkdir(self, sender):
    if self.loggedIn:
      self.view_po = ui.load_view('popover')
      self.view_po.name = 'Make Directory'
      self.view_po['lb_old_name'].text = self.pwd + '\\'
      self.view_po['lb_on'].text = 'Path:'
      self.view_po.present('popover',popover_location=(self.view.width/2,self.view.height/2))
      self.view_po['lb_nn'].text = 'New Dir:'
      self.view_po['bt_cancel'].action = self.bt_cancel
      self.view_po['bt_okay'].action = self.bt_remote_mkdir_okay

  def bt_remote_mkdir_okay(self, sender):
    directory = self.view_po['tf_new_name'].text
    if self.pwd == '\\':
      self.smb.createDirectory(self.share,self.pwd + directory)
    else:
      self.smb.createDirectory(self.share,self.pwd + '\\' + directory)
    self.view_po.close()
    all = self.get_remote_dir()
    self.refresh_table(self.tv_remote,self.lst_remote,all)

  def bt_connect(self, sender):
    hostshare = self.view['tf_host'].text
    if hostshare.find('/') > 0:
      self.host, self.share = hostshare.split('/')
    self.username = self.view['tf_user'].text
    self.password = self.view['tf_password'].text
    
    if self.loggedIn is False:
      try:
        self.smb = SMBConnection('*SMBSERVER', self.host, sess_port=139)
        dialect = self.smb.getDialect()
        if dialect == SMB_DIALECT:
          self.tv_info.text = "SMBv1 dialect used"
        elif dialect == SMB2_DIALECT_002:
          self.tv_info.text = "SMBv2.0 dialect used"
        elif dialect == SMB2_DIALECT_21:
          self.tv_info.text = "SMBv2.1 dialect used"
        else:
          self.tv_info.text = "SMBv3.0 dialect used"
        if self.smb is None:
          self.tv_info.text = "No connection open"
          return
        self.smb.login(self.username, self.password, domain='')
        if self.smb.isGuestSession() > 0:
          self.tv_info.text += "\nGUEST Session Granted"
        else:
          self.tv_info.text += "\nUSER Session Granted"
        self.loggedIn = True
        self.smb.connectTree(self.share)
        self.pwd = '\\'
        all = self.get_remote_dir()
        self.refresh_table(self.tv_remote,self.lst_remote,all)
        self.view['lb_remote'].text = self.pwd
        sender.title = 'Disconnect'
      except Exception, e:
        self.tv_info.text += '\n' + str(e)
        self.loggedIn = False 
    else:
      if self.smb is not None:
        del(self.smb);
      self.share = None
      self.pwd = ''
      self.loggedIn = False
      self.password = None
      self.username = None
      sender.title = 'Connect'
      self.tv_info.text += "\nConnection closed"

  def bt_upload(self, sender):	#put
    if self.loggedIn:
      self.view_po = ui.load_view('select')
      self.view_po.name = 'Upload'
      self.view_po.present('popover',popover_location=(self.view.width/2,self.view.height/2))
      pos = self.localFile.rfind('/')
      fileName = self.localFile[pos+1:]
      self.view_po['tf_name'].text = fileName
      self.view_po['tf_name'].enabled = False
      self.view_po['bt_okay'].action = self.bt_select_okay_put
      self.view_po['bt_cancel'].action = self.bt_cancel

  def bt_select_okay_put(self, sender):
    def write_files(filter=None):
      files =[]
      if filter == None:
        files = [self.view_po['tf_name'].text]
      else:
        #check filter
        if filter[0] == '*' and filter[1] == '.':
          filter = filter[1:]
        else:
          self.tv_info.text += "\nFilter not valid! It has to start with *."
          return
        files = []
        for entry in sorted(os.listdir(self.path)):
            if os.path.isfile(self.path + '/' + entry):
                if filter == '.*':
                  files.append(entry)
                else:
                  filter_len = len(filter)
                  entry_len = len(entry)
                  if entry.find(filter) == entry_len-filter_len:
                    files.append(entry)
      for file in files:
        fh = open(self.path + '/' + file, 'rb')
        if self.pwd == '\\':
          self.smb.putFile(self.share, self.pwd + file, fh.read)
        else:
          self.smb.putFile(self.share, self.pwd + '\\' + file, fh.read)
        fh.close()
    rang = self.view_po['sc_range'].selected_index
    if rang == 0: # selected file
      write_files()
    elif rang == 1: # all files
      write_files(filter='*.*')
    elif rang == 2: # filter
      write_files(filter=self.view_po['tf_filter'].text)
    all = self.get_remote_dir()
    self.refresh_table(self.tv_remote,self.lst_remote,all)
    self.view_po.close()

  def bt_download(self, sender):	#get
    if self.loggedIn:
      self.view_po = ui.load_view('select')
      self.view_po.name = 'Download'
      self.view_po.present('popover',popover_location=(self.view.width/2,self.view.height/2))
      pos = self.remoteFile.rfind('\\')
      fileName = self.remoteFile[pos+1:]
      self.view_po['tf_name'].text = fileName
      self.view_po['tf_name'].enabled = False
      self.view_po['bt_okay'].action = self.bt_select_okay_get
      self.view_po['bt_cancel'].action = self.bt_cancel

  def bt_select_okay_get(self, sender):
    def write_files(filter=None):
      files =[]
      if filter == None:
        files = [self.view_po['tf_name'].text]
      else:
        #check filter
        if filter[0] != '*' and filter[1] != '.':
          self.tv_info.text += "\nFilter not valid! It has to start with *."
          return
        entries = self.smb.listPath(self.share, self.pwd + '\\' + filter)
        filter = filter[1:]
        for e in entries:
          if e.is_directory() == 0:
            entry = str(e.get_longname())
            if filter == '.*':
              files.append(entry)
            else:
              filter_len = len(filter)
              entry_len = len(entry)
              if entry.find(filter) == entry_len-filter_len:
                files.append(entry)
      for file in files:
        fh = open(self.path + '/' + file,'wb')
        try:
          self.smb.getFile(self.share, self.pwd + '\\' + file, fh.write)
        except:
          fh.close()
          os.remove(self.path + '/' + file)
        fh.close()
    rang = self.view_po['sc_range'].selected_index
    if rang == 0: # selected file
      write_files()
    elif rang == 1: # all files
      write_files(filter='*.*')
    elif rang == 2: # filter
      write_files(filter=self.view_po['tf_filter'].text)
    all = self.get_dir()
    self.refresh_table(self.tv_local,self.lst_local,all)
    self.view_po.close()

  def table_local_tapped(self, sender):
    rowtext = sender.items[sender.selected_row]
    filename_tapped = rowtext
    if rowtext[0] == '/':
      if filename_tapped == '/..':
        pos = self.path.rfind('/')
        self.path = self.path[:pos]
      else:
        self.path = self.path + filename_tapped
      all = self.get_dir()
      root_len = len(self.root)
      self.view['lb_local'].text = self.path[root_len:]
      self.refresh_table(self.view['tv_local'],self.lst_local,all)
    else:
      self.localFile = self.path + '/' + filename_tapped

  def table_remote_tapped(self, sender):
    rowtext = sender.items[sender.selected_row]
    filename_tapped = rowtext
    if rowtext[0] == '\\': #directory
      if filename_tapped == '\\..': # up
        pos = self.pwd.rfind('\\')
        self.pwd = self.pwd[:pos]
        if self.pwd == '': # root
          self.pwd = '\\'
      else:
        if self.pwd == '\\': # root
          self.pwd = filename_tapped
        else:
          self.pwd += filename_tapped
      all = self.get_remote_dir()
      self.refresh_table(self.tv_remote,self.lst_remote,all)
      self.view['lb_remote'].text = self.pwd
    else: # file
      self.remoteFile = self.pwd + '\\' + filename_tapped

  def refresh_table(self, table, lst, data):
    lst = ui.ListDataSource(data)
    table.data_source = lst
    table.delegate = lst
    table.editing = False
    lst.font = ('Courier',14)
    if table.name == 'tv_local':
      lst.action = self.table_local_tapped
    else:
      lst.action = self.table_remote_tapped
    lst.delete_enabled = False 
    table.reload_data()
    return

  def get_dir(self):
    dirs  = [] if self.path == self.root else ['..']
    files = []
    for entry in sorted(os.listdir(self.path)):
      if os.path.isdir(self.path + '/' + entry):
        dirs.append(entry)
      else:
        files.append(entry)
    all = ['/' + dir for dir in dirs]
    for file in files:
      full_pathname = self.path + '/' + file
      all.append('{}'.format(file))
    return all

  def get_remote_dir(self):
    if self.loggedIn:
      remoteDir  = [] if self.pwd == '\\' else ['\\..']
      files = []
      entries = self.smb.listPath(self.share, self.pwd + '\\*')
      for e in entries:
        if e.is_directory() > 0:
          if str(e.get_longname()) != '.' and str(e.get_longname()) != '..':
            remoteDir.append('\\' + str(e.get_longname()))
        else:
          files.append(str(e.get_longname()))
      all = sorted(remoteDir)
      for file in sorted(files):
        all.append('{}'.format(file))
      return all
    else:
      self.pwd = ''
      return []
    
    #e.get_filesize()
    #time.ctime(float(e.get_mtime_epoch()))

SMBclient()
