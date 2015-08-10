#!/usr/bin/env python
# coding=utf-8

import web
import os
import sys
import re
import string
import subprocess
import time
import base64
from web.wsgiserver import CherryPyWSGIServer

BUF_SIZE = 128*1024

# scp -rp  /usr/lib64/python2.6/site-packages/psycopg2* root@191.168.45.106:/usr/lib64/python2.6/site-packages/
def get_db_data(tables, vars=None, what='*', where=None, order=None, group=None, 
               limit=None, offset=None, _test=False):
    db = web.database(dbn='postgres', db='store_configure',port=3306, user='postgres',
                      pw='=[/]ASDFjkl123//')
    results = db.select(tables, vars=vars, what=what, where=where, order=order, group=group, 
               limit=limit, offset=offset, _test=_test)
    data = []
    for i in range(len(results)) :
        data.append(results[i])
    return data

 
def auth_required(func):
    def func_auth(arg):
        auth = web.ctx.env.get('HTTP_AUTHORIZATION')
        authreq = False
        if auth is None:
            authreq = True
        else:
            auth = re.sub('^Basic ','',auth)
            username,password = base64.decodestring(auth).split(':')
            if username and password:
                data = get_db_data('tb_nas_user',where="username='%s'"% username )
                if data and data[0]["password"] == password:
                    user_id = data[0]["id"]
                    data = get_db_data('tb_nas_user_share',where="user_id='%s'" % user_id)
                    user_share = {1:[],2:[],3:[]}
                    for item in data:
                        sharename = get_db_data('tb_nas_share',where="id='%s'" % item["share_id"])[0]["sharename"]
                        user_share[item["access"]].append(sharename)
                    path_list = web.ctx.path[1:].split("/",3) # ucs + volume + sharename + subpath
                    if func.__name__ in ["PUT", "POST", "DELETE"]: 
                        if len(path_list) <= 3 or not path_list[3]:
                            web.ctx.status = '403 Forbidden'
                            return "ERROR : This path not permit the action '%s'\n" % func.__name__
                        else:
                            if path_list[2] not in user_share[3]:
                                web.ctx.status = '403 Forbidden'
                                return "ERROR : The path is not exists or permission denied\n" 
                    if  func.__name__ in ['GET']:
                        if len(path_list) >= 3 and  path_list[2]:
                            if path_list[2] not in user_share[3] or path_list[2] not in user_share[2]:
                                web.ctx.status = '403 Forbidden'
                                return "ERROR : The path is not exists or permission denied\n" 
                        else:
                            return func(arg,user_share)
                else:
                    authreq = True
            else:
                authreq = True
        if authreq:
            web.ctx.status = '401 Unauthorized'
            return "ERROR : User does not exist or password error\n"
        return func(arg)
    return func_auth



