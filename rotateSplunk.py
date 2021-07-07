#!/bin/python3
from paramiko import SSHClient
import argparse
import getpass
import os,subprocess
import configparser
from pathlib import Path
import time
import re

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
  thawedPath = "/tmp/splunk-old-index-archives-data/"
  #coldToFrozenDir = "/tmp/splunk-old-index-archives-data/"
  coldToFrozenScript = "$SPLUNK_HOME/bin/coldToFrozenExample.py"
  coldToFrozenDir = "/tmp/heartwise/"
  frozenTimePeriodInSecs = 31449600
  maxTotalDataSizeMB = 200000
  rotatePeriodInSecs = 60

  def __init__(self, rotatePeriodInSecs, coldToFrozenScript,\
               coldToFrozenDir, frozenTimePeriodInSecs, maxTotalDataSizeMB, thawedPath):
    self.localConfigFile = localConfigFile
    self.rotationPeriodInSecs = rotatePeriodInSecs
    self.coldToFrozenScript = coldToFrozenScript
    self.frozenTimePeriodInSecs = frozenTimePeriodInSecs
    self.maxTotalDataSizeMB = maxTotalDataSizeMB
    self.thawedPath = thawedPath

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
  display(f'[ initial ssh connection ]')
  client.connect(args.splunkIp, username=args.username, pkey=key) 
#  client.connect(args.splunkIp, username=args.username, password=str(args.password))
  display(f'[ splunk instance connected ]')
  return client

def display(msg):
  time.sleep(1)
  print('\t'+msg)

def addToRemoteConfig():
  config = configparser.ConfigParser()
  config['main'] = {}
  config['main']['coldToFrozenScript'] = splunkConfig.coldToFrozenScript
  config['main']['coldToFrozenDir'] = splunkConfig.coldToFrozenDir
  config['main']['thawedPath'] = splunkConfig.thawedPath
  config['main']['frozenTimePeriodInSecs'] = str(splunkConfig.frozenTimePeriodInSecs)
  config['main']['maxTotalDataSizeMB'] = str(splunkConfig.maxTotalDataSizeMB)
  config['main']['rotatePeriodInSecs'] = str(splunkConfig.rotatePeriodInSecs)
  with open('./local.indexes.conf','w') as configfile:
    config.write(configfile)
  configfile.close()
  display("[ local.indexes.conf created ]")

def pullRemoteConfig():
  display(f'[ Pulling Splunk Rotate Configuration ]')
  #print(f'[ Pulling Splunk Rotate Configuration ]')
  import subprocess
  try:
    stdout = subprocess.check_output(['scp',\
         args.username+"@"+args.splunkIp+":"+splunkConfig.localConfigFile,'./'])
    
    if stdout.decode("utf8") == '':
      display("[ Remote config pulled ]")
      return
  except subprocess.CalledProcessError as e:
    display("[ No Remote config Found, adding Config ]")
    return False
    #pass
    
def checkRemoteConfig():
  config = configparser.ConfigParser()
  config.sections()
  display("Load {}".format(splunkConfig.localConfigFile))
  config.read('indexes.conf')  
  configNumbers=[]
  for setting in config['main']:
    display(setting+" = "+config['main'][setting])
  for key in splunkConfig.__dict__.keys():
    key = re.sub(r"(^\_.*)","",key)
    configNumbers.append(key)
  #print(len(' '.join(configNumbers).split())-1)
  display('[ Remote_Config Count: {} ]'.format(len(config['main'])))
  display('[ default Config Conunt: {} ]'.format(len(' '.join(configNumbers).split())-1))
  if len(config['main']) == len(' '.join(configNumbers).split())-1:
    display('[ Config matched and number OK]')
  else:
    return False
  if config['main']['coldtofrozenscript'] == splunkConfig.coldToFrozenScript:
    display('[ cold To Frozen Script OK ]')
  else:
    display('[ Error cold To Frozen Script ]')
    return False
  if config['main']['coldtofrozendir'] == splunkConfig.coldToFrozenDir:
    display('[ cold To Frozen Dir OK ]')
  else:
    display('[ Error cold To Frozen Dir ]')
    return False
  if config['main']['frozentimeperiodinsecs'] == str(splunkConfig.frozenTimePeriodInSecs):
    display('[ frozen time period in secs OK ]')
  else:
    display('[ Error frozen time period in secs ]')
    return False
  if config['main']['maxtotaldatasizemb'] == str(splunkConfig.maxTotalDataSizeMB):
    display('[ max Total Data Size Mb OK ]')
  else:
    display('[ Error max Total Data Size Mb ]')
    return False
  if config['main']['rotateperiodinsecs'] == str(splunkConfig.rotatePeriodInSecs):
    display('[ rotate period in secs OK ]')
  else:
    display('[ Error rotate period in secs]')
    return False
  if config['main']['thawedPath'] == splunkConfig.thawedPath:
    display('[ thawedPath OK ]')
  else:
    display('[ Error thawedPath ]')
    return False

def uploadConfig():
  display(f'[ Upload Splunk Rotate Configuration ]')
  try:
    stdout = subprocess.check_output(['scp','local.indexes.conf'\
          ,args.username+"@"+args.splunkIp+":"+splunkConfig.localConfigFile])
    if stdout.decode("utf8") == '':
      display("[ Config Uploaded Successfully ]")
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
    display(' [ No Logs Removed ]')
    return
  stdin, stdout, stderr = client.exec_command('sudo rm -rf "{}"*'\
                   .format(splunkConfig.coldToFrozenDir), get_pty=True)
  if stdout.read().decode("utf8") == '':
    display(' [ {} Frozen Splunk Logs Removed ]'.format(size))
  
def main():
  if pullRemoteConfig() == False:
    addToRemoteConfig()
    uploadConfig()
    
  elif checkRemoteConfig() == False:
    display("[ Config Error ]")
    addToRemoteConfig()
    uploadConfig()
  display("[ All Config OK, Clean Up spaces ]")
  removeOldSplunkLogs()

if __name__ == "__main__":
  main()
