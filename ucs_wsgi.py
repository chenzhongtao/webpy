#!/usr/bin/python -u
# coding=utf-8
from __future__ import with_statement

import os
import re
import string
import subprocess
import time
import traceback
import logging
from xml.sax import saxutils

from eventlet import Timeout

from rest_utils import InvalidParameter, InvalidParameterValue, SubSpaceCreateError, \
    SubSpaceChangeError, Success, cmd_parser, pars_parser, multi_cmd_parser, cluster_volume_size_convert_to_GB, cluster_dataunit_size_convert_to_GB
from utils import get_logger, public, json, timing_stats, split_path
from swob import HTTPAccepted, HTTPBadRequest, \
    HTTPCreated, HTTPForbidden, HTTPInternalServerError, \
    HTTPMethodNotAllowed, HTTPNoContent, HTTPNotFound, \
    HTTPPreconditionFailed, HTTPConflict, Request, Response, \
    HTTPInsufficientStorage, HTTPNotAcceptable, HTTPOk
from base import Controller

def cloud_ip_get(cloud_ip_para):
    cloud_ip = re.sub("[{}]","",cloud_ip_para)
    return cloud_ip


#kill process by name
def kill_by_name(name):
    cmd='ps aux|grep %s'%name
    f=os.popen(cmd)
    txt=f.read().splitlines()
    if len(txt) == 0:
        return
    #获取pid
    for line in txt:
        ' '.join(line.split())
        pid = int(line.split()[1])
        cmd = 'kill -9 %d' % pid
        os.system(cmd)

    return True




