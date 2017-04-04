# vm-automation
## Introduction
The vm-automation repo was created to simplify interactions with virtual
machines.  Specifically, this was built to support automated testing by 
simplifying interaction with VMs.  Currently, it supports VMWare 
Workstation through the vmrun.exe command-line application and ESXi 
through encapsulation of pyvmomi functions.  My testing has used python 
2.7.

### Why bother to encapsulate pyvmomi and vmrun.exe?
I'm no big fan of re-inventing the wheel, but I did so here for two 
reasons:
(1) Using this library allows me to seamlessly manage VMware workstation 
VMs and VMWare ESXi VMs because each server type has a class, and I 
overloaded the management functions to work with both classes.
(2) Pyvmomi is not particularly simple.  If you do not believe me, see 
the `uploadFileToGuest` function.  It contains the pyvmomi calls to
upload a file to a guest OS.  It's about 40 lines.  Even worse is the
code to get a list of VM snapshots, which requires a recurive search.
Vm-automation encapsulates the pyvmomi code and adds error handling as
well.

### Can I use it as a stand-alone solution?
Certainly.  I created the library as a separate entity specifically
because I planned to reuse this library to support other projects.  
Right now, it has all the functions that I need to run automated payload
testing, but I'm all for adding on to support more projects.

### How do I use it?
(1) If you don't have python, crawl out from under the rock and install
it.
(2) Install [pyvmomi](https://pypi.python.org/pypi/pyvmomi) on your machine:
`pip install --upgrade pyvmomi`
(3) Git this repo:
`git clone git@github.com:rapid7/vm-automation.git`

### How can I get started?
The fastest way to get started is to instantiate a server (it can be 
either VMWare ESXi or Workstation).

```
tmoose@ubuntu:~/rapid7/vm-automation$ python
>>> import esxiVm
>>> myserver = esxiServer("xxx.xxx.xxx.xxx", "user", "password", "443", "example.log")
>>> print myserver.connect()
True
```
OK, yeah; I probably should not have made the port number a string....
Anyway, That just got us a connection to the server.
Let's query the Type of Server:
```
>>> print myserver.getVersion()
VMware ESXi 6.5.0 build-4564106
```
By default, nothing happens other than establishing the session.
If we wanted to get a list ov VMs on the server, we need to populate
that list, first:
```
>>> myserver.enumerateVms()
```
Now, we can print it:
```
>>> for vm in myserver.vmList:
...     print vm.vmName
... 
[APT] Windows XP Pro
[APT] Windows 7 x64
[APT] Ubuntu 16x64
[APT] Generic Dev Ubuntu
[APT] Windows 8 x64
[APT] Windows 10x64 Pro
```
These VMs are of a custom vmObject type defined in the esxiVm.py file
As they are a class, you just get an object which is kind of a pain to 
reference.  It might be easier to create a dictionary with the names and
objects as pairs:
```
>>> vmDic = {}
>>> for vm in myserver.vmList:
...     vmDic[vm.vmName] = vm
... 
```
Now, we can play with a given vm more easily:
```
>>> print vmDic['[APT] Windows 10x64 Pro'].isPoweredOn()
False
>>> print vmDic['[APT] Windows 10x64 Pro'].powerOn()
serverlog:[2017-04-04 15:32:30.638260] POWERING ON [APT] Windows 10x64 Pro
serverlog:[2017-04-04 15:32:35.667396] DONE
True
>>> print vmDic['[APT] Windows 10x64 Pro'].isPoweredOn()
True
>>> print vmDic['[APT] Windows 10x64 Pro'].powerOff()
serverlog:[2017-04-04 15:32:50.859867] POWERING OFF [APT] Windows 10x64 Pro
serverlog:[2017-04-04 15:32:55.887729] DONE
True
>>> 
```
More advanced features require you to authenticate with the VM itself:
```
>>> vmDic['[APT] Windows 10x64 Pro'].setUsername('username')
>>> vmDic['[APT] Windows 10x64 Pro'].setPassword('password')
```
I suggest you use the function `waitForVmsToBoot` before calling any
interactive VM functions.  VMware tools gets in odd states during the 
boot process, and that function will wait for VMWare tools to stabilize
and be ready to handle requests:
```
>>> myserver.waitForVmsToBoot([vmDic['[APT] Windows 10x64 Pro']])
serverlog:[2017-04-04 16:02:31.691551] WAITING FOR VMS TO BE READY; THIS COULD TAKE A FEW MINUTES
serverlog:[2017-04-04 16:04:40.216568] VMS APPEAR TO BE READY; PULLING IP ADDRESSES TO VERIFY
serverlog:[2017-04-04 16:04:45.237939] IP ADDRESS FOR [APT] Windows 10x64 Pro = xxx.xxx.xxx.xxx
True
```
Let's grab a process list:
```
>>> vmDic['[APT] Windows 10x64 Pro'].updateProcList()
>>> vmDic['[APT] Windows 10x64 Pro'].updateProcList()
True
>>> for proc in vmDic['[APT] Windows 10x64 Pro'].procList:
...     print proc
... 
0		[System Process]		[System Process]		
4		System		System		NT AUTHORITY\SYSTEM
264		smss.exe		smss.exe		NT AUTHORITY\SYSTEM
356		csrss.exe		csrss.exe		NT AUTHORITY\SYSTEM
424		wininit.exe		wininit.exe		NT AUTHORITY\SYSTEM
432		csrss.exe		csrss.exe		NT AUTHORITY\SYSTEM
500		winlogon.exe		winlogon.exe		NT AUTHORITY\SYSTEM
552		services.exe		services.exe		NT AUTHORITY\SYSTEM
560		lsass.exe		lsass.exe		NT AUTHORITY\SYSTEM
644		svchost.exe		svchost.exe		NT AUTHORITY\SYSTEM
708		svchost.exe		svchost.exe		NT AUTHORITY\NETWORK SERVICE
808		LogonUI.exe		LogonUI.exe		NT AUTHORITY\SYSTEM
816		dwm.exe		dwm.exe		Window Manager\DWM-1
840		svchost.exe		svchost.exe		NT AUTHORITY\SYSTEM
956		svchost.exe		svchost.exe		NT AUTHORITY\SYSTEM
972		svchost.exe		svchost.exe		NT AUTHORITY\LOCAL SERVICE
984		svchost.exe		svchost.exe		NT AUTHORITY\LOCAL SERVICE
620		svchost.exe		svchost.exe		NT AUTHORITY\LOCAL SERVICE
1080		svchost.exe		svchost.exe		NT AUTHORITY\NETWORK SERVICE
1196		svchost.exe		svchost.exe		NT AUTHORITY\LOCAL SERVICE
1276		svchost.exe		svchost.exe		NT AUTHORITY\LOCAL SERVICE
1372		spoolsv.exe		spoolsv.exe		NT AUTHORITY\SYSTEM
1456		svchost.exe		svchost.exe		NT AUTHORITY\SYSTEM
1648		svchost.exe		svchost.exe		NT AUTHORITY\NETWORK SERVICE
1744		svchost.exe		svchost.exe		NT AUTHORITY\SYSTEM
1812		VGAuthService.exe		VGAuthService.exe		NT AUTHORITY\SYSTEM
1840		svchost.exe		svchost.exe		NT AUTHORITY\SYSTEM
1848		vmtoolsd.exe		vmtoolsd.exe		NT AUTHORITY\SYSTEM
1872		MsMpEng.exe		MsMpEng.exe		NT AUTHORITY\SYSTEM
2028		Memory Compression		Memory Compression		NT AUTHORITY\SYSTEM
2292		WmiPrvSE.exe		WmiPrvSE.exe		NT AUTHORITY\NETWORK SERVICE
2356		dllhost.exe		dllhost.exe		NT AUTHORITY\SYSTEM
2452		dllhost.exe		dllhost.exe		NT AUTHORITY\SYSTEM
2592		msdtc.exe		msdtc.exe		NT AUTHORITY\NETWORK SERVICE
2760		VSSVC.exe		VSSVC.exe		NT AUTHORITY\SYSTEM
3024		WmiPrvSE.exe		WmiPrvSE.exe		NT AUTHORITY\SYSTEM
2424		sppsvc.exe		sppsvc.exe		NT AUTHORITY\NETWORK SERVICE
```
There are also a couple of functions that support querying, resetting,
creating, and deleting snapshots:
```
>>> vmDic['[APT] Windows 10x64 Pro'].getSnapshots()
serverlog:[2017-04-04 16:06:16.775557] FINDING SNAPSHOTS FOR [APT] Windows 10x64 Pro
>>> for snapshot in vmDic['[APT] Windows 10x64 Pro'].snapshotList:
...     print snapshot
... 
((vim.vm.SnapshotTree) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   snapshot = 'vim.vm.Snapshot:9-snapshot-3',
   vm = 'vim.VirtualMachine:9',
   name = 'TURNED_OFF',
   description = '',
   id = 3,
   createTime = 2017-02-26T22:08:42.981401Z,
   state = 'poweredOff',
   quiesced = false,
   backupManifest = <unset>,
   childSnapshotList = (vim.vm.SnapshotTree) [
      (vim.vm.SnapshotTree) {
         dynamicType = <unset>,
         dynamicProperty = (vmodl.DynamicProperty) [],
         snapshot = 'vim.vm.Snapshot:9-snapshot-6',
         vm = 'vim.VirtualMachine:9',
         name = 'TESTING_BASE',
         description = '',
         id = 6,
         createTime = 2017-03-17T15:11:29.883673Z,
         state = 'poweredOn',
         quiesced = false,
         backupManifest = <unset>,
         childSnapshotList = (vim.vm.SnapshotTree) [],
         replaySupported = false
      }
   ],
   replaySupported = false
}, 'TURNED_OFF')
((vim.vm.SnapshotTree) {
   dynamicType = <unset>,
   dynamicProperty = (vmodl.DynamicProperty) [],
   snapshot = 'vim.vm.Snapshot:9-snapshot-6',
   vm = 'vim.VirtualMachine:9',
   name = 'TESTING_BASE',
   description = '',
   id = 6,
   createTime = 2017-03-17T15:11:29.883673Z,
   state = 'poweredOn',
   quiesced = false,
   backupManifest = <unset>,
   childSnapshotList = (vim.vm.SnapshotTree) [],
   replaySupported = false
}, 'TURNED_OFF/TESTING_BASE')
```
Well, that did not help because snapshots are pyvmomi objects.... let's
get something useful and list them by name:
```
>>> for snapshot in vmDic['[APT] Windows 10x64 Pro'].snapshotList:
...     print snapshot[0].name
... 
TURNED_OFF
TESTING_BASE
```
OK, well, most of the snapshot work abstracts the pyvmomi class.
Let's look at creating a snapshot.  (Turning off the VM first makes it 
faster).  There are lots of optional parameters for these functions,
but I assumed most common use-cases.
```
>>> vmDic['[APT] Windows 10x64 Pro'].powerOff()
serverlog:[2017-04-04 16:16:13.734495] POWERING OFF [APT] Windows 10x64 Pro
serverlog:[2017-04-04 16:16:18.773459] DONE
True
>>> vmDic['[APT] Windows 10x64 Pro'].takeSnapshot('new_snapshot')
serverlog:[2017-04-04 16:17:02.679320] TAKING SNAPSHOT new_snapshot ON [APT] Windows 10x64 Pro
>>> vmDic['[APT] Windows 10x64 Pro'].getSnapshots()
serverlog:[2017-04-04 16:18:04.798396] FINDING SNAPSHOTS FOR [APT] Windows 10x64 Pro
>>> for snapshot in vmDic['[APT] Windows 10x64 Pro'].snapshotList:
...     print snapshot[0].name
... 
TURNED_OFF
TESTING_BASE
new_snapshot
```
Great; we created a snapshot, but now let's delete it:
```
>>> vmDic['[APT] Windows 10x64 Pro'].deleteSnapshot('new_snapshot')
serverlog:[2017-04-04 16:18:35.777414] FINDING SNAPSHOTS FOR [APT] Windows 10x64 Pro
serverlog:[2017-04-04 16:18:35.787257] DELETING SNAPSHOT new_snapshot FROM [APT] Windows 10x64 Pro
serverlog:[2017-04-04 16:18:40.829540] DONE
True
>>> vmDic['[APT] Windows 10x64 Pro'].getSnapshots()
serverlog:[2017-04-04 16:18:50.773661] FINDING SNAPSHOTS FOR [APT] Windows 10x64 Pro
>>> for snapshot in vmDic['[APT] Windows 10x64 Pro'].snapshotList:
...     print snapshot[0].name
... 
TURNED_OFF
TESTING_BASE
>>> 
```



As a first-use, I implemented this library to support payload testing,
so the following methods are supported now:
server class:
`connect`
`enumerateVms`
`getVersion`
`waitForVmsToBoot`

Vm Class:
`checkTools`
`deleteSnapshot`
`enumerateSnapshotsRecursively`
`getArch`
`getFileFromGuest`
`getSnapshots`
`getVmIp`
`getUsername`
`isPoweredOff`
`isPoweredOn`
`makeDirOnGuest`
`powerOn`
`powerOff`
`revertToSnapshot`
`runCmdOnGuest`
`setPassword`
`setUsername`
`setVmIp`
`takeSnapshot`
`updateProcList`
`uploadAndRun`
`uploadFileToGuest`
`waitForTask`

These are less useful in general, but very useful to automated testing.
In time, they may get moved:
`prepVm`
`revertToTestingBase`
`revertDevVm`
`setTestVm`
`takeTempSnapshot`