urls = (
    #'/', 'index',
    '/ucs/.*', 'UcsController'
)

            
class UcsController(object):
    """WSGI controller for the cloud server."""

    @auth_required
    def GET(self, user_share = None):
        """Handle HTTP GET request."""
        
        #from dbgp.client import brk
        #brk(host="191.168.45.215", port=52338)
        try:
            #import pdb
            #pdb.set_trace()
            user_data = web.input()
            filename, response = self.get_filename(web.ctx.path[1:])
            #print filename, response
            if not filename :
                return response
            
            #print req.headers['download']
            
            #print user_share;
            first_para, rest_para =  web.ctx.path[1:].split('/',1)
            
            if not os.path.exists(filename):
                web.ctx.status = "404 Not Found"
                return "ERROR : %s, No such file or directory\n" % rest_para
            
            qurey_dict = web.input()
            if qurey_dict.has_key('download') and qurey_dict['download'].lower() == "true":
                if os.path.isdir(filename):
                    web.ctx.status = "403 Forbidden"
                    return "ERROR : %s is a directory\n" % rest_para
                else:
                    def download(filename):
                        web.header('Transfer-Encoding','chunked')
                        web.header('Content-Type','application/octet-stream')
                        web.header('CONTENT_LENGTH',os.path.getsize(filename))
                        f = open(filename,"rb")
                        while True:
                            c = f.read(BUF_SIZE)
                            if c:
                                yield c
                            else:
                                break
                    return download(filename)
                        
            if os.path.isdir(filename):
                #file_list = os.listdir(filename)
                #file_list.sort()
                #s = "\n".join(file_list)
                if  user_share :
                    cmd = "cd %s ; /bin/ls -Alhd" % filename
                    for i in range(1, 4):
                        for file_name in user_share[i]:
                            print file_name
                            cmd = cmd + " " + file_name
                    p1 = subprocess.Popen(cmd, shell=True, stderr=subprocess.STDOUT,
                        stdout=subprocess.PIPE)
                    data = p1.stdout.read()
                    return data
                    
                else:
                    cmd = "/bin/ls -Alh %s " %filename
                    p1 = subprocess.Popen(cmd, shell=True, stderr=subprocess.STDOUT,
                                      stdout=subprocess.PIPE)
                    data = p1.stdout.read()
                    return data
            else:
                path, filename = os.path.split(filename)
                cmd = "cd %s ; /bin/ls -Alh %s " %(path, filename)
                p1 = subprocess.Popen(cmd, shell=True, stderr=subprocess.STDOUT,
                                  stdout=subprocess.PIPE)
                data = p1.stdout.read()
                return data
                
        except Exception , err:
            print err
            
    @auth_required      
    def PUT(self):
        """Handle HTTP PUT request."""
        
        #from dbgp.client import brk
        #brk(host="191.168.45.215", port=53541)
        try:
            filename, response = self.get_filename(web.ctx.path[1:])
            if not filename :
                return response
            first_para, rest_para =  web.ctx.path[1:].split('/',1)
 

            if not os.path.exists(os.path.split(filename)[0]):
                web.ctx.status = "404 Not Found"
                return "ERROR : Directory `%s' is not  exists.\n" % os.path.split(rest_para)[0]
            if  os.path.exists(filename):
                web.ctx.status = "409 Conflict"
                return "ERROR : cannot upload file '%s': File exists.\n" % rest_para
            else:
                try:
                    def timeout_reader():
                        return web.ctx.env.get("wsgi.input").read(128*1024)
                
                    with open(filename,"w+") as f:
                        for chunk in iter(lambda: timeout_reader(), ''):
                            upload_size = f.write(chunk)
                    web.ctx.status = "201 Created"
                    return "Upload file success.\n"
                except Exception , err:
                    os.system("rm -rf %s" % filename)
                    print err
                    web.ctx.status = "409 Conflict"
                    return "ERROR : Can not read upload file or file not is exists.\n"
                          
        except Exception , err:
            print err
            
    @auth_required
    def POST(self):
        """Handle HTTP PUT request."""
        
        #from dbgp.client import brk
        #brk(host="191.168.45.215", port=53541)
        try:
            filename, response = self.get_filename(web.ctx.path[1:])
            if not filename :
                return response
            first_para, rest_para =  web.ctx.path[1:].split('/',1)

            if filename[-1] == "/":
                filename = filename[:-1]
                rest_para = rest_para[:-1]
            # 判断父目录是否存在
            if not os.path.exists(os.path.split(filename)[0]):
                web.ctx.status = "404 Not Found"
                return "ERROR : Directory '%s' is not  exists.\n" % os.path.split(rest_para)[0]
            if os.path.exists(filename):
                web.ctx.status = "409 Conflict"
                return "ERROR : cannot create directory `%s': File exists.\n" % rest_para
            else:
                os.mkdir(filename)
                web.ctx.status = "201 Created"
                return "Create directory success.\n"
        except Exception , err:
            print err
    
    @auth_required      
    def DELETE(self):
        """Handle HTTP DELETE request."""
        try:
            filename, response = self.get_filename(web.ctx.path[1:])
            if not filename :
                return response
            first_para, rest_para =  web.ctx.path[1:].split('/',1)
            if "/" in rest_para:
                volume_name, path = rest_para.split('/',1)
            if "/" not in rest_para or not path:
                web.ctx.status = "403 Forbidden"
                return "ERROR : Delete the root directory is forbidden.\n" 
            
            if not os.path.exists(filename):
                web.ctx.status = "404 Not Found"
                return "ERROR : `%s' is not exists.\n" % rest_para
            else:
                os.system("rm -rf %s" % filename)
                return "Delete '%s' success.\n" % rest_para              
        except Exception , err:
            print err

    
    def get_filename(self, url_path):
        try:
            if "/" in url_path:
                first_para, rest_para =  url_path.split('/',1)
            if "/" not in url_path or not rest_para :
                #web.ctx.status = 404
                web.ctx.status = "404 Not Found"
                return None, "ERROR : volume is not found. \n"
            volume_name = rest_para
            path = ''
            if "/" in rest_para:
                volume_name, path = rest_para.split('/',1)
            mount_point = ""
            f = open("/proc/mounts","r")
            mount_str = f.read()
            m = re.match("[\s\S]*?:/%s (.*?) fuse" % volume_name, mount_str)
            if m is not None:
                mount_point = m.group(1)
                if not os.path.exists(mount_point):
                    web.ctx.status = "404 Not Found"
                    return None, "ERROR : volume '%s' mount error, Transport endpoint is not connected\n" % volume_name
            else:
                #return None, web.NotFound("Sorry, the page you were looking for was not found.")
                web.ctx.status = "404 Not Found"
                return None, "ERROR : volume '%s' is not mount. \n" % volume_name
            filename = os.path.join(mount_point, path)
            return filename, None
        except Exception , err:
            print err

  

if __name__ == "__main__":
    if "-s" in sys.argv:
        CherryPyWSGIServer.ssl_certificate = "./host.cert"  
        CherryPyWSGIServer.ssl_private_key = "./host.key"
    app = web.application(urls, globals())
    app.run()