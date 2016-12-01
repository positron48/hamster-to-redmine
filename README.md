# hamster-to-redmine
Export time from hamster to redmine

Simple python script for export your time from [hamster](https://github.com/projecthamster/hamster) to [redmine](http://www.redmine.org/) via [redmine rest api](http://www.redmine.org/projects/redmine/wiki/Rest_api).

Script dirrectly connect to Hamster's sqlite database file to get time data. Time data are grouped by number of task and send via [python-redmine](http://python-redmine.readthedocs.io/installation.html) to server.

To use this script you need run in like this:
```
$ python hamster-to-redmine.py [date]
```
Date must be like 'dd.mm.yyyy'. Script use current date if argument isn't set.

#### Example of script working:
```
$ python hamster-to-redmine.py 01.12.2016
Redmine url: http://redmine.example.com/
login: username
password of username: 
Getting data from 2016-12-01 00:00:00 to 2016-12-02 00:00:00:
Not redmine task: 0.5 task example [example tag] (activity description)
2016-12-01:
task 1111 Redmine task name [redmine project name]
    1111 hours: 6.75 description: activity desctiption from hamster
    Do you want to create new time entry? (y/n) [n]: y
    hours spent [6.75]: 7
    description [activity desctiption from hamster]:
    Create time entry 41021 7 activity desctiption from hamster
task 1122 Redmine task name #2 [redmine project name]
    Already have time entry with the same date: 0.25  username  testing task
    1122 hours: 0.25 description:
    Do you want to create new time entry? (y/n) [n]: n
```

#### Rules to log time via Hamster:
* activity name: '#TASK_ID# any text'
* activity description: 'any text'

Activities groups by #TASK_ID# with summing of hours and joining unique description. Project and tags from hamster aren't used.
