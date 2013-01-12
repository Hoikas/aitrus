#!/usr/bin/env python3

import asyncore
import os, sys
import threading
import http.client
import socket
import json
import time
import getpass
import base64

from irc import *

BOT_VERSION = "Aitrus 0.1"

class AitrusBot(IRCBotBase):
    def handle_connect(self):
        self.join_channel(sys.argv[4])

    def handle_ctcp(self, sender, msg):
        if msg == "VERSION":
            self.send_nctcp(sender, "%s {Python v%s}" % (BOT_VERSION, sys.version))
        elif msg == "TIME":
            self.send_nctcp(sender, "TIME keeps on slippin', slippin'")

    def handle_kick(self, channel, reason):
        # auto rejoin kicked channels
        self.join_channel(channel)


class hubber:
    def __init__(self, repo, irc, username, password):
        self.repo = repo
        self.pulls = {}
        self.issues = {}
        self.irc = irc

        self.htclient = http.client.HTTPSConnection('api.github.com')
        authkey = base64.b64encode(bytes('%s:%s' % (username, password), 'utf8')).decode('ascii')
        self.headers = { 'Authorization': 'Basic ' + authkey }

    def init_db(self):
        self.htclient.request('GET', '/repos/%s/pulls?state=open' % (self.repo),
                              headers=self.headers)
        reply = self.htclient.getresponse()
        if reply.status != 200:
            print('Error fetching open pull requests')
            print(reply.headers)
            print(reply.read())
            sys.exit(1)
        jdata = json.loads(str(reply.read(), 'utf8'))

        for pull in jdata:
            pull_id = pull['number']
            self.pulls[pull_id] = {
                'url': pull['html_url'],
                'user': pull['user']['login'],
                'title': pull['title'],
                }

        self.htclient.request('GET', '/repos/%s/issues?state=open' % (self.repo),
                              headers=self.headers)
        reply = self.htclient.getresponse()
        if reply.status != 200:
            print('Error fetching open issues')
            print(reply.headers)
            print(reply.read())
            sys.exit(1)
        jdata = json.loads(str(reply.read(), 'utf8'))

        for issue in jdata:
            issue_id = issue['number']
            self.issues[issue_id] = {
                'url': issue['html_url'],
                'user': issue['user']['login'],
                'title': issue['title'],
                }

    def check_pulls(self):
        self.htclient.request('GET', '/repos/%s/pulls?state=open' % (self.repo),
                              headers=self.headers)
        reply = self.htclient.getresponse()
        if reply.status != 200:
            print('Error fetching new pull requests')
            print(reply.headers)
            print(reply.read())
        jdata = json.loads(str(reply.read(), 'utf8'))

        watch = set(self.pulls.keys())
        for pull in jdata:
            pull_id = pull['number']
            if pull_id not in watch:
                self.pulls[pull_id] = {
                    'url': pull['html_url'],
                    'user': pull['user']['login'],
                    'title': pull['title'],
                    }
                self.irc.send_wallchan("%s has created pull request #%d (%s): %s" \
                    % (self.pulls[pull_id]['user'], pull_id,
                       self.pulls[pull_id]['title'],
                       self.pulls[pull_id]['url']))
            else:
                watch.remove(pull_id)

        for pull in watch:
            # Find out who closed it
            self.htclient.request('GET', '/repos/%s/pulls/%d' % (self.repo, pull),
                                  headers=self.headers)
            reply = self.htclient.getresponse()
            if reply.status != 200:
                print('Error fetching pull request %d' % pull)
                print(reply.headers)
                print(reply.read())
            jdata = json.loads(str(reply.read(), 'utf8'))

            if jdata['merged']:
                self.irc.send_wallchan("%s has merged pull request #%d (%s)" \
                    % (jdata['merged_by']['login'], pull,
                       jdata['title']))
            else:
                self.irc.send_wallchan("Pull request #%d (%s) has been closed" \
                    % (jdata['number'], jdata['title']))

            del self.pulls[pull]

    def check_issues(self):
        self.htclient.request('GET', '/repos/%s/issues?state=open' % (self.repo),
                              headers=self.headers)
        reply = self.htclient.getresponse()
        if reply.status != 200:
            print('Error fetching new issues')
            print(reply.headers)
            print(reply.read())
        jdata = json.loads(str(reply.read(), 'utf8'))

        watch = set(self.issues.keys())
        for issue in jdata:
            issue_id = issue['number']
            if issue_id not in watch:
                self.issues[issue_id] = {
                    'url': issue['html_url'],
                    'user': issue['user']['login'],
                    'title': issue['title'],
                    }
                self.irc.send_wallchan("%s has created issue #%d (%s): %s" \
                    % (self.issues[issue_id]['user'], issue_id,
                       self.issues[issue_id]['title'],
                       self.issues[issue_id]['url']))
            else:
                watch.remove(issue_id)

        for issue in watch:
            self.irc.send_wallchan("Issue #%d (%s) has been closed" \
                % (issue, self.issues[issue]['title']))

            del self.issues[issue]

def hub_watcher(repos):
    while True:
        time.sleep(30)
        for repo in repos:
            repo.check_pulls()
        time.sleep(30)
        for repo in repos:
            repo.check_issues()

if len(sys.argv) < 6:
    print("Usage:  %s hostname port nick channel user/repo [user/repo [...]]" % sys.argv[0])
    sys.exit(1)

host = sys.argv[1]
port = int(sys.argv[2])
nick = sys.argv[3]
hub_repos = sys.argv[5:]

hub_user = input('Github Email/Username: ')
hub_pass = getpass.getpass()

irc = AitrusBot(host, port, nick)
repos = []
for repo in hub_repos:
    _hub = hubber(repo, irc, hub_user, hub_pass)
    _hub.init_db()
    repos.append(_hub)

hub_th = threading.Thread(target=hub_watcher, args=(repos,))
hub_th.daemon = True
hub_th.start()
asyncore.loop()
