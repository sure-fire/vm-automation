"""
GOOD RESOURCE: http://programtalk.com/python-examples/pyVmomi.vim.vm.guest.NamePasswordAuthentication/
"""


from pyVim.connect import SmartConnect, Disconnect
from pyVmomi import vim, vmodl

from datetime import datetime
import atexit
import requests
from socket import error as SocketError
import ssl
import time

class esxiServer:
    """
    THE esxiServer CLASS IS A CLASS THAT STORES INFORMATION ON AND SIMPLIFIES INTERACTION 
    WITH AN ESXI SERVER.
    """
    def __init__(self, hostname, username, password, port, logFile = "defaultLogfile.log"):
        self.hostname = hostname
        self.username = username
        self.password = password
        self.logFile = logFile 
        self.port = port
        self.vmList = []
        self.fullName = ""
        self.connection = None

    def connect(self):
        """
        connect() INTITATES A CONNECTION TO THE ESXi SERVER AND STORES THE RESULT IN 
        THE CLASS VARIABLE connection.  AFTER THE INTITIAL CONNECT, MEMBER FUNCTUONS 
        USE THE connection VARIABLE.
        """
        retVal = True
        context = None
        if hasattr(ssl, '_create_unverified_context'):
            context = ssl._create_unverified_context()
            try:
                self.connection = SmartConnect(host=self.hostname,
                                               user=self.username,
                                               pwd=self.password,
                                               port=int(self.port),
                                               sslContext=context)
            except SocketError as e:
                self.logMsg("[ERROR]: CANNOT CONTACT SERVER " + self.hostname)
                self.logMsg("SYSTEM ERROR MESSAGE:\n" + str(e))
                retVal = False
            except vim.fault.InvalidLogin as e:
                self.logMsg("[ERROR]: INCORRECT USERNAME/PASSWORD FOR " + self.hostname)
                self.logMsg("SYSTEM ERROR MESSAGE:\n" + str(e))
                retVal = False
            except vim.fault.NoPermission as e:
                self.logMsg("[ERROR]: INCORRECT PERMISSIONS TO LOGIN FOR USER " + self.username + "@" + self.hostname)
                self.logMsg("SYSTEM ERROR MESSAGE:\n" + str(e))
                retVal = False
            except Exception as e:
                self.logMsg("[ERROR]: UNKNOWN ERROR (SORRY!) WHILE CONNECTING TO" + self.hostname)
                self.logMsg("SYSTEM ERROR MESSAGE:\n" + str(e))
                retVal = False
            else:
                if not self.connection:
                    self.logMsg("CONNECTION TO" + self.hostname + " WAS UNSUCCESSFUL")
                    retVal = False
                else:
                    retVal = True
            atexit.register(Disconnect, self.connection)
        return retVal
    
    def logMsg(self, strMsg):
		if strMsg == None:
			strMsg="[None]"
		dateStamp = 'serverlog:[' + str(datetime.now())+ '] '
		#DELETE THIS LATER:
		print dateStamp + strMsg
		try:
			logFileObj = open(self.logFile, 'ab')
			logFileObj.write(dateStamp + strMsg + '\n')
			logFileObj.close()
		except IOError:
			return False
		return True
    
    def waitForVmsToBoot(self, vmList):
        """
        IF YOU TRY AND INTERACT WITH A VM BEFORE IT FINISHES LOADING VMWARE TOOLS, IT CAUSES A FAULT AND CRASHES
        IF YOU TRY AND INTERACT WITH A VM BEFORE IT FINISHES BOOTING, IT CAUSES A FAULT AND CRASHES
        IF YOU TRY AND CHECK IF IT BOOTED BEFORE TOOLS ARE RUNNING, IT CAUSES A FAULT AND CRASHES
        THIS JUST POLLS THE TOOLS INSTALLATION UNTIL TOOLS REPONDS CORRECTLY, THEN STARTS ASKING FOR THE IP
        ADDRESS.  ONCE THE IP ADDRESS COMES UP, YOU CAN USE IT.
        """
        self.logMsg("WAITING FOR VMS TO BE READY; THIS COULD TAKE A FEW MINUTES")
        vmsReady = False
        while(vmsReady == False):
            vmsReady = True
            for i in vmList:
                if i.isPoweredOn() == False:
                    time.sleep(1)
                    self.logMsg(i.vmName + " DID NOT POWER ON AS EXPECTED; RETRYING")
                    i.powerOn(True)
                if i.checkTools(True) == False:
                    vmsReady = False
            time.sleep(1)
        retVal = True
        self.logMsg("VMS APPEAR TO BE READY; PULLING IP ADDRESSES TO VERIFY")
        time.sleep(5)
        for i in vmList:
            for j in range(5):
                ipAddress = i.getVmIp()
                if ipAddress != None:
                    break;
                else:
                    self.logMsg("IP ADDRESS LOOKUP FAILED FOR " + i.vmName + " = " + str(ipAddress))
                time.sleep(1)
            if ipAddress == None:
                retVal = False
                self.logMsg(i.vmName + " FAILED TO INITIALIZE")
            else:
                self.logMsg("IP ADDRESS FOR " + i.vmName + " = " + ipAddress)
        return retVal

    
    
    def enumerateVms(self, negFilter = None):
        """
        THERE ARE SEVERAL WAYS TO ENUMERATE VMs. THIS IS BY FAR THE EASIEST, 
        BUT I AM NOT SURE IF IT WILL WORK ON LARGER DEPLOYMENTS BECAUSE OF
        vSPHERE'S HEIRARCHIAL STORAGE METHODOLOGY
        """
        content = self.connection.content
        objView = content.viewManager.CreateContainerView(content.rootFolder,
                                                          [vim.VirtualMachine],
                                                          True)
        vimVmList = objView.view
        objView.Destroy()
        for i in vimVmList:
            if negFilter != None and negFilter.upper() in i.name.upper():
                continue
            else:
                self.vmList.append(esxiVm(self, i))
        
    def getVersion(self):
        """
        RETURNS ESXI VERSION
        """
        content = self.connection.RetrieveContent()
        self.fullName = content.about.fullName
        return self.fullName

