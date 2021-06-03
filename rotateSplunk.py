#!/bin/python
from paramiko import SSHClient
import argparse
import getpass
import os,subprocess
import configparser
from pathlib import Path
import time

class Password:
  DEFAULT = 'Prompt if not secify'
  def __init__(self, value):
    if value == self.DEFAULT:
      value = getpass.getpass('ssh Password: ')
    self.value = value
  def __str__(self):
    return self.value

class splunkConfig:
  localConfigFile = "/home/pi/indexes.conf"
  #localConfigFile = "/data/splunk/etc/system/local/indexes.conf"
  rotatePeriodInSecs = 60
  coldToFrozenScript = "$SPLUNK_HOME/bin/coldToFrozenExample.py"
  coldToFrozenDir = "/tmp/heartwise/"
  #coldToFrozenDir = "/tmp/splunk-old-index-archives-data/"
  frozenTimePeriodInSecs = 94608000
  maxTotalDataSizeMB = 250000

  def __init__(self, rotatePeriodInSecs, coldToFrozenScript,\
               coldToFrozenDir, frozenTimePeriodInSecs, maxTotalDataSizeMB):
    self.localConfigFile = localConfigFile
    self.rotationPeriodInSecs = rotatePeriodInSecs
    self.coldToFrozenScript = coldToFrozenScript
    self.frozenTimePeriodInSecs = frozenTimePeriodInSecs
    self.maxTotalDataSizeMB = maxTotalDataSizeMB

parser = argparse.ArgumentParser()
parser.add_argument('-u', '--username', type=str, help='ssh username', required=True)
#parser.add_argument('-p', '--password', type=Password, help='ssh password', default=Password.DEFAULT)
parser.add_argument('-i', '--splunkIp', help='IP or hostname', required=True)
args = parser.parse_args()

def authenticate():
  import paramiko
  key = paramiko.RSAKey.from_private_key_file(os.path.expanduser('~/.ssh/id_rsa'))
  client = paramiko.SSHClient()
#  client.load_host_keys(os.path.expanduser('~/.ssh/known_hosts'))
  client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
  display(f'\t[ initial ssh connection ]')
  client.connect(args.splunkIp, username=args.username, pkey=key) 
#  client.connect(args.splunkIp, username=args.username, password=str(args.password))
  display(f'\t[ splunk instance connected ]')
  return client

def display(msg):
  time.sleep(1)
  print(msg)

def addToRemoteConfig():
  config = configparser.ConfigParser()
  config['main'] = {}
  config['main']['coldToFrozenScript'] = splunkConfig.coldToFrozenScript
  config['main']['coldToFrozenDir'] = splunkConfig.coldToFrozenDir
  config['main']['frozenTimePeriodInSecs'] = str(splunkConfig.frozenTimePeriodInSecs)
  config['main']['maxTotalDataSizeMB'] = str(splunkConfig.maxTotalDataSizeMB)
  config['main']['rotatePeriodInSecs'] = str(splunkConfig.rotatePeriodInSecs)
  with open('./local.indexes.conf','w') as configfile:
    config.write(configfile)
  configfile.close()
  display("\t[ local.indexes.conf created ]")

def pullRemoteConfig():
  display(f'\t[ Pulling Splunk Rotate Configuration ]')
  #print(f'\t[ Pulling Splunk Rotate Configuration ]')
  import subprocess
  try:
    stdout = subprocess.check_output(['scp',\
         args.username+"@"+args.splunkIp+":"+splunkConfig.localConfigFile,'./'])
    
    if stdout.decode("utf8") == '':
      display("\t[ Remote config pulled ]")
      return
  except subprocess.CalledProcessError as e:
    display("\t[ No Remote config Found, adding Config ]")
    return False
    #pass
    
def checkRemoteConfig():
  config = configparser.ConfigParser()
  config.sections()
  display("\tLoad {}".format(splunkConfig.localConfigFile))
  config.read('indexes.conf')  
  for setting in config['main']:
    display(setting+" = "+config['main'][setting])
  if config['main']['coldtofrozenscript'] == splunkConfig.coldToFrozenScript:
    display('\t[ cold To Frozen Script OK ]')
  else:
    display('\t[ Error cold To Frozen Script ]')
    return False
  if config['main']['coldtofrozendir'] == splunkConfig.coldToFrozenDir:
    display('\t[ cold To Frozen Dir OK ]')
  else:
    display('\t[ Error cold To Frozen Dir ]')
    return False
  if config['main']['frozentimeperiodinsecs'] == str(splunkConfig.frozenTimePeriodInSecs):
    display('\t[ frozen time period in secs OK ]')
  else:
    display('\t[ Error frozen time period in secs ]')
    return False
  if config['main']['maxtotaldatasizemb'] == str(splunkConfig.maxTotalDataSizeMB):
    display('\t[ max Total Data Size Mb OK ]')
  else:
    display('\t[ Error max Total Data Size Mb ]')
    return False
  if config['main']['rotateperiodinsecs'] == str(splunkConfig.rotatePeriodInSecs):
    display('\t[ rotate period in secs OK ]')
  else:
    display('\t[ Error rotate period in secs]')
    return False

def uploadConfig():
  display(f'\t[ Upload Splunk Rotate Configuration ]')
  try:
    stdout = subprocess.check_output(['scp','local.indexes.conf'\
          ,args.username+"@"+args.splunkIp+":"+splunkConfig.localConfigFile])
    if stdout.decode("utf8") == '':
      display("\t[ Config Uploaded Successfully ]")
    #else:
  except subprocess.CalledProcessError as e:
    display(e.output)
    
def removeOldSplunkLogs():
  client = authenticate()
  stdin, stdout, stderr = client.exec_command('sudo du -sh "{}"*'\
              .format(splunkConfig.coldToFrozenDir), get_pty=True)
  display('rm -rf:\n{}'.format(stdout.read().decode("utf8")))
  display('stderr :\n{}'.format(stderr.read().decode("utf8")))
  stdin, stdout, stderr = client.exec_command('sudo du -sh "{}"'\
              .format(splunkConfig.coldToFrozenDir), get_pty=True)
  size = stdout.read().decode("utf8").split("\t",1)[0]
  decision = input("Are you sure to Remove Logs in {}?\n {} space will be freed\n This CANNOT be Undone\
            yes/no? (default: no), ans:".format(splunkConfig.coldToFrozenDir,size))
  if decision.lower() != 'yes':
    display('\t [ No Logs Removed ]')
    return
  stdin, stdout, stderr = client.exec_command('sudo rm -rf "{}"*'\
                   .format(splunkConfig.coldToFrozenDir), get_pty=True)
  if stdout.read().decode("utf8") == '':
    display('\t [ {} Frozen Splunk Logs Removed ]'.format(size))
  
def main():
  if pullRemoteConfig() == False:
    addToRemoteConfig()
    uploadConfig()
    
  elif checkRemoteConfig() == False:
    display("\t[ Config Error ]")
    addToRemoteConfig()
    uploadConfig()
  display("\t[ All Config OK, Clean Up spaces ]")
  removeOldSplunkLogs()

if __name__ == "__main__":
  main()
