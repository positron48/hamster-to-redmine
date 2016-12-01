import sqlite3 as sqlite
import sys
import os
from xdg.BaseDirectory import xdg_data_home
import re
from boto.dynamodb.condition import NULL
import datetime
from redmine import Redmine

try:
    dayFrom = datetime.datetime.strptime(sys.argv[1], '%d.%m.%Y')
    dayTo = dayFrom + datetime.timedelta(days=1)
except IndexError:
    dayFrom = datetime.date.today()
    dayTo = dayFrom + datetime.timedelta(days=1)
    
print "stats from", dayFrom, "to", dayTo

database_dir = os.path.realpath(os.path.join(xdg_data_home, "hamster-applet"))
db_path = os.path.join(database_dir, "hamster.db")


con = sqlite.connect(db_path, sqlite.PARSE_DECLTYPES | sqlite.PARSE_COLNAMES)
cur = con.cursor()

#get all tasks from date
query = """SELECT a.id AS id,
                  a.start_time AS start_time,
                  a.end_time AS end_time,
                  a.description as description,
                  b.name AS name, b.id as activity_id,
                  c.name as category,
                  e.name as tag
            FROM facts a
            LEFT JOIN activities b ON a.activity_id = b.id
            LEFT JOIN categories c ON b.category_id = c.id
            LEFT JOIN fact_tags d ON d.fact_id = a.id
            LEFT JOIN tags e ON e.id = d.tag_id
            WHERE a.start_time > '"""+dayFrom.strftime('%Y-%m-%d')+"""' AND a.end_time < '"""+dayTo.strftime('%Y-%m-%d')+"""'
            ORDER BY a.start_time ASC"""
            
cur.execute(query)  # tags, categories, activities, facts

tags = cur.fetchall()
cur.close()

#format dictionary
tasks = {}
for (i, tag) in enumerate(tags):
    start = datetime.datetime.strptime(tag[1], '%Y-%m-%d %H:%M:%S')
    end = datetime.datetime.strptime(tag[2], '%Y-%m-%d %H:%M:%S')
    hours = (end - start).seconds/3600.0

    if tag[3] is None:
        description = ''
    else:
        description = tag[3]
        
    tasks[i] = {
        'id':tag[0], 
        'start':start, 
        #'end':end, 
        'hours':hours,
        'description':description, 
        'name':tag[4], 
        #'cat':tag[5], 
        'tag':tag[6]
    }
    
#parse redmine task_id
for task in tasks.values():
    result = re.match(r'^\d+', task['name'])
    if result:
        task_id = result.group(0)
        task['task_id'] = task_id
    else:
        task['task_id'] = ''

#format data to write in redmine: group by date, task_id
try:
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
            print '!!not redmine task:', task['hours'], task['name'], "[" + task['tag'] + "]", "(" + task['description'] + ")"
        
    dkeys = redmine_tasks.keys()
    dkeys = list(dkeys)
    dkeys.sort()
    
    redmine = Redmine('http://redmine.skillum.ru/', username='#YOUR_USERNAME#', password='#YOUR_LOGIN#')
    
    
    for date in dkeys:
        print date, ':'
        dayHours = 0
        for (task_id, task) in redmine_tasks[date].items():          
            task['description'] = set(task['description'])
            task['description'] = list(task['description'])
            task['description'] = ', '.join(task['description'])
            task['description'] = task['description'].encode('utf-8')
            
            issue = redmine.issue.get(task_id)
            print "task", task_id, issue.subject, "[" + issue.project.name + "]"
            print "\t", round(task['hours'], 2), "\t", task['name'], "(" + task['description'] + ")"
        
            time_entries = redmine.time_entry.filter(issue_id = task_id, spent_on=dayFrom.strftime('%Y-%m-%d'))
            for time_entry in time_entries:
                print "\t", '!!Already have time entry:', time_entry.hours,"\t", time_entry.user.name,"\t", time_entry.comments
            
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
                redmine.time_entry.create(issue_id=task_id, spent_on=dayFrom.strftime('%Y-%m-%d'),hours=hours,comments=description)
                        
except KeyboardInterrupt:
    print "\nexit"
