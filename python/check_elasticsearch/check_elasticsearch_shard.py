# -*- coding: utf-8 -*-
#!/usr/bin/python
##-------------------------------------------------------------------
## @copyright 2017 DennyZhang.com
## Licensed under MIT
##   https://raw.githubusercontent.com/DennyZhang/devops_public/master/LICENSE
##
## File : check_elasticsearch_shard.py
## Author : Denny <denny@dennyzhang.com>
## Description :
##    Make sure ES indices have enough shards.
##    Make sure no same shard(primary, replica) are in the same node, to avoid SPOF
## --
## Created : <2017-02-24>
## Updated: Time-stamp: <2017-03-14 11:33:16>
##-------------------------------------------------------------------
import argparse
import requests
import sys
import socket
import re

NAGIOS_OK_ERROR=0
NAGIOS_EXIT_ERROR=2

def get_es_index_list(es_host, es_port):
    index_list = []
    url = "http://%s:%s/_cat/indices?v" % (es_host, es_port)
    r = requests.get(url)
    '''
Sample output:
root@test:/# curl 172.17.0.8:9200/_cat/indices?v
health status index                                          pri rep docs.count docs.deleted store.size pri.store.size
green  open   master-index-098f6bcd4621d373cade4e832627b4f6    1   0          1            0      8.1kb          8.1kb
green  open   master-index-13a1f8adbec032ed68f3d035449ef48d    1   0          1            0     10.6kb         10.6kb
...
...
'''
    # TODO: error handling, if curl requests fails
    for line in r.content.split("\n"):
        # remove the header
        if " index " in line or line == '':
            continue
        else:
            # get the column of index name
            line = ' '.join(line.split())
            l = line.split(" ")
            index_list.append(l[2])
    return index_list

def get_es_shard_count(es_host, es_port, index_name):
    number_of_shards = -1
    url = "http://%s:%s/%s/_settings?pretty" % (es_host, es_port, index_name)
    r = requests.get(url)
    '''
Sample output:
        ...
        ...
        "number_of_shards" : "1",
        "query" : {
          "bool" : {
            "max_clause_count" : "10240"
        ...
        ...
    '''
    # TODO: error handling, if curl requests fails
    for line in r.content.split("\n"):
        if "\"number_of_shards\" : " in line:
            value = line.split(":")[1]
            value = value.replace(" ", "").replace("\"", "").replace(",", "")
            number_of_shards = int(value)
    if number_of_shards == -1:
        raise Exception("Error: fail to get shard count of elasticsearch index(%s)." % (index_name))
    return number_of_shards

def confirm_es_shard_count(es_host, es_port, es_index_list, \
                             min_shard_count, es_pattern_regexp):
    # Check all ES indices have more than $min_shard_count shards
    failed_index_list = []
    for index_name in es_index_list:
        if es_pattern_regexp != "":
            m = re.search(es_pattern_regexp, index_name)
            # Skip ES index which doesn't match the pattern
            if m is None:
                continue
        number_of_shards = get_es_shard_count(es_host, es_port, index_name)
        if number_of_shards < min_shard_count:
            print "ERROR: index(%s) only has %d shards, less than %d." \
                % (index_name, number_of_shards, min_shard_count)
            failed_index_list.append(index_name)
    return failed_index_list

if __name__ == '__main__':
    # get parameters from users
    parser = argparse.ArgumentParser()
    parser.add_argument('--es_host', required=False, \
                        help="server ip or hostname for elasticsearch instance. Default value is ip of eth0", type=str)
    parser.add_argument('--es_port', default='9200', required=False, \
                        help="server port for elasticsearch instance", type=str)
    parser.add_argument('--es_pattern_regexp', required=False, default='', \
                        help="ES index name pattern. Only ES indices with matched pattern will be examined", type=str)
    parser.add_argument('--min_shard_count', default=3, required=False, \
                        help="minimal shard each elasticsearch index should have", type=str)
    l = parser.parse_args()

    es_port = l.es_port
    min_shard_count = int(l.min_shard_count)
    es_pattern_regexp = l.es_pattern_regexp
    es_host = l.es_host

    if min_shard_count == 0:
        print "OK: skip the check, since the given min_shard_count is 0"
        sys.exit(NAGIOS_OK_ERROR)

    # get ip of eth0, if es_host is not given
    if es_host is None:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        es_host = s.getsockname()[0]

    es_index_list = get_es_index_list(es_host, es_port)

    failed_index_list = confirm_es_shard_count(es_host, es_port, es_index_list, \
                                                 min_shard_count, es_pattern_regexp)

    if len(failed_index_list) != 0:
        print "ERROR: Below indices don't have enough shard:\n%s" % \
            (",".join(failed_index_list))
        sys.exit(NAGIOS_EXIT_ERROR)
    else:
        # TODO: make sure no same shard in one node, to avoid SPOF
        print "OK: all ES indices have no less than %d shards" % (min_shard_count)
        sys.exit(NAGIOS_OK_ERROR)
## File : check_elasticsearch_shard.py ends
