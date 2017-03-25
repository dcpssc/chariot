# from fabric.api import run, env, put, sudo, local, hosts
# source https://phab-riaps.isis.vanderbilt.edu/source/riaps-pycom/browse/ISORC/fab_src/
from fabric.api import *
import time
import socket
import re
from fabric.contrib.files import exists
from fabric.decorators import parallel
env.hosts = ['bbb-eb18.local']

env.password = 'riapspwd'
env.user = 'riaps'
env.sudo_password = 'riapspwd'

mongoServer = '192.168.0.108'
managementEngine = '192.168.0.108'
monitoringServer = 'bbb-1f82'
re_MongoServer = re.compile('MongoServer: localhost')
re_MonitoringServer = re.compile('MonitoringServer: localhost')
re_ManagementEngine = re.compile('ManagementEngine: localhost')
re_NodeName = re.compile('NodeName: default_name')
re_NodeTemplate = re.compile('NodeTemplate: default_template')

env.roledefs = {
  'four' : ['bbb-1f82.local', 'bbb-53b9.local', 'bbb-d5b5.local', 'bbb-ff98.local'],
  'three' : ['bbb-1f82.local', 'bbb-53b9.local', 'bbb-d5b5.local'],
  'two' : ['bbb-1f82.local', 'bbb-53b9.local'],
  'one' : ['bbb-1f82.local'],
  'mana' : [managementEngine],
  'monti': [monitoringServer+'.local'],
  'compute' : ['bbb-53b9.local', 'bbb-d5b5.local', 'bbb-ff98.local'],
  'egress' : ['bbb-ff98.local'], }
role = 'one'

def find_nodes():
  local("sudo arp-scan --interface=enp0s8 --localnet")
  local("sudo arp-scan --interface=enp0s3 --localnet")
  
@roles('four')
@parallel
def setupNodes():
    """ installs pip2, and  copies and installs version of chariot from local ~/chariot"""
    sudo("apt install python-pip -y")
    if not exists('~/chariot'):
        run('mkdir chariot')
    put('~/chariot', '~/')
    # Install edge CHARIOT runtime
    sudo("cd ~/chariot/Runtime && sudo pip2 install --upgrade .")
    # among other things the above installs chariot-dm, chariot-nm, and chariot-nmw at /etc/init.d, they need to be made executable
    #sudo("chmod +x /etc/init.d/chariot*")
    #This makes chariot-nm start on boot
    #run("cd /etc/init.d && sudo update-rc.d chariot-nm defaults 99")
    #sudo("systemctl enable chariot-nm.service")
    #sudo("systemctl start chariot-nm.service")
    #check to make sure it was actually set up and started. 
    #run("systemctl status chariot-nm.service")
    #run("service chariot-nm status")
    #sudo("reboot")
    

@roles('four')
def updateChariot():
  if not exists('~/chariot'):
    run('mkdir chariot')
  put('~/chariot', '~/')

@roles('mana')
def setupManagementEngine():
    # update /etc/hosts
    if exists('/etc/hosts_bak'):
        sudo('mv /etc/hosts_bak /etc/hosts')
    sudo('cp /etc/hosts /etc/hosts_bak')  # in case I screw up
    sudo('echo "' + mongoServer + ' MongoServer" >> /etc/hosts')
    local('sudo -H pip2 install chariot-runtime')

@roles('monti')
def setupMonitor():
  """host a ZooKeeper server and a CHARIOT Node Membership Watcher"""
  # Update /etc/hosts with mongo-server and management-engine nodes
  if exists('/etc/hosts_bak'):
        sudo('mv /etc/hosts_bak /etc/hosts')
  sudo('cp /etc/hosts /etc/hosts_bak')  # in case I screw up
  sudo('echo "' + mongoServer + ' MongoServer" >> /etc/hosts')
  sudo('echo "' + managementEngine + ' ManagementEngine" >> /etc/hosts')
  # Install ZooKeeper
  sudo('apt update')
  sudo("apt install zookeeper -y")
  sudo("apt install zookeeperd -y")
  # Install edge CHARIOT runtime
  #sudo("cd ~/chariot/Runtime && sudo pip2 install --upgrade .")
  # update configuration file located in /etc/chariot/chariot.conf
  updateChariotConf()  
  # Use update-rc.d to launch Node Membership Watcher at boot
  #run ("cd /etc/init.d && sudo update-rc.d chariot-nmw defaults 99")
  sudo("systemctl enable chariot-nmw")
  # Restart the node, zookeep and node membership watcher will start. 

