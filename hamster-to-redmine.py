#! /usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import os
import re
import datetime
import getpass
import sqlite3 as sqlite
from xdg.BaseDirectory import xdg_data_home
from redmine import Redmine
from redmine.exceptions import AuthError
import ConfigParser
from ConfigParser import NoSectionError, NoOptionError

#colors for terminal
class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

def translit(text):
    
    if text is None:
        return 'default'
    
    symbols = (u"абвгдеёжзийклмнопрстуфхцчшщъыьэюяАБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ",
               u"abvgdeejzijklmnoprstufhzcss_y_euaABVGDEEJZIJKLMNOPRSTUFHZCSS_Y_EUA")
    
    tr = {ord(a):ord(b) for a, b in zip(*symbols)}

    return text.translate(tr)  # looks good

#set period
try:
    dayFrom = datetime.datetime.strptime(sys.argv[1], '%d.%m.%Y')
    dayTo = dayFrom + datetime.timedelta(days=1)
except IndexError:
    dayFrom = datetime.date.today()
    dayTo = dayFrom + datetime.timedelta(days=1)
except ValueError:
    print bcolors.FAIL + "Incorrect date argument" + bcolors.ENDC
    quit()
    

#read config
cfg_file_path = 'hamster-to-redmine.cfg'
config = ConfigParser.ConfigParser()
config.read(cfg_file_path)

def getOrCreateValueFromConfig(config, config_file_path, group, name):
    try:
        value = config.get(group, name)
        print group, name, ":", value
    except NoSectionError:
        value = raw_input(group + ' ' + name + ': ')
        config.add_section(group)   
        config.set(group, name, value)
        config_file = open(config_file_path, 'w')
        config.write(config_file)
    except NoOptionError:
        value = raw_input(group + ' ' + name + ': ')
        config.set(group, name, value)
        config_file = open(config_file_path, 'w')
        config.write(config_file)
    return value

def getOrInputPasswordFromConfig(config, config_file_path, group, name):
    try:
        value = config.get(group, name)
    except (NoSectionError, NoOptionError):
        value = getpass.getpass('Password: ')
    return value


redmine_default_url = getOrCreateValueFromConfig(config, cfg_file_path, 'Redmine', 'default_url')
redmine_default_user = getOrCreateValueFromConfig(config, cfg_file_path, 'Redmine', 'default_user')
redmine_default_password = getOrInputPasswordFromConfig(config, cfg_file_path, 'Redmine', 'default_password')
redmine_default_api = Redmine(redmine_default_url, username=redmine_default_user, password=redmine_default_password)

def redmineCheckAuth(redmine_api):
    try:
        redmine_api.auth()
    except AuthError:
        print bcolors.FAIL + 'Incorrect login or password' + bcolors.ENDC;
        quit()

redmineCheckAuth(redmine_default_api)

use_another_redmine = getOrCreateValueFromConfig(config, cfg_file_path, 'Redmine', 'additional')

if(use_another_redmine is 'y'):
    redmine_additional_url = getOrCreateValueFromConfig(config, cfg_file_path, 'Redmine', 'additional_url')
    redmine_additional_user = getOrCreateValueFromConfig(config, cfg_file_path, 'Redmine', 'additional_user')
    redmine_additional_password = getOrInputPasswordFromConfig(config, cfg_file_path, 'Redmine', 'additional_password')
    redmine_additional_api = Redmine(redmine_additional_url, username=redmine_additional_user, password=redmine_additional_password)
    redmineCheckAuth(redmine_additional_api)


print "Getting data from", dayFrom, "to", dayTo, ":"

#get path to hamster sqlite db
database_dir = os.path.realpath(os.path.join(xdg_data_home, "hamster-applet"))
db_path = os.path.join(database_dir, "hamster.db")


con = sqlite.connect(db_path, sqlite.PARSE_DECLTYPES | sqlite.PARSE_COLNAMES)
cur = con.cursor()

#get all tasks from date (query from hamster sources)
query = """SELECT a.id AS id,
                  a.start_time AS start_time,
                  a.end_time AS end_time,
                  a.description as description,
                  b.name AS name, 
                  b.id as activity_id,
                  c.name as category,
                  e.name as tag
            FROM facts a
            LEFT JOIN activities b ON a.activity_id = b.id
            LEFT JOIN categories c ON b.category_id = c.id
            LEFT JOIN fact_tags d ON d.fact_id = a.id
            LEFT JOIN tags e ON e.id = d.tag_id
            WHERE a.start_time > '"""+dayFrom.strftime('%Y-%m-%d')+"""'
                AND a.end_time < '"""+dayTo.strftime('%Y-%m-%d')+"""'
            ORDER BY a.start_time ASC"""
