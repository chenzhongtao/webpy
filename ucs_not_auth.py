#!/usr/bin/env python
# coding=utf-8

import web
import os
import re
import string
import subprocess
import time
from web.wsgiserver import CherryPyWSGIServer

BUF_SIZE = 128*1024
  
  
#CherryPyWSGIServer.ssl_certificate = "/root/ssl/webpy/host.cert"  
#CherryPyWSGIServer.ssl_private_key = "/root/ssl/webpy/host.key" 

urls = (
    '/', 'index',
    '/ucs/.*', 'UcsController'
)

            
class UcsController(object):
    """WSGI controller for the cloud server."""


    def GET(self):
        """Handle HTTP GET request."""
        
        #from dbgp.client import brk
        #brk(host="191.168.45.215", port=52338)
        try:
            user_data = web.input()
            #print user_data
            #ctx = web.ctx
            #env = web.ctx.env
            #print user
            #path = web.ctx.path
            #print path
            filename, response = self.get_filename(web.ctx.path[1:])
            #print filename, response
            if not filename :
                return response
            
            #print req.headers['download']
            
            first_para, rest_para =  web.ctx.path[1:].split('/',1)
            
            if not os.path.exists(filename):
                return "ERROR : %s, No such file or directory\n" % rest_para
            
            qurey_dict = web.input()
            if qurey_dict.has_key('download') and qurey_dict['download'].lower() == "true":
                if os.path.isdir(filename):
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
            
    def PUT(self):
        """Handle HTTP PUT request."""
        
        #from dbgp.client import brk
        #brk(host="191.168.45.215", port=53541)
        try:
            filename, response = self.get_filename(web.ctx.path[1:])
            if not filename :
                return response
            first_para, rest_para =  web.ctx.path[1:].split('/',1)
            print web.ctx.env.get('CONTENT_LENGTH')
 

            if not os.path.exists(os.path.split(filename)[0]):
                return "ERROR : Directory `%s' is not  exists.\n" % os.path.split(rest_para)[0]
            if  os.path.exists(filename):
                return "ERROR : cannot upload file '%s': File exists.\n" % rest_para
            else:
                try:
                    def timeout_reader():
                        return web.ctx.env.get("wsgi.input").read(128*1024)
                
                    with open(filename,"w+") as f:
                        for chunk in iter(lambda: timeout_reader(), ''):
                            upload_size = f.write(chunk)
                    return "Upload file success.\n"
                except Exception , err:
                    os.system("rm -rf %s" % filename)
                    print err
                    return "ERROR : Can not read upload file or file not is exists.\n"
                          
        except Exception , err:
            print err

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
            if not os.path.exists(os.path.split(filename)[0]):
                return "ERROR : Directory '%s' is not  exists.\n" % os.path.split(rest_para)[0]
            if os.path.exists(filename):
                return "ERROR : cannot create directory `%s': File exists.\n" % rest_para
            else:
                os.mkdir(filename)
                return "Create directory success.\n"
        except Exception , err:
            print err
            
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
                return "ERROR : Delete the root directory is forbidden.\n" 
            
            if not os.path.exists(filename):
                return "ERROR : `%s' is not exists.\n" % rest_para
            else:
                os.system("rm -rf %s" % filename)
                return "Delete '%s' success.\n" % filename               
        except Exception , err:
            print err

    
    def get_filename(self, url_path):
        try:
            if "/" in url_path:
                first_para, rest_para =  url_path.split('/',1)
            if "/" not in url_path or not rest_para :
                #web.ctx.status = 404
                return None, "ERROR : volume is not found. \n"
            volume_name = rest_para
            path = ''
            if "/" in rest_para:
                volume_name, path = rest_para.split('/',1)
            mount_point = ""
            f = open("/proc/mounts","r")
            mount_str = f.read()
            m = re.match("[\s\S]*:/%s (.*?) fuse" % volume_name, mount_str)
            if m is not None:
                mount_point = m.group(1)
            else:
                #return None, web.NotFound("Sorry, the page you were looking for was not found.")
                return None, "ERROR : volume '%s' is not mount. \n" % volume_name
            filename = os.path.join(mount_point, path)
            return filename, None
        except Exception , err:
            print err

  

if __name__ == "__main__":
    app = web.application(urls, globals())
    app.run()