@roles('compute')
@parallel
def setupCompute():
  """Setup CHARIOT compute nodes"""
  # Update /etc/hosts with mongo-server and monitoring-server
  if exists('/etc/hosts_bak'):
        sudo('mv /etc/hosts_bak /etc/hosts')
  sudo('cp /etc/hosts /etc/hosts_bak')  # in case I screw up
  sudo('echo "' + mongoServer + ' MongoServer" >> /etc/hosts')
  sudo('echo "' + monitoringServer + ' MonitoringServer" >> /etc/hosts')
  # Install edge CHARIOT runtime
  #sudo("cd ~/chariot/Runtime && sudo pip2 install .")
  # sudo("cd ~/chariot/Runtime && sudo pip2 install --upgrade .")
  # update configuration file located in /etc/chariot/chariot.conf
  updateChariotConf()  
  sudo("systemctl enable chariot-nm")
  sudo("systemctl disable chariot-dm")
  
  #run("cd /etc/init.d && sudo update-rc.d chariot-nm defaults 99")
  #run("cd /etc/init.d && sudo update-rc.d chariot-dm defaults 99")
  print("\n after reboot check the MongoDB server for the presence of ConfigSpace database and Nodes collection. This collection should have a document each for every compute node.")
  #sudo("reboot")
  
def setupAlias():
    
    sudo('cp /etc/hosts /etc/hosts_bak')  # in case I screw up
    sudo('echo "' + mongoServer + ' MongoServer" >> /etc/hosts')
    sudo('echo "' + monitoringServer + ' MonitoringServer" >> /etc/hosts')

@roles('mana')
def initMana():
  """run the management engine for initial deployment"""
  run("chariot-me -i")

@roles('compute')
def checkLogs():
  """Check deployment manager logs on compute nodes to verify that deployement actions were taken"""
  run("cat /etc/chariot/logs")  # not sure if this is cat-able

@roles('mana')
def testFailure():
  """test node egress (node failure)"""
  run("chariot-me")  # Start management-engine without initial deplflag
  egress()

@roles('egress')
def egress():
  """poweroff egress nodes"""
  print("sudo poweroff")
  # sudo("reboot")#I think i prefer reboot because then it does both egress and ingress. 
  
@roles('monti')
def updateChariotConf():    
    if exists('/etc/chariot/chariot.conf_bak'):
        sudo('mv etc/chariot/chariot.conf_bak etc/chariot/chariot.conf')
    sudo('cp /etc/chariot/chariot.conf /etc/chariot/chariot.conf.bak')
    sudo("sed -i 's/MongoServer: localhost/MongoServer: " + mongoServer + "/g' /etc/chariot/chariot.conf")
    sudo("sed -i 's/MonitoringServer: localhost/MonitoringServer: " + monitoringServer + "/g' /etc/chariot/chariot.conf")
    sudo("sed -i 's/ManagementEngine: localhost/ManagementEngine: " + managementEngine + "/g' /etc/chariot/chariot.conf")
    hostName = run("hostname")
    sudo("sed -i 's/default_name/" + hostName + "/g' /etc/chariot/chariot.conf")
    
    #sed -i 's/original/new/g' file.txt
          
      # update configuration file located in /etc/chariot/chariot.conf
#     [Base]
#     NodeName: default_name
#     NodeTemplate: default_template
#     Interface: eth0
#     Network: chariot
#     
#     [Services]
#     MongoServer: localhost
#     MonitoringServer: localhost
#     ManagementEngine: localhost
    