class esxiVm:
    def __init__(self, serverObject, vmObject):
        self.server =           serverObject
        self.vmObject =         vmObject
        self.procList =         []
        self.revertSnapshots =  []
        self.snapshotList =     []
        self.testVm =           False
        self.vmIdentifier =     vmObject.summary.config.vmPathName
        self.vmIp =             None
        self.vmName =           vmObject.summary.config.name
        self.vmOS =             vmObject.summary.config.guestFullName
        self.vmPassword =       ""
        self.vmUsername =       ""
        self.uploadDir =        ""
        self.payloadList =      []
        self.resultDict =       {}
        if '64-bit' in self.vmOS:
            self.arch = 'x64'
        else:
            self.arch = 'x86'
        
    def checkTools(self, waitForTools = True):
        """
        THERE HAS TO BE A BETTER WAY TO DO THIS....
        WHEN I WROTE IT, THERE WERE ONLY 2 POSSIBLE VALUES, ON AND NOT ON YET...
        THERE ARE A FEW OPTIONS I FOUND LATER THAT ARE THE EQUIVALENT OF "NEVER COMING ON, YOU BETTER QUIT"
            DIFFICULT TO EXIT FROM WITHIN A FUNCTION, AND RETURNING False MEANS "WAIT"
            PROBABLY NEED TO TRUNCATE THIS TO 
                CHECKING FOR STATE, 
                ENCAPSULATE WITH try/except
                RETURN STRING OR FLAG FOR "READY" "NOT READY" "FAULT"
        """
        tools_status = self.vmObject.guest.toolsStatus
        if tools_status == 'toolsNotRunning':
            retVal = False
        elif tools_status == 'toolsOld':
            self.server.logMsg("YOU SHOULD UPGRADE THE VMWARE TOOLS ON " + self.vmName)
            retVal = True
        elif tools_status == 'toolsNotInstalled':
            self.server.logMsg("YOU SHOULD INSTALL VMWARE TOOLS ON " + self.vmName)
            retVal = False
        elif tools_status == 'toolsOk':
            retVal = True
        else:
            self.server.logMsg("UNKNOWN STATE OF VMWARE TOOLS ON " + self.vmName + "::" +tools_status)
            retVal = False
        return retVal
                
    def deleteSnapshot(self, snapshotName):
        self.getSnapshots()
        for i in self.snapshotList:
            if i[0].name == snapshotName:
                self.server.logMsg("DELETING SNAPSHOT " + snapshotName + " FROM " + self.vmName)
                return self.waitForTask(i[0].snapshot.RemoveSnapshot_Task(False))
            
    def enumerateSnapshotsRecursively(self, snapshots, snapshot_location):
        if not snapshots:
            return
        
        for snapshot in snapshots:
            if snapshot_location:
                current_snapshot_path = snapshot_location + '/' + snapshot.name
            else:
                current_snapshot_path = snapshot.name
            self.snapshotList.append((snapshot, current_snapshot_path))
            self.enumerateSnapshotsRecursively(snapshot.childSnapshotList, current_snapshot_path)
        return

    def getArch(self):
        return self.arch

    def getFileFromGuest(self, srcFile, dstFile):
        for i in range(3):
            self.server.logMsg("ATTEMPTING TO GET " +srcFile)
            retVal = False
            if self.checkTools():
                creds = vim.vm.guest.NamePasswordAuthentication(username=self.vmUsername, 
                                                                password=self.vmPassword)
                content = self.server.connection.RetrieveContent()
                try:
                    file_attribute = vim.vm.guest.FileManager.FileAttributes()
                    vmFileManager = content.guestOperationsManager.fileManager
                    ftInfo = vmFileManager.InitiateFileTransferFromGuest(self.vmObject, 
                                                                    creds, 
                                                                    srcFile)
                    #THIS IS STUPID, BUT THERE IS SOME ASSEMBLY REQUIRED
                    splitUrl = ftInfo.url.split('*')
                    realUrl = splitUrl[0] + self.server.hostname + splitUrl[1]
                    self.server.logMsg(srcFile + " URL = " + realUrl)
                    self.server.logMsg(srcFile +" SIZE = " + str(ftInfo.size))
                    resp = requests.get(realUrl, verify=False)
                    if not resp.status_code == 200:
                        self.server.logMsg("ERROR GETTING FILE " + \
                                          srcFile + " FROM " +\
                                          self.vmName + " HTTP CODE " + \
                                          str(resp.status_code))
                        retVal = True
                    else:
                        getFile = open(dstFile, 'wb')
                        getFile.write(resp.content)
                        getFile.close()
                        self.server.logMsg("SAVED FILE FROM " + self.vmName + \
                                          " AS " + dstFile + \
                                          " HTTP RESPONSE WAS " + str(resp.status_code))
                        retVal=True
                except IOError, e:
                    self.server.logMsg(str(e))
                    pass
                #SOMETIMES THE VM GETS SQUIRRLEY; IF SO, JUST TRY AGAIN
                except Exception as e:
                    self.server.logMsg("VM IN A STRANGE STATE; SKIPPING PROCESSLIST UPDATE:\n" + str(e))
                    continue
            else:
                self.server.logMsg("THERE IS A PROBLEM WITH THE VMWARE TOOLS ON " + self.vmName)
            return retVal
                
    def getSnapshots(self):
        """
        SEARCHING FOR SNAPSHOTS IS UNPLEASANT
        SINCE SNAPSHOTS ARE NESTED, RECURSIVE CALLS ARE NECESSARY
        """
        self.server.logMsg("FINDING SNAPSHOTS FOR " + self.vmName)
        self.snapshotList = []
        if hasattr(self.vmObject.snapshot, 'rootSnapshotList'):
            self.enumerateSnapshotsRecursively(self.vmObject.snapshot.rootSnapshotList, '')
        return
        
    def getVmIp(self):
        """ 
        IT IS POSSIBLE TO GET NO IP ADDRESS IN THE GAP BETWEEN WHEN VMWARE 
        TOOLS FINISHES LOADING AND BEFORE NETWORKING SERVICES START
        THIS WILL TRY TO GET THE IP ADDRESS FOR 2 MINUTES
        """
        ipAttempts = 120
        for i in range(ipAttempts):
            self.vmIp = self.vmObject.summary.guest.ipAddress
            if self.vmIp != None:
                break
            else:
                strAttempt = "(ATTEMPT " + str(i) + " OF " + str(ipAttempts) + ")"
                self.server.logMsg(strAttempt + " FAILED TO GET IP ADDRESS FROM " + self.vmName)
                time.sleep(1)
        return self.vmIp
    
    def getUsername(self):
        return self.vmUsername
    
    def isTestVm(self):
        return self.testVm

    def isPoweredOff(self):
        return not self.isPoweredOn()
    
    def isPoweredOn(self):
        if self.vmObject.runtime.powerState == vim.VirtualMachinePowerState.poweredOn:
            return True
        else:
            return False
    
    def makeDirOnGuest(self, dirPath):
        self.server.logMsg("CREATING " + dirPath + " ON " + self.vmName + " ")
        retVal = True
        if self.checkTools():
            creds = vim.vm.guest.NamePasswordAuthentication(username=self.vmUsername, 
                                                                      password=self.vmPassword)
            content = self.server.connection.RetrieveContent()
            try:
                content.guestOperationsManager.fileManager.MakeDirectoryInGuest(self.vmObject, 
                                                                                creds, 
                                                                                dirPath, 
                                                                                False)
                retVal = True
            except IOError as e:
                self.server.logMsg("[ERROR]: FILE NOT FOUND")
                self.server.logMsg("SYSTEM ERROR: " + str(e))
                retVal = False
            except vim.fault.InvalidGuestLogin as f:
                self.server.logMsg("[WARNING]: DIRECTORY " + dirPath + " ALREADY EXISTS ON " + self.vmName)
                self.server.logMsg("SYSTEM ERROR: " + str(f))
                retVal = True
            except vim.fault.InvalidGuestLogin as g:
                self.server.logMsg("[ERROR]: INCORRECT USERNAME/PASSWORD PROVIDED FOR " + self.vmName)
                self.server.logMsg("SYSTEM ERROR: " + str(g))
                retVal = False
            except Exception as g:
                self.server.logMsg("[ERROR]: UNKNOWN EXCEPTION WHILE MAKING " + dirPath + " ON " + self.vmName)
                self.server.logMsg("SYSTEM ERROR: " + str(g))
                retVal = False
        else:
            self.server.logMsg("ERROR: VMWARE TOOLS NOT INSTALLED ON " + self.vmName)
            retVal = False
        return retVal

    def powerOn(self, asyncFlag = False):
        """
        WARNING: DURING POWER-ON, TOOLS CAN GET INTO TEMPORARY FUNKY STATES WHERE IT WILL 
        ACCEPT COMMANDS AS THOUGH IT IS RUNNING, BUT THEN IT REALIZES THAT ITS NOT READY, 
        AND FAULTS OUT FOR UNPREDICTABLE AND ODD REASONS.  I DO NOT SUGGEST THAT YOU CALL THIS
        WITH asyncFlag SET TO True, BUT IT IS YOUR LIFE, AND I AM NOT YOUR MOTHER. 
        DO WHAT YOU WANT.
        """
        if self.isPoweredOn():
            self.server.logMsg(self.vmName + " IS ALREADY RUNNING, CANNOT POWER-ON HARDER")
            return None
        else:
            self.server.logMsg("POWERING ON " + self.vmName)
            if asyncFlag:
                return self.vmObject.PowerOnVM_Task()
            else:
                return self.waitForTask(self.vmObject.PowerOnVM_Task())
    
    def powerOff(self, asyncFlag = False):
        if self.isPoweredOff():
            self.server.logMsg(self.vmName + " IS ALREADY OFF, CANNOT POWER-OFF HARDER")
            return None
        else:
            self.server.logMsg("POWERING OFF " + self.vmName)
            if asyncFlag:
                return self.vmObject.PowerOnVM_Task()
            else:
                return self.waitForTask(self.vmObject.PowerOffVM_Task())

    def prepVm(self):
        """
        prepVm USED TO RUN A BUNCH OF COMMANDS TO PREP THE VM, BUT I'VE OFFLOADED MOST
        OF THEM TO powerOn WITH THE ASYNC FLAG, SO THIS IS A KIND OF A SAD FUNCTION, NOW.
        
        """
        self.server.logMsg("PREPARING " + self.vmName + " FOR TESTING")
        self.server.logMsg(self.vmName + " OPERATING SYSTEM: " + self.vmOS)
        self.server.logMsg(self.vmName + " ARCHITECTURE: " + self.getArch())
        self.getSnapshots()
        self.powerOn(False)

    def revertToTestingBase(self):
        self.server.logMsg("RESETTING VM " + self.vmName)
        self.getSnapshots()
        for i in self.snapshotList:
            if 'testing_base' in i[0].name.lower():
                self.server.logMsg("REVERTING VM TO " + i[0].name)
                return self.revertToSnapshot(i[0].snapshot)
        return None

    def revertToSnapshot(self, snapshotObj):
        return self.waitForTask(snapshotObj.RevertToSnapshot_Task())
        
    def revertDevVm(self):
        self.getSnapshots()
        for i in self.snapshotList:
            if "PAYLOAD_TESTING-" in i[0].name:
                self.server.logMsg("REVERTING " + self.vmName + " TO " + i[0].name)
                self.revertToSnapshot(i[0].snapshot)
                self.deleteSnapshot(i[0].name)

    def runCmdOnGuest(self, cmdAndArgList):
        self.server.logMsg("RUNNING '" + ' '.join(cmdAndArgList) + "' ON " + self.vmName)
        if self.checkTools():
            try:
                creds = vim.vm.guest.NamePasswordAuthentication(username=self.vmUsername, 
                                                                password=self.vmPassword)
                content = self.server.connection.RetrieveContent()
                cmdspec = vim.vm.guest.ProcessManager.ProgramSpec(programPath=cmdAndArgList[0],
                                                                  arguments=' '.join(cmdAndArgList[1:]))
                cmdpid = content.guestOperationsManager.processManager.StartProgramInGuest(vm=self.vmObject, 
                                                                                           auth=creds, 
                                                                                           spec=cmdspec)
                retVal = cmdpid
                self.server.logMsg("LAUNCHING '" + ' '.join(cmdAndArgList) + "' ON " + self.vmName)
                retVal = True
            except vim.fault.InvalidGuestLogin as e:
                self.server.logMsg("INCORRECT USERTNAME/PASSWORD PROVIDED FOR " + self.vmName)
                self.server.logMsg("SYSTEM ERROR:\n" + str(e))
                retVal = False
            except vim.fault.GuestPermissionDenied as f:
                self.server.logMsg("INSUFFICIENT PERMISSIONS TO RUN " + \
                                  ' '.join(cmdAndArgList) + " ON " + self.vmName)
                self.server.logMsg("SYSTEM ERROR:\n" + str(f))                
                retVal = False
        else:
            self.server.logMsg("FAILED TO RUN '" + ' '.join(cmdAndArgList) + "' ON " + self.vmName)
            retVal = False
        return retVal
 
    def setPassword(self, vmPassword):
        self.vmPassword = vmPassword

    def setTestVm(self):
        self.testVm = True
        
    def setUsername(self, vmUsername):
        self.vmUsername = vmUsername

    def setVmIp(self, ipAddress):
        self.vmIp = ipAddress
        return True
    
    def takeSnapshot(self, 
                     snapshotName, 
                     asyncFlag = False,
                     snapshotDescription = '',
                     dumpMemory = False, 
                     setQuiescent = False):
        self.server.logMsg("TAKING SNAPSHOT " + snapshotName + " ON " + self.vmName)
        snapshotTask = self.vmObject.CreateSnapshot_Task(snapshotName, 
                                                      snapshotDescription, 
                                                      dumpMemory, 
                                                      setQuiescent)
        if not asyncFlag:
            return self.waitForTask(snapshotTask)
        else:
            return None

    def takeTempSnapshot(self, asyncFlag = False):
        snapshotName = "PAYLOAD_TESTING-" + str(time.time()).split('.')[0]
        return self.takeSnapshot(snapshotName, asyncFlag)
    
    def updateProcList(self):
        content = self.server.connection.RetrieveContent()
        creds = vim.vm.guest.NamePasswordAuthentication(username=self.vmUsername, 
                                                            password=self.vmPassword)
        """
        UNDER HEAVY LOAD, VMTools CAN GET IN AN ODD STATE AND FLAKE OUT WHEN YOU TRY TO
        GET THE PROCLIST.  WHEN IT GETS LIKE THAT, IT THROWS the EXCEPTION 
        vim.fault.InvalidState. IF THAT HAPPENS, TRYING AGAIN ALMOST ALWAYS WORKS.  
        THAT'S WHY THE CALL SITS IN A LOOP LIKE THIS....
        """
        for i in range(5):
            try:
                processList = content.guestOperationsManager.processManager.ListProcessesInGuest(vm=self.vmObject,
                                                                                             auth=creds)
            except vim.fault.InvalidState as e:
                self.server.logMsg("[WARNING]: VM IN A STRANGE STATE; RETRYING PROCLIST UPDATE")
                self.server.logMsg("SYSTEM ERROR:\n" + str(e))
                retVal = False
                time.sleep(1)
                pass
            except Exception as f:
                self.server.logMsg("[ERROR]: UNKNOWN ERROR (SORRY!)")
                self.server.logMsg("SYSTEM ERROR:\n" + str(f))
                retVal = False
                break
            else:
                self.procList[:]=[]
                for runningProc in processList:
                    self.procList.append(str(runningProc.pid) + "\t\t" + \
                                         runningProc.name + "\t\t" + \
                                         runningProc.cmdLine + "\t\t" + \
                                         runningProc.owner)
                retVal = True
        return retVal

    def uploadAndRun(self, srcFile, dstFile, remoteInterpreter = None):
        """
        THIS JUST COMBIENS THE UPLOAD AND EXECUTE FUNCTIONS, BUT IF THE VM IS 'NIX, IT ALSO
        CHMODS THE FILE SO WE CAN EXECUTE IT
        """
        self.server.logMsg("SOURCE FILE = " + srcFile + "; DESTINATION FILE = " + dstFile)
        if remoteInterpreter!= None:
            remoteCmd = [remoteInterpreter, dstFile]
        else:
            remoteCmd = [dstFile]
        if not self.uploadFileToGuest(srcFile, dstFile):
            self.server.logMsg("[FATAL ERROR]: FAILED TO UPLOAD " + srcFile + " TO " + self.devVm)
            return False
        chmodCmdList = "/bin/chmod 755".split() + [dstFile]
        if not self.runCmdOnGuest(chmodCmdList):
            self.server.logMsg("[FATAL ERROR]: FAILED TO RUN " + ' '.join(chmodCmdList) + " ON " + self.devVm)
            return False
        if not self.runCmdOnGuest(remoteCmd):
            self.server.logMsg("[FATAL ERROR]: FAILED TO RUN '" + ' '.join(remoteCmd) + "' ON " + self.devVm)
            return False
        return True
        
    def uploadFileToGuest(self, srcFile, dstFile):
        """
        uploadFileToGuest UPLOADS A FILE TO A VM
        """
        self.server.logMsg("ATTEMPTING TO UPLOAD " +srcFile + " TO " + dstFile + " ON " + self.vmName)
        self.server.logMsg("USING " + self.vmUsername + " PW " + self.vmPassword + " ON " + self.vmName)
        retVal = False
        if self.checkTools():
            creds = vim.vm.guest.NamePasswordAuthentication(username=self.vmUsername, 
                                                            password=self.vmPassword)
            content = self.server.connection.RetrieveContent()
            try:
                srcFileObj = open(srcFile, 'rb')
                fileContent = srcFileObj.read()
                srcFileObj.close()
            except IOError:
                self.server.logMsg("FAILED TO OPEN FILE " + srcFile)
                return retVal
            try:
                file_attribute = vim.vm.guest.FileManager.FileAttributes()
                vmFileManager = content.guestOperationsManager.fileManager
                incompleteUrl = vmFileManager.InitiateFileTransferToGuest(self.vmObject, 
                                                                creds, 
                                                                dstFile,
                                                                file_attribute,
                                                                len(fileContent), 
                                                                True)
                self.server.logMsg(incompleteUrl)
                #THIS IS STUPID, BUT THERE IS SOME ASSEMBLY REQUIRED
                splitUrl = incompleteUrl.split('*')
                realUrl = splitUrl[0] + self.server.hostname + splitUrl[1]
                self.server.logMsg(realUrl)
                resp = requests.put(realUrl, data=fileContent, verify=False)
                if not resp.status_code == 200:
                    self.server.logMsg("ERROR UPLOADING FILE TO " + self.vmName + " HTTP CODE " + str(resp.status_code))
                    retVal = True
                else:
                    self.server.logMsg("UPLOADED FILE TO " + self.vmName + " HTTP CODE " + str(resp.status_code))
                    retVal=True
            except IOError as e:
                self.server.logMsg("FILE NOT FOUND: " + srcFile)
                self.server.logMsg("SYSTEM ERROR: " + str(e))
            except vim.fault.InvalidGuestLogin as f:
                self.server.logMsg("INCORRECT USERTNAME/PASSWORD PROVIDED FOR " + self.vmName)
                self.server.logMsg("USERNAME: " + self.vmUsername + " PASSWORD: " + self.vmPassword)
                self.server.logMsg("SYSTEM ERROR: " + str(f))
        else:
            self.server.logMsg("THERE IS A PROBLEM WITH THE VMWARE TOOLS ON " + self.vmName)
        return retVal
    
    def waitForTask(self, task):
        """
        YES, THIS IS A DISASTER... 
        EVEN IN VIM, NESTED LOOPS ARE REQUIRED AS TASKS CAN BE CHILDREN OF TASKS, JUST LIKE
        SNAPSHOTS
        """
        pc = self.server.connection.content.propertyCollector
        objSpec = vmodl.query.PropertyCollector.ObjectSpec(obj=task)
        propSpec = vmodl.query.PropertyCollector.PropertySpec(type=vim.Task,
                                                             pathSet=[], all=True)
        filterSpec = vmodl.query.PropertyCollector.FilterSpec()
        filterSpec.objectSet = [objSpec]
        filterSpec.propSet = [propSpec]
        filter = pc.CreateFilter(filterSpec, True)
        for i in range(20):
            update = pc.WaitForUpdates(None)
            for filterSet in update.filterSet:
                for filterObject in filterSet.objectSet:
                    if filterObject.obj == task:
                        for change in filterObject.changeSet:
                            taskStatus = "UNKNOWN"
                            if change.name == 'info':
                                taskStatus = change.val.state
                            elif change.name == 'info.state':
                                taskStatus = change.val
                            else:
                                continue
                            if taskStatus == 'success':
                                self.server.logMsg("DONE")
                                return True
            time.sleep(5)
        self.server.logMsg("TASK NOT COMPLETED IN ALLOTTED TIME")
        return False
        
