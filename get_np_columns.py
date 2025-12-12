#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# get_np_columns.py
#
# Copyright (c) 2025 Riverbed Technology, Inc.
#
# This software is licensed under the terms and conditions of the MIT License
# accompanying the software ("License").  This software is distributed "AS IS"
# as set forth in 
"""
Get the list of columns available in the NetProfiler.

Usage/Example:

    python get_np_columns.py <host> -u <user name> -p <password> [--list-groupbys] [--centricity c] [--realm r] [--groupby g]
    [--ids colids] [--filter column-filter]

Output sample:

Key Columns                  Label                        ID      Type
-----------------------------------------------------------------------------------------------
app_info                     Application                  52      string
app_name                     Application                  17      app
app_raw                      Raw app                      94      string
c2s_flags                    C2S_FLAGS                    50      string
cli_group_id                 Client Group ID              26      int
cli_group_name               Client Group                 27      group_parts
cli_group_parts              Client Group                 128     group_parts
cli_host_dhcp_dns            Client Host                  74      hostname
cli_host_dns                 Client                       14      host_parts
cli_host_ip                  Client IP                    13      ipaddr
...
"""


from steelscript.netprofiler.commands.columns import Command

if __name__ == '__main__':
    Command().run()