cur.execute(query)

allTasks = cur.fetchall()
cur.close()

#format tasks data
tasks = {}
for (i, task) in enumerate(allTasks):
    start = datetime.datetime.strptime(task[1], '%Y-%m-%d %H:%M:%S')
    end = datetime.datetime.strptime(task[2], '%Y-%m-%d %H:%M:%S')
    hours = (end - start).seconds/3600.0

    if task[3] is None:
        description = ''
    else:
        description = task[3]
    
    tasks[i] = {
        'id': task[0], 
        'start': start, 
        #'end': end, 
        'hours': hours,
        'description': description, 
        'name': task[4], 
        'cat': task[6], 
        'tag': task[7]
    }
    
#parse redmine task_id (first number in activity name)
for task in tasks.values():
    result = re.match(r'^\d+', task['name'])
    if result:
        task_id = result.group(0)
        task['task_id'] = task_id
    else:
        task['task_id'] = ''

#format data to send in redmine: group by date, task_id
redmine_tasks = {}
for task in tasks.values():

    taskDate = task['start'].strftime('%Y-%m-%d')
    try:
        redmine_tasks[taskDate]
    except KeyError:
        redmine_tasks[taskDate] = {}
    
    if task['task_id'] is not '':
        try:
            redmine_tasks[taskDate][task['task_id']]
            redmine_tasks[taskDate][task['task_id']]['hours'] += task['hours']
            if task['description'] is not '':
                redmine_tasks[taskDate][task['task_id']]['description'].append(task['description'])
        except KeyError:
            redmine_tasks[taskDate][task['task_id']] = {}
            redmine_tasks[taskDate][task['task_id']] = task
            
            description = task['description']
            redmine_tasks[taskDate][task['task_id']]['description'] = []

            if description is not '':
                redmine_tasks[taskDate][task['task_id']]['description'].append(description)
    else:
        print bcolors.WARNING +\
            'Not redmine task:', \
            task['hours'], \
            task['name'], \
            "[" + task['tag'] + "]", \
            "(" + task['description'] + ")" +\
            bcolors.ENDC
    
dkeys = redmine_tasks.keys()
dkeys = list(dkeys)
dkeys.sort()
                
for date in dkeys:
    print date, ':'
    dayHours = 0
    for (task_id, task) in redmine_tasks[date].items():          
        task['description'] = set(task['description'])
        task['description'] = list(task['description'])
        task['description'] = ', '.join(task['description'])
        task['description'] = task['description'].encode('utf-8')
        
        redmine_number = getOrCreateValueFromConfig(config, cfg_file_path, 'Redmine projects', translit(task['cat']))
        if(redmine_number is '2'):
            redmine_api = redmine_additional_api
            print 'additional redmine detected'
        else:
            redmine_api = redmine_default_api
            print 'default redmine detected'
            
        issue = redmine_api.issue.get(task_id)
        
        print "task", task_id, issue.subject, "[" + issue.project.name + "]"
        
        time_entries = redmine_api.time_entry.filter(issue_id = task_id, spent_on=dayFrom.strftime('%Y-%m-%d'))
        for time_entry in time_entries:
            print "\t", bcolors.WARNING +\
                'Already have time entry with same date:', \
                time_entry.hours,"\t", time_entry.user.name,"\t", \
                time_entry.comments +\
                bcolors.ENDC
        
        print "\t", task_id, 'hours:', task['hours'], 'description: ', task['description']
        agreeToCreateRedmineTimeEntry = raw_input("\t" + 'Do you want to create new time entry? (y/n) [n]: ')
        
        if agreeToCreateRedmineTimeEntry == "y":
            
            hoursInputed = raw_input("\t" + 'hours spent [' + str(task['hours']) + ']: ')
            try:
                hours = float(hoursInputed)
            except ValueError:
                hours = task['hours']
                
            description = task['description']
            descriptionInputed = raw_input("\t" + 'description ['+description+']: ')
            if descriptionInputed is not '':
                description = descriptionInputed
            
            print "\t", 'Create time entry', task_id, hours, description 
            redmine_api.time_entry.create(\
                issue_id=task_id, \
                spent_on=dayFrom.strftime('%Y-%m-%d'),\
                hours=hours,\
                comments=description\
            )