class UcsController(object):
    """WSGI controller for the cloud server."""
    def __init__(self, conf):
        self.logger = get_logger(conf, log_route='cloud-server')

    @timing_stats()
    def DELETE(self, req):
        """Handle HTTP DELETE request."""
        try:
            filename, response = self.get_filename(req)
            if not filename :
                return response
            first_para, rest_para =  req.split_path(1,2,True)
            

            if not os.path.exists(filename):
                return HTTPBadRequest(body="ERROR : `%s' is not exists.\n" %
                            rest_para, content_type="text/plain", request=req)
            else:
                os.system("rm -rf %s" % filename)
                return Response(body= "Delete %s success.\n" % filename ,
                    content_type="text/plain", request=req)
                      
        except Exception , err:
            print err



    @timing_stats()
    def PUT(self, req):
        """Handle HTTP PUT request."""
        
        #from dbgp.client import brk
        #brk(host="191.168.45.215", port=53541)
        try:
            filename, response = self.get_filename(req)
            if not filename :
                return response
            first_para, rest_para =  req.split_path(1,2,True)

            if not os.path.exists(os.path.split(filename)[0]):
                return HTTPBadRequest(body="ERROR : Directory `%s' is not  exists.\n" %
                            os.path.split(rest_para)[0], content_type="text/plain", request=req)
            if  os.path.exists(filename):
                return HTTPBadRequest(body="ERROR : cannot upload file `%s': File exists.\n" %
                            rest_para, content_type="text/plain", request=req)
            else:
                try:
                    def timeout_reader():
                        return req.environ['wsgi.input'].read(128*1024)
                
                    with open(filename,"w+") as f:
                        for chunk in iter(lambda: timeout_reader(), ''):
                            upload_size = f.write(chunk)
                    return Response(body= "Upload file success.\n",
                        content_type="text/plain", request=req)
                except :
                    os.system("rm -rf %s" % filename)
                    return HTTPBadRequest(body="ERROR : Can not read upload file or file not is exists.\n",
                                          content_type="text/plain", request=req)
                          
        except Exception , err:
            print err
    @timing_stats()
    def GET(self, req):
        """Handle HTTP GET request."""
        
        #from dbgp.client import brk
        #brk(host="191.168.45.215", port=53541)
        try:
            filename, response = self.get_filename(req)
            if not filename :
                return response
            
            #print req.headers['download']
            
            first_para, rest_para =  req.split_path(1,2,True)
            
            if not os.path.exists(filename):
                return HTTPBadRequest(body="ERROR : %s, No such file or directory\n" % rest_para,
                        content_type="text/plain", request=req)
            
            qurey_dict = self.get_query(req)
            if qurey_dict.has_key('download') and qurey_dict['download'].lower() == "true":
                if os.path.isdir(filename):
                    return HTTPBadRequest(body="ERROR : %s is a directory\n" % rest_para,
                        content_type="text/plain", request=req)
                else:
                    f = open(filename,"r")
                    response = Response(request=req, app_iter=f,
                              content_type="application/octet-stream")
                    response.content_length = os.path.getsize(filename)
                    return response
                
            if os.path.isdir(filename):
                #file_list = os.listdir(filename)
                #file_list.sort()
                #s = "\n".join(file_list)
                cmd = "/bin/ls -Alh %s " %filename
                p1 = subprocess.Popen(cmd, shell=True, stderr=subprocess.STDOUT,
                                  stdout=subprocess.PIPE)
                data = p1.stdout.read()
                return Response(body= data,
                        content_type="text/plain", request=req)
            else:
                path, filename = os.path.split(filename)
                cmd = "cd %s ; /bin/ls -Alh %s " %(path, filename)
                p1 = subprocess.Popen(cmd, shell=True, stderr=subprocess.STDOUT,
                                  stdout=subprocess.PIPE)
                data = p1.stdout.read()
                return Response(body= data,
                        content_type="text/plain", request=req)
                
        except Exception , err:
            print err

    @timing_stats()
    def POST(self, req):
        """Handle HTTP PUT request."""
        
        #from dbgp.client import brk
        #brk(host="191.168.45.215", port=53541)
        try:
            filename, response = self.get_filename(req)
            if not filename :
                return response
            first_para, rest_para =  req.split_path(1,2,True)

            if filename[-1] == "/":
                filename = filename[:-1]
                rest_para = rest_para[:-1]
            if not os.path.exists(os.path.split(filename)[0]):
                return HTTPBadRequest(body="ERROR : Directory `%s' is not  exists.\n" %
                            os.path.split(rest_para)[0], content_type="text/plain", request=req)
            if os.path.exists(filename):
                return HTTPBadRequest(body="ERROR : cannot create directory `%s': File exists.\n" %
                            rest_para, content_type="text/plain", request=req)
            else:
                os.mkdir(filename)
                return Response(body= "Create directory success.\n",
                    content_type="text/plain", request=req)
        except Exception , err:
            print err


    @timing_stats()
    def HEAD(self, req):
        """Handle HTTP DELETE request."""
        try:
            filename, response = self.get_filename(req)
            if not filename :
                return response
            first_para, rest_para =  req.split_path(1,2,True)
            

            if not os.path.exists(filename):
                return HTTPBadRequest(body="ERROR : `%s' is not exists.\n" %
                            rest_para, content_type="text/plain", request=req)
            else:
                os.system("rm -rf %s" % filename)
                return Response(body= "Delete %s success.\n" % rest_para ,
                    content_type="text/plain", request=req)
                      
        except Exception , err:
            print err
    
    def get_filename(self, req):
        try:
            first_para, rest_para =  req.split_path(1,2,True)
            if not rest_para :
                return None, HTTPBadRequest(body="ERROR : volume is not found. \n" ,
                        content_type="text/plain", request=req)
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
                return None, HTTPBadRequest(body="ERROR : volume %s is not mount. \n" %                             volume_name,  content_type="text/plain", request=req)
            filename = os.path.join(mount_point, path)
            return filename, None
        except Exception , err:
            print err
            
    def get_query(self, req):
        try :   
            qurey_dict = {}
            if req.query_string:
                qurey_list1 = req.query_string.split(",")
                qurey_list2 = [x.strip().split('=') for x in qurey_list1 if "=" in x]
                qurey_dict = dict(qurey_list2)
        except Exception , err:
            print err
        return qurey_dict
            



